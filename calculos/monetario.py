"""Valores/faixas e arredondamento compartilhados, sem rede ou Streamlit."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
D=Decimal

class ErroMonetario(ValueError):
    pass


def decimal(valor, campo, positivo=False):
    if isinstance(valor,bool) or not isinstance(valor,(str,int,float,Decimal)):
        raise ErroMonetario(f"{campo}: informe número {'positivo' if positivo else 'não negativo'}.")
    try:
        n=D(str(valor))
    except InvalidOperation as erro:
        raise ErroMonetario(f"{campo}: número inválido.") from erro
    if not n.is_finite() or (n <= 0 if positivo else n < 0):
        raise ErroMonetario(f"{campo}: número finito {'positivo' if positivo else 'não negativo'} necessário.")
    return n


def moeda(codigo):
    if not isinstance(codigo,str) or not re.fullmatch(r"[A-Z]{3}",codigo):
        raise ErroMonetario("Moeda deve ser um código de três letras maiúsculas.")
    return codigo


def faixa(valor):
    if isinstance(valor,dict):
        minimo=decimal(valor.get("minimo"),"Mínimo monetário")
        maximo=decimal(valor["maximo"],"Máximo monetário") if valor.get("maximo") is not None else None
        ref=decimal(valor["referencia_superior"],"Referência superior") if valor.get("referencia_superior") is not None else None
        if (maximo is not None and maximo < minimo) or (ref is not None and ref < minimo):
            raise ErroMonetario("Faixa monetária ou referência superior invertida.")
        return dict(minimo=minimo,maximo=maximo,referencia_superior=ref)
    v=decimal(valor,"Valor monetário")
    return dict(minimo=v,maximo=v,referencia_superior=None)


def multiplicar(f,fator):
    if fator==0:
        return faixa(0)
    return {k:v*fator if v is not None else None for k,v in f.items()}


def somar(faixas):
    faixas=list(faixas)
    if not faixas:
        return faixa(0)
    aberto=any(f["maximo"] is None for f in faixas)
    superiores=[f["maximo"] if f["maximo"] is not None else f.get("referencia_superior") for f in faixas]
    return dict(minimo=sum((f["minimo"] for f in faixas),D(0)),
                maximo=None if aberto else sum((f["maximo"] for f in faixas),D(0)),
                referencia_superior=sum(superiores,D(0)) if aberto and all(v is not None for v in superiores) else None)


CASAS_MOEDAS={'BRL':2,'USD':2,'EUR':2,'MXN':2,'CLP':0,'ZAR':2}


def arredondar(f,codigo=None):
    casas=CASAS_MOEDAS.get(codigo,2)
    passo=D(1).scaleb(-casas)
    return {k:decimal(v,'Valor').quantize(passo,rounding=ROUND_HALF_UP) if v is not None else None for k,v in f.items()}


