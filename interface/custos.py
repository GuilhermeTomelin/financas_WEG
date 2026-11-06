"""Entradas de responsabilidade e apresentação da mesma consolidação salva."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
from html import escape
import streamlit as st
from calculos.consolidacao import componentes_custo,RESPONSAVEIS
from interface.conversao import texto_faixa
from interface.componentes import numero_br

RESP={'vendedor':'Vendedor/exportador','comprador':'Comprador','terceiro':'Terceiro','nao_definido':'Não definido'}
TRAT={'herdar':'Manter inclusão/estado da origem','separado':'Adicionado separadamente',
      'incluido_preco':'Incluído no preço comercial (comprador)',
      'incluido_outro':'Incluído em outra cobrança','incluido_base_vendedor':'Incluído no custo interno (vendedor)'}
COBERTURAS={'nao_informado':'Não confirmado','contemplado':'Contemplado no escopo informado','nao_aplicavel':'Não aplicável — premissa explícita'}

BASES={'valor_comercial':'Valor comercial da mercadoria','fabricacao':'Fabricação','compra':'Compra'}
ALCANCES={'porto_destino':'porto de destino','cliente':'local final do cliente'}
NATUREZAS={'simulado':'simulada','manual':'manual','informado_manualmente':'informada pelo usuário','nao_informado':'não informada',
    'exemplo_didatico':'exemplo didático','documentado':'documentada','real':'real informada na origem','revisao_pendente':'revisão pendente'}
CATEGORIAS={'base_inicial':'Base inicial','mercadorias':'Mercadoria','terrestre_origem':'Transporte na origem',
    'origem':'Despesas na origem','documentacao':'Documentação','maritimo':'Frete marítimo','seguro':'Seguro',
    'destino':'Despesas no destino','terrestre_destino':'Transporte no destino','outras':'Outras despesas','tributos':'Tributos'}
ESTADOS_CUSTO={'nao_somado':'Sem soma nesta perspectiva','base_inicial':'Base inicial','fora_escopo':'Fora do escopo',
    'incluido_na_base':'Incluído na base','incluido_em_outro':'Incluído em outra cobrança','responsabilidade_nao_definida':'Responsabilidade pendente',
    'adicionado':'Adicionado separadamente','pendente':'Valor/câmbio pendente','nao_aplicavel':'Não aplicável','isento':'Isenção fundamentada na origem','excluido':'Excluído na origem'}


def configurar_custos(consolidacao,tributacao,variante,contexto):
    # Um novo produto/variante/rota/equipamento exige confirmar as condições próprias.
    dados={k:v for k,v in contexto.items() if k!='quantidade'}
    token=hashlib.sha256(json.dumps(dados,sort_keys=True,default=str).encode()).hexdigest()[:12]
    p='custo_'+token+'_'
    with st.expander('Configurar perspectivas, responsabilidades e cobertura',expanded=False):
        st.caption('Atribuição econômica manual. Pagador inicial é registrado separadamente. Nenhum Incoterm distribui despesas automaticamente.')
        perspectiva=st.selectbox('Perspectiva do resumo',['comprador','vendedor'],format_func=RESP.get,key='custo_perspectiva')
        a,b,c=st.columns(3)
        incoterm=a.text_input('Incoterm informado (opcional)',key=p+'incoterm').strip().upper()
        versao=b.text_input('Versão das regras informada',key=p+'versao').strip()
        local_nomeado=c.text_input('Local/porto nomeado do contrato',key=p+'nomeado').strip()
        st.caption('Registro de condições particulares, sem sugestões documentadas ICC nesta versão. Transferência de risco não é usada para atribuir custos.')
        log=consolidacao.get('resultado_logistica') or {}
        locais=(log.get('premissas') or {}).get('locais') or {}
        a,b=st.columns(2)
        st.session_state.setdefault(p+'local_origem',locais.get('terrestre_origem',''))
        origem=a.text_input('Local de origem/coleta do escopo',key=p+'local_origem')
        st.session_state.setdefault(p+'local_final',locais.get('terrestre_destino',''))
        final=b.text_input('Local final de entrega (quando houver)',key=p+'local_final')
        a,b=st.columns(2)
        ate=a.selectbox('Destino até o qual consolidar',['porto_destino','cliente'],format_func=lambda x:'Porto de destino' if x=='porto_destino' else 'Local final do cliente',key=p+'ate')
        dia=b.date_input('Data da simulação de custos',value=None if 'custo_data' in st.session_state else date.today(),key='custo_data')
        st.caption('Porto de embarque: '+contexto['origem_unlocode']+' · Porto de destino: '+contexto['destino_unlocode'])
        trechos={}
        for trecho,nome in [('origem','Origem → porto de embarque'),('maritimo','Porto de embarque → porto de destino'),('destino','Porto de destino → cliente')]:
            a,b=st.columns(2)
            estado=a.selectbox('Cobertura: '+nome,list(COBERTURAS),format_func=COBERTURAS.get,key=p+'trecho_'+trecho)
            premissa=b.text_input('Premissa da cobertura: '+nome,key=p+'premissa_'+trecho)
            trechos[trecho]=dict(estado=estado,premissa=premissa)
        st.markdown('**Base interna exclusiva do vendedor**')
        modo=st.radio('Origem do custo de fabricação/compra',['catalogo','manual'],format_func=lambda x:'Custo de origem do catálogo' if x=='catalogo' else 'Entrada manual independente do preço comercial',key=p+'base_modo',horizontal=True)
        interno=deepcopy(variante.get('custo_origem') or {})
        if modo=='manual':
            a,b,c=st.columns(3)
            tipo=a.selectbox('Tipo da base interna',['fabricacao','compra'],format_func=lambda x:'Fabricação' if x=='fabricacao' else 'Compra',key=p+'base_tipo')
            minimo=b.number_input('Custo interno unitário mínimo',min_value=0.0,value=None,key=p+'base_minimo')
            definido=c.checkbox('Custo unitário definido (sem faixa)',key=p+'base_definido')
            maximo=minimo if definido else st.number_input('Custo interno unitário máximo (vazio = aberto)',min_value=0.0,value=None,key=p+'base_maximo')
            a,b=st.columns(2)
            st.session_state.setdefault(p+'base_moeda','BRL')
            codigo=a.text_input('Moeda do custo interno',max_chars=3,key=p+'base_moeda').strip().upper()
            fonte=b.text_input('Fonte/premissa independente do custo interno',key=p+'base_fonte')
            interno=dict(tipo=tipo,valor_unitario=dict(minimo=minimo,maximo=maximo,referencia_superior=None) if minimo is not None else None,
                moeda=codigo,fonte=fonte,natureza='informado_manualmente',data_referencia=dia.isoformat() if dia else None)
        else:
            interno['valor_unitario']=dict(minimo=interno['minimo'],maximo=interno.get('maximo'),referencia_superior=interno.get('referencia_superior')) if interno.get('minimo') is not None else None
            st.caption('Base interna do catálogo: '+texto_faixa(interno['valor_unitario'],interno.get('moeda') or 'BRL')+'. Ausência desse custo afeta apenas o vendedor.')
        st.markdown('**Tributos adicionais por perspectiva**')
        impostos={}
        for lado in ('comprador','vendedor'):
            a,b=st.columns(2)
            padrao='usar_cenario' if tributacao else 'nao_informado'
            opcoes=['nao_informado','usar_cenario','sem_adicionais']
            st.session_state.setdefault(p+'tributos_'+lado,padrao)
            estado=a.selectbox('Tributos — '+RESP[lado],opcoes,format_func=lambda x:{'nao_informado':'Não definido / pendente','usar_cenario':'Usar cenário tributário compatível','sem_adicionais':'Declaro ausência de tributos adicionais no escopo'}[x],key=p+'tributos_'+lado)
            premissa=b.text_input('Premissa tributária — '+RESP[lado],key=p+'tributos_premissa_'+lado)
            impostos[lado]=dict(estado=estado,premissa=premissa)
        st.caption('Ausência de adicionais é declaração manual do escopo, sem criar isenção ou validar regra legal. Créditos potenciais não são abatidos.')
        itens=componentes_custo(consolidacao,tributacao)
        nomes={i['id']:i['nome'] for i in itens}
        nomes['base_vendedor']='Base interna do vendedor'
        atribuicoes={}
        for i in itens:
            if i['id']=='mercadoria':continue
            k=p+'item_'+i['id']+'_'
            with st.expander(i['nome']+' · responsabilidade e inclusão'):
                st.caption('Origem: '+i['natureza']+' · estado '+i['estado']+' · '+texto_faixa(i['valor_original'],i['moeda']))
                a,b=st.columns(2)
                st.session_state.setdefault(k+'responsavel','nao_definido')
                st.session_state.setdefault(k+'pagador','nao_definido')
                responsavel=a.selectbox('Responsável econômico',RESPONSAVEIS,format_func=RESP.get,key=k+'responsavel')
                pagador=b.selectbox('Pagador inicial (não determina o custo)',RESPONSAVEIS,format_func=RESP.get,key=k+'pagador')
                tratamento=st.selectbox('Tratamento na consolidação',list(TRAT),format_func=TRAT.get,key=k+'tratamento')
                incluido=None
                if tratamento=='incluido_outro':
                    opcoes=[id_ for id_ in nomes if id_ not in (i['id'],'mercadoria','base_vendedor')]
                    if opcoes:incluido=st.selectbox('Cobrança que inclui este item',opcoes,format_func=nomes.get,key=k+'incluido')
                    else:st.info('Não há outra cobrança. Selecione outro tratamento.')
                justificativa=st.text_input('Condição particular/premissa do tratamento',key=k+'justificativa')
                atribuicoes[i['id']]=dict(responsavel=responsavel,pagador_inicial=pagador,tratamento=tratamento,incluido_em=incluido,justificativa=justificativa)
        obs=st.text_area('Demais responsabilidades e premissas',key=p+'observacoes')
    return dict(perspectiva=perspectiva,base_vendedor=interno,itens=atribuicoes,tributos=impostos,
        contrato=dict(incoterm=incoterm or None,versao=versao or None,local_nomeado=local_nomeado or None,atribuicao='manual',observacoes=obs),
        escopo=dict(local_origem=origem,porto_embarque=contexto['origem_unlocode'],porto_destino=contexto['destino_unlocode'],
            local_final_entrega=final,ate=ate,data_simulacao=dia.isoformat() if dia else None,trechos=trechos))


def percentual(f):
    if f is None:return 'Indisponível'
    return numero_br(Decimal(str(f['minimo'])))+'%'+(' · máximo desconhecido' if f['maximo'] is None else ' a '+numero_br(Decimal(str(f['maximo'])))+'%' if f['maximo']!=f['minimo'] else '')


def exibir_custos(resultado):
    st.subheader('Custo da operação por perspectiva')
    lado=resultado['perspectiva_selecionada']
    st.markdown('**'+('Custo de aquisição do comprador' if lado=='comprador' else 'Custo do vendedor/exportador')+'**')
    st.caption(resultado['cobertura']['rotulo']+' · Escopo solicitado: '+ALCANCES[resultado['cobertura']['solicitada']])
    st.caption('Completude dos dados é separada da natureza das fontes. Totais de comprador e vendedor são independentes; não representam preço de venda, lucro ou margem.')
    resumo,composicao,premissas=st.tabs(['Resumo','Composição dos custos','Responsabilidades e premissas'])
    perspectiva=resultado['perspectivas'][lado]
    with resumo:
        st.caption('Naturezas registradas: '+', '.join(NATUREZAS.get(n,n) for n in perspectiva['naturezas'])+'. Atribuições econômicas manuais, sem matriz automática de Incoterms.')
        cols=st.columns(len(perspectiva['por_moeda']))
        for col,(codigo,r) in zip(cols,perspectiva['por_moeda'].items()):
            with col.container(border=True,key='card_custo_'+codigo):
                st.markdown('**'+codigo+'**')
                st.badge('Dados completos para o escopo declarado' if r['estado_dados']=='completo' else 'Dados parciais',color='green' if r['estado_dados']=='completo' else 'orange')
                st.caption('Base utilizada: '+BASES.get(r['tipo_base'],'Não informada'))
                for campo,nome in [('base_inicial','Base inicial do lote'),('base_unitaria','Base inicial por produto'),
                    ('despesas_adicionais_conhecidas','Despesas adicionais conhecidas'),('tributos_conhecidos','Tributos adicionais conhecidos'),
                    ('subtotal_conhecido','Subtotal conhecido'),('total_estimado','Total estimado do escopo'),
                    ('total_unitario','Custo total por produto'),('acrescimo_absoluto','Acréscimo conhecido sobre a base')]:
                    st.html('<p><strong>'+nome+':</strong> '+escape(texto_faixa(r[campo],codigo))+'</p>')
                if r['estado_dados']=='parcial':st.caption('Conhecido por produto: '+texto_faixa(r['unitario_conhecido'],codigo)+'. Não representa custo completo.')
                st.write('Acréscimo sobre a base inicial: '+percentual(r['percentual_acrescimo']))
                st.caption('Denominador do acréscimo: '+texto_faixa(r['denominador_acrescimo'],codigo)+' · mesmo lote, perspectiva e moeda.')
                if r['motivo_percentual']:st.caption(r['motivo_percentual'])
                if r['pendencias']:
                    with st.expander('Pendências desta perspectiva em '+codigo):
                        for p in r['pendencias']:st.write('• '+p)
        st.caption('Divisor do custo unitário: '+str(resultado['quantidade_produtos'])+' produtos. Nenhum crédito tributário é abatido automaticamente.')
    with composicao:
        for codigo,r in perspectiva['por_moeda'].items():
            componentes={i['id']:i for i in resultado['componentes']}
            linhas=[]
            for item in r['linhas']:
                i=componentes[item['id']]
                linhas.append({'Item':i['nome'],'Categoria':CATEGORIAS.get(i['categoria'],i['categoria']),'Responsável econômico':RESP[i['responsavel']],
                    'Pagador inicial':RESP[i['pagador_inicial']],'Incluído em':i['incluido_em_efetivo'] or '—',
                    'Valor original':texto_faixa(i['valor_original'],i['moeda'] or codigo),
                    'Valor considerado ('+codigo+')':texto_faixa(item['valor_considerado'],codigo),
                    'Participação no total':percentual(item['participacao_no_total']),
                    'Fonte/estado':str(i.get('fonte') or 'Não informada')+' · '+i['natureza']+' · '+i['estado'],
                    'Tratamento':ESTADOS_CUSTO.get(item['estado'],item['estado']),'Explicação':item['motivo']})
            st.markdown('**Composição em '+codigo+'**')
            st.dataframe(linhas,hide_index=True,width='stretch')
            st.caption('Denominador da participação: total desta perspectiva em '+codigo+' · '+texto_faixa(r['denominador_participacao'],codigo)+'. Participações ficam indisponíveis para total variável, zero ou parcial.')
    with premissas:
        st.write(perspectiva['atribuicao'])
        st.caption('Ajustar inclusão/responsabilidade nesta consolidação não altera a fórmula tributária de origem. Confira as bases fiscais quando o contrato ou preço incluir componentes antes cobrados separadamente.')
        st.json(resultado['configuracao'])
        st.caption('Taxas e fontes preservadas na consolidação, sem nova consulta ao exibir:')
        st.json({'novas_conversoes':resultado['cotacoes_usadas'],'conversoes_monetarias':resultado['cotacoes_monetarias'],'tributacao':resultado['fonte_tributaria'],'fontes_logisticas':resultado.get('premissas_logisticas')})
        st.caption(resultado['premissas'])
