"""Apresentação compartilhada dos valores originais, taxas e duas moedas."""
from decimal import Decimal
from html import escape
import streamlit as st
from interface.componentes import numero_br
from interface.resumo_logistico import texto_faixa as _texto_faixa, ESTADOS
from calculos.monetario import CASAS_MOEDAS


def texto_faixa(f,codigo):
    return _texto_faixa(f,codigo,casas=CASAS_MOEDAS.get(codigo,2))


def exibir_consolidacao(resultado,compacto=False):
    st.subheader('Mercadorias e logística por moeda')
    st.caption(resultado['base_comercial']+' Valores logísticos são os itens selecionados; não é custo completo ao cliente.')
    colunas=st.columns(len(resultado['por_moeda']))
    for coluna,(codigo,r) in zip(colunas,resultado['por_moeda'].items()):
        with coluna.container(border=True,key='card_consolidacao_'+codigo):
            st.markdown('**'+codigo+'**')
            st.badge('Completo para o escopo selecionado' if r['estado']=='completo' else 'Parcial / pendente',color='green' if r['estado']=='completo' else 'orange')
            for chave,nome in (('mercadorias','Mercadorias'),('frete_maritimo','Frete marítimo'),('demais_despesas','Demais despesas logísticas'),('seguro','Seguro')):
                st.html('<p><strong>'+nome+':</strong> '+escape(texto_faixa(r['grupos'][chave],codigo))+'</p>')
            st.html('<p><strong>Subtotal de mercadorias + logística:</strong> '+escape(texto_faixa(r['subtotal_mercadorias_logistica'],codigo))+'</p>')
            if r['estado']=='parcial':
                st.caption('Soma conhecida parcial: '+texto_faixa(r['subtotal_conhecido'],codigo)+'. Não representa o total completo do escopo.')
                with st.expander('Pendências em '+codigo):
                    for p in r['pendencias']:
                        st.write('• '+p)
    destinos=list(resultado['por_moeda'])
    linhas=[]
    for item in resultado['itens']:
        ativo=item['participa_total'] and item['estado'] not in ('incluido','nao_aplicavel','excluido')
        estado=ESTADOS.get(item['estado'],item['estado']) if item['participa_total'] else 'Fora do escopo'
        linha={'Item':item['nome'],'Origem do dado':item['natureza'],'Estado':estado,
               'Valor original':texto_faixa(item['valor_original'],item['moeda']),'Moeda':item['moeda']}
        for destino in destinos:
            q=item['taxas'][destino]
            linha['Taxa → '+destino]=(f"1 {q['origem']} = {numero_br(Decimal(str(q['cotacao'])),8)} {q['destino']} ({q['metodo']})" if q else 'Não aplicada / pendente' if ativo else 'Sem cobrança separada')
            linha['Valor em '+destino]=texto_faixa(item['convertidos'][destino],destino) if ativo else estado
        linhas.append(linha)
    with st.expander('Detalhamento monetário · originais e conversões',expanded=not compacto):
        st.dataframe(linhas,hide_index=True,width='stretch')
    with st.expander('Conjunto de taxas · fontes, datas e métodos'):
        st.caption('Últimas referências disponíveis, não taxas executáveis de banco/corretora. Não se presume cotação de hoje. Nenhuma taxa é consultada ao renderizar esta seção.')
        for q in resultado['cotacoes_usadas']:
            st.write(f"1 {q['origem']} = {numero_br(Decimal(str(q['cotacao'])),8)} {q['destino']} · {q['metodo']} · {q['provedor']}")
            st.caption(f"Referência: {q.get('data_referencia') or 'Sem data / identidade ou manual'} · Consulta: {q.get('consultado_em') or 'Não registrada (local ou legado)'}")
            if q.get('metadados_ausentes'):
                st.caption('Metadados ausentes: '+', '.join(q['metadados_ausentes']))
            st.json(q)
        st.caption(resultado['politica'])
