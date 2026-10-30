import math

import requests

URL_COTACAO = "https://api.frankfurter.dev/v2/rate"
MOEDAS_SUPORTADAS = ("USD", "EUR", "BRL")
TIMEOUT_SEGUNDOS = 10


class ErroCambio(Exception):
    """Erro ao consultar a cotação de câmbio."""


def consultar_cotacao(moeda_origem, moeda_destino):
    origem = str(moeda_origem).strip().upper()
    destino = str(moeda_destino).strip().upper()

    for moeda in (origem, destino):
        if moeda not in MOEDAS_SUPORTADAS:
            raise ErroCambio(f"Moeda não suportada: {moeda}. Use USD, EUR ou BRL.")

    if origem == destino:
        return {
            "origem": origem,
            "destino": destino,
            "cotacao": 1.0,
            "data_referencia": None,
        }

    url = f"{URL_COTACAO}/{origem}/{destino}"

    try:
        resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
        resposta.raise_for_status()
        dados = resposta.json()
        cotacao = float(dados["rate"])
        data_referencia = str(dados["date"])
    except requests.exceptions.HTTPError as erro:
        raise ErroCambio(f"A API respondeu com erro HTTP: {erro}") from erro
    except (ValueError, KeyError, TypeError) as erro:
        raise ErroCambio("A API devolveu dados em formato inesperado.") from erro
    except requests.exceptions.RequestException as erro:
        raise ErroCambio(f"Falha de conexão com a API: {erro}") from erro

    if not math.isfinite(cotacao) or cotacao <= 0:
        raise ErroCambio("A API devolveu uma cotação inválida.")

    return {
        "origem": origem,
        "destino": destino,
        "cotacao": cotacao,
        "data_referencia": data_referencia,
    }