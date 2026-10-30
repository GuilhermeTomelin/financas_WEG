import json
from pathlib import Path

CAMINHO_PRODUTOS = Path(__file__).resolve().parent.parent / "dados" / "produtos.json"


class ErroCatalogo(Exception):
    """Erro ao carregar o catálogo de produtos."""


def carregar_catalogo():
    try:
        with open(CAMINHO_PRODUTOS, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except FileNotFoundError as erro:
        raise ErroCatalogo(
            f"Arquivo do catálogo não encontrado: {CAMINHO_PRODUTOS}"
        ) from erro
    except ValueError as erro:
        raise ErroCatalogo("O arquivo do catálogo não contém um JSON válido.") from erro
    except OSError as erro:
        raise ErroCatalogo(f"Não foi possível ler o catálogo: {erro}") from erro

    produtos = dados.get("produtos") if isinstance(dados, dict) else None
    if not isinstance(produtos, list) or not produtos:
        raise ErroCatalogo("O catálogo deve ter uma lista não vazia em 'produtos'.")

    return produtos

def carregar_dados_simulador():
    pasta = CAMINHO_PRODUTOS.parent

    def ler_json(nome):
        try:
            conteudo = (pasta / nome).read_text(encoding="utf-8-sig")
            return json.loads(conteudo)
        except (OSError, ValueError) as erro:
            raise ErroCatalogo(f"Falha ao ler {nome}: {erro}") from erro

    catalogo = ler_json("produtos_simulados.json")
    rotas = ler_json("rotas.json")

    if not isinstance(catalogo, dict) or not catalogo.get("produtos"):
        raise ErroCatalogo("O catálogo simulado não contém produtos.")

    if not isinstance(rotas, dict) or not rotas.get("origem") or not rotas.get("destinos"):
        raise ErroCatalogo("Confira a origem e os destinos em rotas.json.")

    return catalogo, rotas