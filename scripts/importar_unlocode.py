"""Importa o ZIP CSV oficial sem extrair arquivos e sem dependências adicionais."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLICACAO = "2025-1"
URL = "https://opensource.unicc.org/un/unece/uncefact/vocab-locode/-/jobs/artifacts/2025-1/download?job=package-release"
STATUS = frozenset(("AA", "AC", "AF", "AI", "AM", "AS", "RL"))
CODIGO = re.compile(r"[A-Z]{2}[A-Z2-9]{3}")


def elegivel(linha):
    return (len(linha) >= 12 and linha[0].strip() not in ("X", "=")
            and linha[6].strip().startswith("1") and linha[7].strip() in STATUS)


def processar_zip(conteudo, versao, url, obtido_em):
    """Processamento determinístico, com proveniência fornecida pelo download."""
    paises, portos, subdivisoes = {}, {}, {}
    duplicados, conflitos = {}, set()
    with zipfile.ZipFile(io.BytesIO(conteudo)) as arquivo:
        partes = sorted(n for n in arquivo.namelist()
                        if re.search(r"UNLOCODE CodeListPart[123]\.csv$", n))
        if len(partes) != 3:
            raise ValueError("O ZIP deve conter as três partes CSV oficiais da publicação.")
        subs = [n for n in arquivo.namelist() if n.endswith("/SubdivisionCodes.csv")]
        if len(subs) != 1:
            raise ValueError("SubdivisionCodes.csv ausente ou duplicado.")
        for row in csv.reader(io.StringIO(arquivo.read(subs[0]).decode("utf-8-sig"))):
            if len(row) >= 3:
                subdivisoes[(row[0], row[1])] = row[2]
        for nome in partes:
            for row in csv.reader(io.StringIO(arquivo.read(nome).decode("utf-8-sig"))):
                if len(row) < 12:
                    raise ValueError(f"Linha CSV incompleta em {nome}.")
                row = [v.strip() for v in row]
                pais = row[1].upper()
                if not row[2] and row[3].startswith("."):
                    paises[pais] = dict(iso=pais, nome=row[3][1:].strip())
                    continue
                if not elegivel(row):
                    continue
                codigo = pais + row[2].upper()
                if not CODIGO.fullmatch(codigo):
                    raise ValueError(f"UN/LOCODE malformado: {codigo}")
                if codigo in conflitos:
                    duplicados[codigo].append(row)
                    continue
                if codigo in portos:
                    anterior = portos[codigo]
                    duplicados.setdefault(codigo, []).append(row)
                    if (anterior["funcao"], anterior["status"], anterior["subdivisao"]) != (row[6], row[7], row[5] or None):
                        conflitos.add(codigo)
                        del portos[codigo]
                        continue
                    # Aliases de nome: manter registro mais recente; desempate
                    # pelo indicador de mudança de nome e nome lexical.
                    rank = (row[8], row[0] == "#", row[3])
                    rank_anterior = (anterior["atualizado_em"] or "", anterior["alteracao"] == "#", anterior["nome"])
                    if rank <= rank_anterior:
                        anterior.setdefault("nomes_alternativos", []).append(row[3])
                        continue
                    aliases = [anterior["nome"], *anterior.get("nomes_alternativos", [])]
                else:
                    aliases = []
                portos[codigo] = dict(unlocode=codigo, nome=row[3], nome_sem_acentos=row[4],
                    pais_iso=pais, subdivisao=row[5] or None,
                    nome_subdivisao=subdivisoes.get((pais, row[5])),
                    funcao=row[6], status=row[7], alteracao=row[0] or None,
                    atualizado_em=row[8] or None, coordenadas=row[10] or None,
                    observacoes=row[11] or None, nomes_alternativos=aliases)
    usados = {p["pais_iso"] for p in portos.values()}
    if not usados or usados - paises.keys():
        raise ValueError("País ausente ou nenhum porto elegível na publicação.")
    return dict(metadados=dict(publicacao=versao, url=url,
                pagina_publicacao="https://unlocode.unece.org/publications/",
                obtido_em=obtido_em, sha256=hashlib.sha256(conteudo).hexdigest(),
                atribuicao="United Nations Economic Commission for Europe (UNECE), UN/LOCODE; cópia filtrada pelo projeto.",
                licenca="CC BY 4.0, conforme indicação na página da publicação",
                termos="https://unlocode.unece.org/terms/",
                documentacao="https://unlocode.unece.org/recommendation16/",
                filtro=dict(funcao="primeiro caractere igual a 1 (marítimo)",
                            status=sorted(STATUS), alteracoes_excluidas=["X", "="]),
                codigos_com_duplicatas=sorted(duplicados), duplicatas_conflitantes_excluidas=sorted(conflitos),
                criterio_duplicatas="Aliases com mesma função/status/subdivisão: registro mais recente; desempate por # e nome. Conflitos excluídos.",
                total_paises=len(usados), total_localidades=len(portos)),
                paises={p: paises[p] for p in sorted(usados)},
                portos={k: portos[k] for k in sorted(portos)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo", type=Path, help="ZIP oficial previamente obtido")
    parser.add_argument("--versao", default=PUBLICACAO)
    parser.add_argument("--url", default=URL)
    parser.add_argument("--obtido-em", help="Data/hora ISO real da obtenção (obrigatória com --arquivo)")
    parser.add_argument("--saida", type=Path, default=ROOT / "dados" / "portos_unlocode.json")
    args = parser.parse_args()
    if args.versao != PUBLICACAO and args.url == URL:
        parser.error("Ao mudar a versão, informe também a URL da publicação correspondente.")
    if args.arquivo:
        if not args.obtido_em:
            parser.error("Informe --obtido-em com a data real de obtenção do ZIP.")
        if datetime.fromisoformat(args.obtido_em).tzinfo is None:
            parser.error("--obtido-em deve incluir o fuso horário real.")
        conteudo, obtido = args.arquivo.read_bytes(), args.obtido_em
    else:
        with urlopen(args.url, timeout=60) as resposta:
            conteudo = resposta.read()
        obtido = datetime.now(timezone.utc).isoformat()
    dados = processar_zip(conteudo, args.versao, args.url, obtido)
    args.saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dados["metadados"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
