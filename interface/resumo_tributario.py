"""Apresentação de fotografias fiscais, sem recálculo de registros salvos."""
from decimal import Decimal
from html import escape
import streamlit as st
from interface.conversao import texto_faixa
from interface.componentes import numero_br

SITUACOES={'calculado':'Calculado','calculado_zero':'Alíquota/valor zero informado (não é isenção)',
 'nao_informado':'Não informado / pendente','nao_aplicavel':'Não aplicável','incluido':'Já incluído em outro item',
 'fora_escopo':'Fora do escopo selecionado','fora_vigencia':'Fora da vigência','nao_suportado':'Cenário/fórmula não suportado','isento':'Isento com fundamentação registrada'}


def exibir_resumo_tributario(snapshot,compacto=False):
    r=snapshot['resultado'] if 'resultado' in snapshot else snapshot
    st.subheader('Simulação tributária')
    st.warning(r['natureza_resultado'])
    st.caption('Escopo configurado; não representa cobertura tributária completa do país ou custo final garantido ao cliente. Nenhum crédito é descontado automaticamente.')
    for aviso in r['avisos']:
        st.caption(aviso)
    colunas=st.columns(len(r['por_moeda']))
    for coluna,(codigo,dados) in zip(colunas,r['por_moeda'].items()):
        with coluna.container(border=True,key='card_tributos_'+codigo):
            st.markdown('**'+codigo+'**')
            st.badge('Completo para o escopo configurado' if dados['estado']=='completo' else 'Resultado parcial',color='green' if dados['estado']=='completo' else 'orange')
            for campo,nome in [('total_tributario_conhecido','Tributos conhecidos'),('por_produto','Tributos conhecidos por produto'),
                               ('subtotal_mercadorias_logistica','Mercadorias + logística'),('subtotal_acrescido_tributos','Subtotal acrescido dos tributos calculados')]:
                st.html('<p><strong>'+nome+':</strong> '+escape(texto_faixa(dados[campo],codigo))+'</p>')
            percentual=dados['percentual_base_comercial']
            if percentual is not None:
                st.write('Percentual conhecido sobre a base comercial: '+numero_br(Decimal(str(percentual['minimo'])))+'%'+(' · máximo desconhecido' if percentual['maximo'] is None else ' a '+numero_br(Decimal(str(percentual['maximo'])))+'%' if percentual['maximo']!=percentual['minimo'] else ''))
            else:
                st.caption(dados['motivo_percentual'])
            st.caption('Denominador: preço comercial do lote · '+texto_faixa(dados['denominador'],codigo))
            st.caption('Cálculo dos tributos: '+dados['estado_tributos']+' para os itens configurados, mantendo a natureza manual/didática/documentada acima.')
            if dados['pendencias']:
                with st.expander('Pendências tributárias em '+codigo,expanded=not compacto):
                    for mensagem in dados['pendencias']:
                        st.write('• '+mensagem)
    with st.expander('Tributos individualizados e memória de cálculo',expanded=not compacto):
        st.dataframe([{'Tributo':x['nome'],'Versão':x['versao'],'Jurisdição':x['jurisdicao'],
                       'Estado':SITUACOES[x['estado_calculo']],'Base':texto_faixa(x['base_calculada'],x['moeda']),
                       'Alíquota':str(x['aliquota']).replace('.',',')+'%' if x.get('aliquota') is not None and x['tipo_calculo']=='percentual' else '—',
                       'Fórmula':x['formula'] or 'Indisponível','Resultado original':texto_faixa(x['valor_original'],x['moeda']),
                       'Natureza':x['estado_regra'],'Fonte':x.get('fonte') or 'Sem fonte legal — manual/didático',
                       'Revisão especialista':x.get('revisao_especialista','Não registrada')} for x in r['regras']],hide_index=True,width='stretch')
        st.caption('Base percentual formada somente pelos componentes configurados. Uma alíquota zero não comprova isenção.')
        st.json({'cenario':r['cenario'],'classificacao':r['classificacao'],'regras':r['regras']})
    with st.expander('Câmbio de referência e aduaneiro usados'):
        st.write('Apresentação e bases com câmbio de referência:')
        st.json(r['cotacoes_usadas'])
        st.write('Bases que exigem câmbio aduaneiro informado separadamente:')
        st.json(r['cotacoes_aduaneiras_usadas'])
        st.caption('Frankfurter é referência de simulação; não é assumida como taxa aduaneira de nenhuma jurisdição.')
