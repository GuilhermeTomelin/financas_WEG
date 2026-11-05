"""Contrato: 1 origem = taxa × destino. Direta, inversa e identidade; sem cruzamento."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, localcontext
from calculos.monetario import ErroMonetario, decimal, moeda, faixa, multiplicar


def normalizar_cotacao(q):
    if not isinstance(q,dict):
        raise ErroMonetario('Cotação deve ser um objeto.')
    de,para=moeda(q.get('origem')),moeda(q.get('destino'))
    taxa=decimal(q.get('cotacao'),'Taxa de câmbio',positivo=True)
    if de==para and taxa!=1:
        raise ErroMonetario('Conversão na mesma moeda exige taxa 1.')
    data=q.get('data_referencia')
    if data is not None:
        try:
            date.fromisoformat(data)
        except (TypeError,ValueError) as erro:
            raise ErroMonetario('Data de referência da cotação inválida.') from erro
    instante=q.get('consultado_em')
    if instante is not None:
        try:
            if datetime.fromisoformat(instante).tzinfo is None:
                raise ValueError('fuso ausente')
        except (TypeError,ValueError) as erro:
            raise ErroMonetario('Momento da consulta deve ser ISO com fuso.') from erro
    fonte=q.get('fonte') or q.get('provedor') or 'Origem não informada (legado)'
    metodo=q.get('metodo') or ('identidade' if de==para else 'direta')
    if metodo not in ('direta','inversa','identidade','manual'):
        raise ErroMonetario('Método de conversão não suportado.')
    return dict(deepcopy(q),origem=de,destino=para,cotacao=taxa,data_referencia=data,
                consultado_em=instante,fonte=fonte,provedor=q.get('provedor') or fonte,metodo=metodo,
                metadados_ausentes=sorted(set(q.get('metadados_ausentes',[])) | {k for k in ('consultado_em','provedor','metodo') if not q.get(k)}))


class ConjuntoCotacoes:
    def __init__(self,cotacoes=()):
        self.taxas={}
        self.usadas={}
        self.faltantes=set()
        self.problemas=[]
        for entrada in cotacoes:
            q=normalizar_cotacao(entrada)
            chave=(q['origem'],q['destino'])
            anterior=self.taxas.get(chave)
            if anterior and (anterior['cotacao'],anterior['data_referencia'])!=(q['cotacao'],q['data_referencia']):
                raise ErroMonetario('Cotações conflitantes para o mesmo par no conjunto.')
            self.taxas[chave]=q
        datas={q['data_referencia'] for q in self.taxas.values() if q['origem']!=q['destino'] and q['data_referencia'] is not None}
        self.coerente=len(datas)<=1
        if not self.coerente:
            self.problemas.append('Datas de câmbio incompatíveis no conjunto; atualize todas as taxas da simulação. Não foram misturadas datas nos totais.')
        self.data_referencia=next(iter(datas)) if len(datas)==1 else None

    def resolver(self,de,para):
        moeda(de);moeda(para)
        if de==para:
            q=dict(origem=de,destino=para,cotacao=Decimal(1),data_referencia=None,
                   consultado_em=None,provedor='Local',fonte='Identidade da mesma moeda',metodo='identidade',metadados_ausentes=[])
        elif not self.coerente:
            self.faltantes.add((de,para))
            return None
        else:
            q=self.taxas.get((de,para))
            if q is None:
                inversa=self.taxas.get((para,de))
                if inversa:
                    with localcontext() as ctx:
                        ctx.prec=50
                        taxa=Decimal(1)/inversa['cotacao']
                    q=dict(inversa,origem=de,destino=para,cotacao=taxa,metodo='inversa',componentes=[deepcopy(inversa)])
            if q is None or (q['data_referencia'] is None and q['metodo']!='manual'):
                self.faltantes.add((de,para))
                return None
        self.usadas[(de,para)]=deepcopy(q)
        return deepcopy(q)

    def converter(self,valor,de,para):
        q=self.resolver(de,para)
        if q is None:
            return None
        return multiplicar(faixa(valor),q['cotacao'])
