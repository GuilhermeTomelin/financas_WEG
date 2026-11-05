"""Despesas logísticas selecionadas. Sem rede, impostos ou responsabilidades contratuais."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import re

from calculos.conteineres import calcular_conteineres

D=Decimal
CAMPOS=("minimo","maximo","referencia_superior")
ESTADOS=("conhecido","desconhecido","nao_aplicavel","incluido","excluido")
BASES=("operacao","conteiner","produto","percentual")
CATEGORIAS=("terrestre_origem","origem","documentacao","maritimo","seguro","destino","terrestre_destino","outras")


class ErroDespesas(ValueError):
    pass


def decimal(valor, campo, positivo=False):
    if isinstance(valor,bool) or not isinstance(valor,(str,int,float,Decimal)):
        raise ErroDespesas(f"{campo}: informe número {'positivo' if positivo else 'não negativo'}.")
    try:
        n=D(str(valor))
    except InvalidOperation as erro:
        raise ErroDespesas(f"{campo}: número inválido.") from erro
    if not n.is_finite() or (n <= 0 if positivo else n < 0):
        raise ErroDespesas(f"{campo}: número finito {'positivo' if positivo else 'não negativo'} necessário.")
    return n


def moeda(codigo):
    if not isinstance(codigo,str) or not re.fullmatch(r"[A-Z]{3}",codigo):
        raise ErroDespesas("Moeda deve ser um código de três letras maiúsculas.")
    return codigo


def faixa(valor):
    if isinstance(valor,dict):
        minimo=decimal(valor.get("minimo"),"Mínimo monetário")
        maximo=decimal(valor["maximo"],"Máximo monetário") if valor.get("maximo") is not None else None
        ref=decimal(valor["referencia_superior"],"Referência superior") if valor.get("referencia_superior") is not None else None
        if (maximo is not None and maximo < minimo) or (ref is not None and ref < minimo):
            raise ErroDespesas("Faixa monetária ou referência superior invertida.")
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


def arredondar(f):
    return {k:v.quantize(D('.01'),rounding=ROUND_HALF_UP) if v is not None else None for k,v in f.items()}


def validar_despesas(despesas):
    if not isinstance(despesas,list):
        raise ErroDespesas("Informe uma lista de despesas.")
    por_id={}
    for d in despesas:
        if not isinstance(d,dict) or not isinstance(d.get("id"),str) or not d["id"] or d["id"]=='mercadoria' or d["id"] in por_id:
            raise ErroDespesas("Identificador de despesa ausente, reservado ou duplicado.")
        if not isinstance(d.get("nome"),str) or not d["nome"].strip():
            raise ErroDespesas("Toda despesa precisa de nome.")
        if d.get("estado") not in ESTADOS or d.get("base") not in BASES or d.get("categoria") not in CATEGORIAS:
            raise ErroDespesas(f"{d['nome']}: estado, categoria ou base de cobrança inválidos.")
        if type(d.get("participa_total")) is not bool:
            raise ErroDespesas(f"{d['nome']}: confirme participação no total.")
        if not isinstance(d.get("natureza"),str) or not d["natureza"]:
            raise ErroDespesas(f"{d['nome']}: origem do dado ausente.")
        moeda(d.get("moeda"))
        if d["estado"]=='conhecido':
            if d["base"]=='percentual':
                decimal(d.get("valor"),d['nome'])
            else:
                faixa(d.get("valor"))
        if d["id"]=='frete_maritimo' and (d["base"]!='conteiner' or d["categoria"]!='maritimo'):
            raise ErroDespesas("Frete marítimo FCL exige cobrança por contêiner.")
        componentes=d.get("componentes_base",[])
        if not isinstance(componentes,list) or any(not isinstance(c,str) for c in componentes) or len(set(componentes))!=len(componentes):
            raise ErroDespesas(f"{d['nome']}: componentes da base inválidos ou duplicados.")
        por_id[d["id"]]=d
    for d in despesas:
        deps=[d.get("incluido_em")] if d["estado"]=='incluido' else (d.get("componentes_base",[]) if d['base']=='percentual' else [])
        for dep in deps:
            if dep==d["id"] or (dep not in por_id and (dep!='mercadoria' or d['estado']=='incluido')) or dep is None:
                raise ErroDespesas(f"{d['nome']}: referência de inclusão/base ausente, desconhecida ou circular.")
    visitados=set()
    def visitar(id_,caminho):
        if id_ in caminho:
            raise ErroDespesas("Dependência circular entre despesas e/ou bases percentuais.")
        if id_ in visitados:
            return
        d=por_id[id_]
        deps=[d['incluido_em']] if d['estado']=='incluido' else (d.get('componentes_base',[]) if d['base']=='percentual' else [])
        for dep in deps:
            if dep!='mercadoria':
                visitar(dep,caminho|{id_})
        visitados.add(id_)
    for id_ in por_id:
        visitar(id_,set())
    return por_id


def assinatura_contexto(produto_id,variante,quantidade,origem,destino,conteiner_id,moeda_apresentacao):
    dados=[produto_id,variante,quantidade,origem,destino,conteiner_id,moeda_apresentacao]
    return hashlib.sha256(json.dumps(dados,ensure_ascii=False,sort_keys=True,default=str).encode('utf-8')).hexdigest()


def serializar(valor):
    """JSON sem perdas de centavos: valores Decimal viram strings decimais."""
    return json.loads(json.dumps(valor,ensure_ascii=False,default=lambda v:str(v) if isinstance(v,Decimal) else _erro_json(v),allow_nan=False))


def _erro_json(valor):
    raise TypeError(f"Tipo não serializável: {type(valor).__name__}")


def calcular_logistica(variante,quantidade,conteiner,origem,destino,moeda_apresentacao,despesas,
                       declaracao=None,cotacoes=(),quantidade_manual=None,tarifa=None,locais=None):
    for codigo in (origem,destino):
        if not isinstance(codigo,str) or not re.fullmatch(r"[A-Z]{2}[A-Z2-9]{3}",codigo):
            raise ErroDespesas("Portos devem usar identificadores UN/LOCODE completos.")
    moeda(moeda_apresentacao)
    if tarifa and (tarifa.get('origem_unlocode'),tarifa.get('destino_unlocode'),tarifa.get('conteiner_id')) != (origem,destino,conteiner['id']):
        raise ErroDespesas("Tarifa incompatível com a direção, portos ou tipo de contêiner selecionado.")
    despesas=deepcopy(despesas)
    por_id=validar_despesas(despesas)
    if tarifa:
        for id_ in tarifa.get('despesas_incluidas',[]):
            d=por_id.get(id_)
            if d and d['participa_total'] and d['estado'] not in ('incluido','excluido','nao_aplicavel'):
                raise ErroDespesas(f"{d['nome']} está declarada incluída na tarifa. Use o estado Incluída ou remova explicitamente a inclusão da tarifa para cobrá-la à parte.")
    capacidade=calcular_conteineres(variante,quantidade,conteiner,quantidade_manual)
    n=capacidade['quantidade_avaliada'] if capacidade['compativel'] else None
    pendencias=[]
    if not capacidade['compativel']:
        pendencias.extend(capacidade['motivos'])
    elif not capacidade['atende']:
        pendencias.append(f"Quantidade de contêineres insuficiente: {capacidade['unidades_nao_atendidas']} unidades de embarque não atendidas. Não representa transporte completo do lote.")
    taxas={}
    for q in cotacoes:
        origem_q,destino_q=moeda(q.get('origem')),moeda(q.get('destino'))
        taxa=decimal(q.get('cotacao'),'Cotação',positivo=True)
        if not q.get('fonte'):
            raise ErroDespesas("Fonte da cotação ausente.")
        if q.get('data_referencia') is not None:
            try:
                date.fromisoformat(q['data_referencia'])
            except (TypeError,ValueError) as erro:
                raise ErroDespesas("Data da cotação inválida.") from erro
        taxas[(origem_q,destino_q)]=dict(q,cotacao=taxa)
    usadas={}
    faltantes=set()
    def converter(f,de,para):
        if de==para:
            usadas[(de,para)]=dict(origem=de,destino=para,cotacao=D(1),fonte='Identidade da mesma moeda',data_referencia=None)
            return f
        q=taxas.get((de,para))
        if q is None:
            faltantes.add((de,para))
            return None
        usadas[(de,para)]=q
        return multiplicar(f,q['cotacao'])
    calculados={}
    def calcular_item(id_):
        if id_ in calculados:
            return calculados[id_]
        d=por_id[id_]
        item=dict(d,total_original=None,total_convertido=None,base_calculada=None,pendencias=[])
        calculados[id_]=item
        if not d['participa_total'] or d['estado'] in ('excluido','nao_aplicavel'):
            return item
        if d['estado']=='incluido':
            pai=calcular_item(d['incluido_em'])
            item['cobertura_confirmada']=pai.get('cobertura_confirmada',False) if pai['estado']=='incluido' else pai['total_original'] is not None
            if not item['cobertura_confirmada']:
                item['pendencias'].append(f"{d['nome']}: item que a inclui não tem valor disponível no escopo.")
            return item
        if d['estado']=='desconhecido':
            item['pendencias'].append(f"{d['nome']}: valor aplicável desconhecido.")
            return item
        if d['categoria'] in ('terrestre_origem','terrestre_destino') and not (locais or {}).get(d['categoria'],'').strip():
            item['pendencias'].append(f"{d['nome']}: informe local de coleta/entrega; porto ou país não definem transporte terrestre.")
            return item
        if d['base']=='percentual':
            bases=[]
            componentes=d.get('componentes_base',[])
            if not componentes:
                item['pendencias'].append(f"{d['nome']}: escolha explicitamente os componentes da base percentual.")
            for componente in componentes:
                if componente=='mercadoria':
                    if not declaracao or declaracao.get('valor') is None or not declaracao.get('origem_escolha'):
                        item['pendencias'].append(f"{d['nome']}: valor declarado da mercadoria não informado/escolhido explicitamente.")
                        continue
                    f=faixa(declaracao['valor'])
                    de=moeda(declaracao.get('moeda'))
                else:
                    dependencia=calcular_item(componente)
                    f=dependencia['total_original']
                    de=dependencia['moeda']
                    if f is None:
                        item['pendencias'].append(f"{d['nome']}: componente {dependencia['nome']} indisponível ou fora do escopo.")
                        continue
                convertido=converter(f,de,d['moeda'])
                if convertido is None:
                    item['pendencias'].append(f"{d['nome']}: falta cotação {de} → {d['moeda']} para sua base.")
                else:
                    bases.append(convertido)
            if item['pendencias']:
                return item
            item['base_calculada']=somar(bases)
            total=multiplicar(item['base_calculada'],decimal(d['valor'],d['nome'])/100)
        else:
            if d['base']=='conteiner' and n is None:
                item['pendencias'].append(f"{d['nome']}: quantidade de contêineres não disponível para carga incompatível.")
                return item
            fator={'operacao':1,'conteiner':n,'produto':quantidade}[d['base']]
            total=multiplicar(faixa(d['valor']),D(fator))
        item['total_original']=arredondar(total)
        convertido=converter(item['total_original'],d['moeda'],moeda_apresentacao)
        if convertido is not None:
            item['total_convertido']=arredondar(convertido)
        else:
            item['pendencias'].append(f"{d['nome']}: falta cotação {d['moeda']} → {moeda_apresentacao}.")
        return item
    for id_ in por_id:
        calcular_item(id_)
    itens=[calculados[d['id']] for d in despesas]
    for item in itens:
        pendencias.extend(item['pendencias'])
    subtotais={}
    categorias={}
    convertidas=[]
    conversao_incompleta=False
    for item in itens:
        if item['total_original'] is None:
            continue
        subtotais.setdefault(item['moeda'],[]).append(item['total_original'])
        categorias.setdefault(item['categoria'],{}).setdefault(item['moeda'],[]).append(item['total_original'])
        if item['total_convertido'] is not None:
            convertidas.append(item['total_convertido'])
        else:
            conversao_incompleta=True
    conhecido=None if conversao_incompleta or (not convertidas and pendencias) else arredondar(somar(convertidas))
    pendencias=list(dict.fromkeys(pendencias))
    completo=not pendencias
    return dict(estado='completo' if completo else 'parcial',pendencias=pendencias,moeda_apresentacao=moeda_apresentacao,
                capacidade=capacidade,quantidade_conteineres=n,origem_quantidade='manual' if quantidade_manual is not None else 'estimada pela calculadora',
                frete_maritimo=calculados.get('frete_maritimo'),despesas=itens,
                subtotais_por_moeda={m:arredondar(somar(fs)) for m,fs in subtotais.items()},
                por_categoria={c:{m:arredondar(somar(fs)) for m,fs in moedas.items()} for c,moedas in categorias.items()},
                total_logistico_conhecido=conhecido,total_consolidado=conhecido if completo else None,
                total_por_produto=arredondar(multiplicar(conhecido,D(1)/quantidade)) if conhecido is not None and capacidade['atende'] else None,
                cotacoes_usadas=list(usadas.values()),pares_faltantes=[list(p) for p in sorted(faltantes)],
                premissas=dict(declaracao=deepcopy(declaracao),locais=deepcopy(locais or {}),tarifa=deepcopy(tarifa),
                               arredondamento='ROUND_HALF_UP: duas casas por total de despesa na moeda original, por conversão e por custo unitário; somam-se as linhas arredondadas.',
                               escopo='Despesas selecionadas da simulação, sem definir responsabilidades contratuais, impostos ou custo completo ao cliente.'))


def cenario_compativel(cenario,produto_id,variante,quantidade,origem,destino,conteiner_id,moeda_apresentacao):
    if not isinstance(cenario,dict):
        return None
    esperado=assinatura_contexto(produto_id,variante,quantidade,origem,destino,conteiner_id,moeda_apresentacao)
    return deepcopy(cenario) if cenario.get('assinatura')==esperado else None
