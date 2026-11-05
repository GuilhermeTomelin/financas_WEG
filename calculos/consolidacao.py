"""Consolidação da mesma operação em BRL e na moeda selecionada, sem rede."""
from copy import deepcopy
from calculos.cambio import ConjuntoCotacoes
from calculos.monetario import faixa, somar, arredondar
from calculos.operacoes import calcular_subtotal_faixa
from calculos.fretes import calcular_logistica


def consolidar_operacao(variante,quantidade,moeda_catalogo,moeda_apresentacao,cotacoes=(),logistica=None):
    conjunto=ConjuntoCotacoes(cotacoes)
    destinos=list(dict.fromkeys(['BRL',moeda_apresentacao]))
    original=faixa(calcular_subtotal_faixa(variante,quantidade))
    mercadoria=dict(id='mercadoria',nome='Mercadorias · preço comercial do catálogo',categoria='mercadorias',
                    natureza='simulado',moeda=moeda_catalogo,valor_original=original,estado='conhecido',participa_total=True,
                    base_comercial='Preço comercial da variante; custo de fabricação/compra não é somado.')
    itens=[mercadoria]
    resultado_logistica=None
    pendencias_comuns=[]
    if logistica is not None:
        args=deepcopy(logistica)
        for chave in ('produto_id','moeda','cotacoes'):
            args.pop(chave,None)
        args.update(variante=variante,quantidade=quantidade,moeda_apresentacao=moeda_apresentacao,
                    cotacoes=cotacoes,conjunto=conjunto)
        resultado_logistica=calcular_logistica(**args)
        # Pendências de câmbio são avaliadas por destino abaixo; as demais são comuns.
        pendencias_comuns=[p for p in resultado_logistica['pendencias'] if 'falta cotação' not in p or 'para sua base' in p]
        for d in resultado_logistica['despesas']:
            itens.append(dict(id=d['id'],nome=d['nome'],categoria=d['categoria'],natureza=d['natureza'],
                              moeda=d['moeda'],valor_original=deepcopy(d['total_original']),estado=d['estado'],
                              participa_total=d['participa_total'],incluido_em=d.get('incluido_em'),
                              parametro_original=deepcopy(d.get('valor')),base_cobranca=d['base']))
    else:
        pendencias_comuns.append('Logística não configurada para estas entradas; subtotal de mercadorias + logística indisponível.')
    por_moeda={}
    for item in itens:
        item['convertidos']={}
        item['taxas']={}
        for destino in destinos:
            f=item['valor_original']
            convertido=conjunto.converter(f,item['moeda'],destino) if f is not None else None
            item['convertidos'][destino]=arredondar(convertido,destino) if convertido is not None else None
            item['taxas'][destino]=deepcopy(conjunto.usadas.get((item['moeda'],destino))) if f is not None else None
    for destino in destinos:
        pendencias=list(pendencias_comuns)
        grupos={k:[] for k in ('mercadorias','frete_maritimo','seguro','demais_despesas')}
        conhecidos=[]
        grupos_pendentes=set()
        subtotais_originais={}
        for item in itens:
            ativo=item['participa_total'] and item['estado'] not in ('incluido','nao_aplicavel','excluido')
            if not ativo:
                continue
            grupo='mercadorias' if item['id']=='mercadoria' else 'frete_maritimo' if item['id']=='frete_maritimo' else 'seguro' if item['categoria']=='seguro' else 'demais_despesas'
            f=item['convertidos'][destino]
            if item['valor_original'] is not None:
                subtotais_originais.setdefault(item['moeda'],[]).append(item['valor_original'])
            if f is None:
                grupos_pendentes.add(grupo)
                pendencias.append(f"{item['nome']}: valor ou conversão {item['moeda']} → {destino} pendente.")
            else:
                grupos[grupo].append(f)
                conhecidos.append(f)
        pendencias.extend(conjunto.problemas)
        pendencias=list(dict.fromkeys(pendencias))
        totais={g:(None if g in grupos_pendentes else arredondar(somar(fs),destino) if fs else (None if g=='mercadorias' or logistica is None else faixa(0))) for g,fs in grupos.items()}
        conhecido=arredondar(somar(conhecidos),destino) if conhecidos else None
        por_moeda[destino]=dict(estado='parcial' if pendencias else 'completo',pendencias=pendencias,
                               grupos=totais,subtotal_conhecido=conhecido,
                               subtotal_mercadorias_logistica=conhecido if not pendencias else None,
                               subtotais_originais={m:arredondar(somar(fs),m) for m,fs in subtotais_originais.items()})
    return dict(versao=1,moeda_apresentacao=moeda_apresentacao,base_comercial=mercadoria['base_comercial'],itens=itens,
                por_moeda=por_moeda,estado='completo' if all(r['estado']=='completo' for r in por_moeda.values()) else 'parcial',
                cotacoes_usadas=list(conjunto.usadas.values()),pares_faltantes=[list(p) for p in sorted(conjunto.faltantes)],
                data_referencia=conjunto.data_referencia,resultado_logistica=resultado_logistica,
                politica='ROUND_HALF_UP por item e moeda (CLP: 0 casas; demais: 2). Total = soma dos itens exibidos. Sem impostos, spreads ou tarifas bancárias automáticas.')
