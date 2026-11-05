"""Especificações locais: não consulta fontes externas durante a simulação."""
import json
from pathlib import Path
from consumo.catalogo import ErroCatalogo
from calculos.conteineres import validar_conteiner

CAMINHO = Path(__file__).resolve().parents[1] / "dados" / "conteineres.json"


def carregar_conteineres():
    try:
        dados = json.loads(CAMINHO.read_text(encoding="utf-8"))["conteineres"]
        ids = set()
        if not isinstance(dados, list) or not dados:
            raise ValueError("Lista de equipamentos ausente.")
        for c in dados:
            validar_conteiner(c)
            if not c.get("id") or c["id"] in ids or not c.get("nome") or not c.get("fonte") or not c.get("url"):
                raise ValueError("Identificador, nome ou fonte ausente/duplicado.")
            ids.add(c["id"])
        return dados
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as erro:
        raise ErroCatalogo(f"Falha nas especificações dos contêineres: {erro}") from erro
