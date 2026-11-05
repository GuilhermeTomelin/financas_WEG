"""Resumo reutilizado no simulador e no editor de despesas."""
from decimal import Decimal
from html import escape
import streamlit as st
from interface.componentes import numero_br

ESTADOS={'conhecido':'Valor conhecido','desconhecido':'Valor desconhecido (pendente)',
         'nao_aplicavel':'Não aplicável','incluido':'Incluída em outro item','excluido':'Excluída do escopo'}
BASES={'operacao':'Por operação','conteiner':'Por contêiner','produto':'Por produto','percentual':'Percentual'}

CATEGORIAS={'terrestre_origem':'Transporte terrestre na origem','origem':'Portuárias de origem',
            'documentacao':'Documentação','maritimo':'Frete marítimo','seguro':'Seguro',
            'destino':'Portuárias de destino','terrestre_destino':'Transporte terrestre no destino','outras':'Outras despesas'}
NATUREZAS={'simulado':'Simulado','informado_manualmente':'Informado manualmente','nao_informado':'Não informado'}


def total_item(item,convertido=False,codigo=None):
    if not item['participa_total'] or item['estado']=='excluido':
        return 'Fora do escopo'
    if item['estado']=='nao_aplicavel':
        return 'Não aplicável'
    if item['estado']=='incluido':
        return 'Incluída em outro item; sem cobrança duplicada'
    if item['estado']=='desconhecido':
        return 'Valor desconhecido'
    return texto_faixa(item['total_convertido'] if convertido else item['total_original'],codigo if convertido else item['moeda'])


def texto_faixa(f,codigo,casas=2):
    if f is None:
        return 'Indisponível'
    minimo=f"{codigo} {numero_br(Decimal(str(f['minimo'])),casas)}"
    if f['maximo'] is None:
        ref=f.get('referencia_superior')
        return f"A partir de {minimo}" + (f" · referência superior {codigo} {numero_br(Decimal(str(ref)),casas)} (não é teto)" if ref is not None else '')
    if Decimal(str(f['minimo']))==Decimal(str(f['maximo'])):
        return minimo
    return minimo+f" a {codigo} {numero_br(Decimal(str(f['maximo'])),casas)}"


def exibir_resumo(resultado,compacto=False):
    codigo=resultado['moeda_apresentacao']
    st.badge('Completo para o escopo selecionado' if resultado['estado']=='completo' else 'Resultado parcial',color='green' if resultado['estado']=='completo' else 'orange')
    st.caption('Despesas selecionadas, sem definir responsabilidades contratuais. Não inclui impostos nem constitui custo completo ao cliente.')
    st.html('<p><strong>Total logístico conhecido:</strong> '+escape(texto_faixa(resultado['total_logistico_conhecido'],codigo))+'</p>')
    st.html('<p><strong>Logística conhecida por produto:</strong> '+escape(texto_faixa(resultado['total_por_produto'],codigo))+'</p>')
    if resultado['total_consolidado'] is None:
        st.caption('Total consolidado do escopo indisponível até resolver as pendências; o valor conhecido, quando exibido, é parcial.')
    frete=resultado.get('frete_maritimo')
    if frete:
        st.html('<p><strong>Frete marítimo total:</strong> '+escape(texto_faixa(frete['total_original'],frete['moeda']))+'</p>')
    st.caption(f"Contêineres: {resultado['quantidade_conteineres'] if resultado['quantidade_conteineres'] is not None else 'indisponível'} · quantidade {resultado['origem_quantidade']}.")
    if resultado['pendencias']:
        with st.expander('Pendências do cenário',expanded=not compacto):
            for p in resultado['pendencias']:
                st.write('• '+p)
    if compacto:
        return
    st.subheader('Subtotais conhecidos por moeda original')
    for m,f in resultado['subtotais_por_moeda'].items():
        st.text(texto_faixa(f,m))
    st.subheader('Detalhamento das despesas')
    st.dataframe([{'Despesa':d['nome'],'Categoria':CATEGORIAS[d['categoria']],'Estado':ESTADOS[d['estado']],
                   'Participa do escopo':'Sim' if d['participa_total'] else 'Não','Base':BASES[d['base']],
                   'Origem':NATUREZAS.get(d['natureza'],d['natureza']),'Incluída em':d.get('incluido_em') or '—',
                   'Base percentual':texto_faixa(d.get('base_calculada'),d['moeda']) if d['base']=='percentual' else '—',
                   'Percentual':numero_br(Decimal(str(d['valor'])),4).rstrip('0').rstrip(',')+'%' if d['base']=='percentual' and d.get('valor') is not None else '—',
                   'Total original':total_item(d),
                   'Total convertido':total_item(d,True,codigo)} for d in resultado['despesas']],hide_index=True,width='stretch')
    st.subheader('Demais despesas por categoria e moeda')
    st.dataframe([{'Categoria':CATEGORIAS[c],'Moeda':m,'Total conhecido':texto_faixa(f,m)}
                   for c,moedas in resultado['por_categoria'].items() if c!='maritimo' for m,f in moedas.items()],hide_index=True,width='stretch')
    with st.expander('Taxas, fontes e datas usadas'):
        if not resultado['cotacoes_usadas']:
            st.caption('Nenhuma conversão monetária realizada.')
        for q in resultado['cotacoes_usadas']:
            st.write(f"1 {q['origem']} = {numero_br(Decimal(str(q['cotacao'])),6)} {q['destino']} · {q['fonte']} · referência {q.get('data_referencia') or 'Não informada / identidade local'}")
