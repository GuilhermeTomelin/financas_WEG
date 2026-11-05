"""Frankfurter v2: consulta isolada e atualização explícita de um lote coerente."""
from datetime import date, datetime, timezone
from copy import deepcopy
from decimal import Decimal
import requests
from calculos.cambio import normalizar_cotacao, ConjuntoCotacoes
from calculos.monetario import decimal

URL_COTACAO="https://api.frankfurter.dev/v2/rate"
MOEDAS_SUPORTADAS=("BRL","EUR","USD","MXN","CLP","ZAR")
TIMEOUT_SEGUNDOS=10


class ErroCambio(Exception):
    pass


def consultar_cotacao(moeda_origem,moeda_destino,data_referencia=None):
    origem=str(moeda_origem).strip().upper()
    destino=str(moeda_destino).strip().upper()
    for m in (origem,destino):
        if m not in MOEDAS_SUPORTADAS:
            raise ErroCambio(f"Moeda não suportada: {m}. Opções: {', '.join(MOEDAS_SUPORTADAS)}.")
    if data_referencia is not None:
        try:
            date.fromisoformat(data_referencia)
        except (TypeError,ValueError) as erro:
            raise ErroCambio('Data solicitada inválida.') from erro
    if origem==destino:
        return dict(origem=origem,destino=destino,cotacao=1.0,data_referencia=None,consultado_em=None,
                    provedor='Local',fonte='Identidade da mesma moeda',metodo='identidade')
    try:
        kwargs=dict(timeout=TIMEOUT_SEGUNDOS)
        if data_referencia:
            kwargs['params']={'date':data_referencia}
        resposta=requests.get(f"{URL_COTACAO}/{origem}/{destino}",**kwargs)
        resposta.raise_for_status()
        dados=resposta.json(parse_float=Decimal)
        if not isinstance(dados,dict) or dados.get('base','').upper()!=origem or dados.get('quote','').upper()!=destino or isinstance(dados.get('rate'),bool):
            raise ValueError('Direção ou resposta inválida.')
        taxa=decimal(dados['rate'],'Taxa',positivo=True)
        referencia=dados['date']
        date.fromisoformat(referencia)
        return dict(origem=origem,destino=destino,cotacao=str(taxa),data_referencia=referencia,
                    consultado_em=datetime.now(timezone.utc).isoformat(),provedor='Frankfurter v2 (taxa de referência agregada)',
                    fonte='Frankfurter',metodo='direta',data_solicitada=data_referencia)
    except requests.exceptions.RequestException as erro:
        raise ErroCambio(f'Falha na consulta Frankfurter: {erro}') from erro
    except (ValueError,KeyError,TypeError,AttributeError) as erro:
        raise ErroCambio('Resposta Frankfurter inválida: taxa, direção ou data ausentes/inválidas.') from erro


def atualizar_cotacoes(calcular,consultar=None):
    """Um clique = um novo conjunto; primeiro par ancora a data dos demais.

    calcular recebe a lista do lote e devolve pares_faltantes. Não há cache de
    rede implícito nem reaproveitamento silencioso de taxa após uma falha.
    """
    consultar=consultar or consultar_cotacao
    cache={}
    erros=[]
    tentados=set()
    resultado=calcular([])
    data=None
    while True:
        pares={tuple(p) for p in resultado['pares_faltantes']}-tentados
        if not pares:
            break
        for de,para in sorted(pares):
            tentados.add((de,para))
            if ConjuntoCotacoes(cache.values()).resolver(de,para) is not None:
                continue
            try:
                bruto=consultar(de,para,data_referencia=data) if data else consultar(de,para)
                q=normalizar_cotacao(dict(bruto,fonte=bruto.get('fonte','Frankfurter')))
                if (q['origem'],q['destino'])!=(de,para):
                    raise ValueError('Resposta com direção diferente da consulta.')
                if data and q['data_referencia']!=data:
                    raise ValueError(f"Data retornada {q['data_referencia']} difere do lote {data}.")
                data=data or q['data_referencia']
                chave=f"{q['provedor']}|{de}|{para}|{q['data_referencia']}"
                cache[chave]=q
            except (ErroCambio,ValueError) as erro:
                erros.append(f'{de} → {para}: {erro}')
        resultado=calcular(list(cache.values()))
    return cache,resultado,erros


def obter_cache_sessao(estado):
    """Migra taxas antigas uma única vez; nunca ressuscita cache após falha."""
    if 'cotacoes_sessao' not in estado:
        cache=deepcopy(estado.get('frete_cotacoes',{}))
        legada=estado.get('cambio_simulador')
        if isinstance(legada,dict) and legada.get('origem')!=legada.get('destino'):
            q=normalizar_cotacao(legada)
            if not any((v.get('origem'),v.get('destino'))==(q['origem'],q['destino']) for v in cache.values()):
                cache[f"legado|{q['origem']}|{q['destino']}|{q['data_referencia']}"]=q
        estado['cotacoes_sessao']=cache
    return estado['cotacoes_sessao']
