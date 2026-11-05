"""Cadastro local de localidades marítimas, separado das rotas comerciais."""
from functools import lru_cache
import json
from pathlib import Path
import unicodedata

from consumo.catalogo import ErroCatalogo
from scripts.importar_unlocode import CODIGO, STATUS

PASTA = Path(__file__).resolve().parents[1] / "dados"


def validar_base(base):
    paises, portos = base["paises"], base["portos"]
    for iso, pais in paises.items():
        if pais.get("iso") != iso or len(iso) != 2 or not iso.isascii() or not iso.isupper() or not iso.isalpha():
            raise ValueError(f"País inválido: {iso}")
    for codigo, porto in portos.items():
        if (not CODIGO.fullmatch(codigo) or porto.get("unlocode") != codigo
                or porto.get("pais_iso") != codigo[:2] or codigo[:2] not in paises):
            raise ValueError(f"Relação país/porto inválida: {codigo}")
        if (not porto.get("funcao", "").startswith("1") or porto.get("status") not in STATUS
                or porto.get("alteracao") in ("X", "=")):
            raise ValueError(f"Localidade fora do filtro marítimo: {codigo}")


@lru_cache(maxsize=1)
def carregar_portos():
    try:
        base = json.loads((PASTA / "portos_unlocode.json").read_text(encoding="utf-8"))
        config = json.loads((PASTA / "navegacao.json").read_text(encoding="utf-8"))
        validar_base(base)
        for codigo in [config["origem_padrao"], config["destino_padrao"], *config["favoritos"]]:
            if codigo not in base["portos"]:
                raise ValueError(f"Porto configurado ausente na base: {codigo}")
        for iso, dados in config["paises"].items():
            porto = base["portos"].get(dados["porto_padrao"], {})
            if iso not in base["paises"] or porto.get("pais_iso") != iso:
                raise ValueError(f"Porto padrão incompatível com país: {iso}")
        return base, config
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as erro:
        raise ErroCatalogo(f"Falha na base de portos: {erro}. Confira a importação UN/LOCODE.") from erro


def nome_pais(base, config, iso):
    return config["paises"].get(iso, {}).get("nome", base["paises"][iso]["nome"])


def rotulo_porto(porto):
    sub = porto.get("subdivisao") or "subdivisão não informada"
    nome_sub = porto.get("nome_subdivisao")
    return f"{porto['nome']} · {sub}{' / ' + nome_sub if nome_sub else ''} · {porto['unlocode']}"


def normalizar_busca(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto.casefold()) if not unicodedata.combining(c))


def buscar_portos(base, iso, busca="", favoritos=()):
    busca = normalizar_busca(busca.strip())
    opcoes = [p for p in base["portos"].values() if p["pais_iso"] == iso
              and (not busca or busca in normalizar_busca(rotulo_porto(p) + " " + p.get("nome_sem_acentos", "") + " " + " ".join(p.get("nomes_alternativos", []))))]
    return sorted(opcoes, key=lambda p: (p["unlocode"] not in favoritos, normalizar_busca(p["nome"]), p["unlocode"]))


def garantir_selecao(estado, chave, opcoes, padrao=None):
    """Remove seleção incompatível antes de criar o widget dependente."""
    if estado.get(chave) not in opcoes:
        estado[chave] = padrao if padrao in opcoes else (opcoes[0] if opcoes else None)


def invalidar_resultado(estado, selecao):
    if estado.get("selecao_operacao") != selecao:
        estado["selecao_operacao"] = selecao
        for chave in ("cambio_simulador", "falha_cambio", "registro_salvo", "fotografia", "resultado_id"):
            estado.pop(chave, None)


def consultar_rota(config, origem, destino):
    """Somente a combinação exata pode recuperar informação comercial."""
    return next((r for r in config["rotas"] if r["origem_unlocode"] == origem
                 and r["destino_unlocode"] == destino), None)


def dados_localidade(base, config, codigo):
    p = base["portos"][codigo]
    return dict(porto=p["nome"], pais=nome_pais(base, config, p["pais_iso"]),
                pais_iso=p["pais_iso"], unlocode=codigo, subdivisao=p["subdivisao"],
                moeda=config["paises"].get(p["pais_iso"], {}).get("moeda"))
