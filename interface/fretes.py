"""Simulação editável de logística, sem escrita nos cadastros originais."""
from copy import deepcopy
from uuid import uuid4
import streamlit as st

from consumo.catalogo import carregar_dados_simulador, ErroCatalogo
from consumo.portos import carregar_portos, nome_pais, buscar_portos, rotulo_porto, garantir_selecao, dados_localidade
from consumo.conteineres import carregar_conteineres
from consumo.fretes import carregar_fretes, buscar_tarifa, despesas_da_rota
from consumo.cambio import MOEDAS_SUPORTADAS, consultar_cotacao, ErroCambio, atualizar_cotacoes, obter_cache_sessao
from calculos.operacoes import calcular_subtotal_faixa
from calculos.fretes import calcular_logistica, assinatura_contexto, serializar
from interface.componentes import cabecalho, numero_br
from calculos.consolidacao import consolidar_operacao
from interface.conversao import exibir_consolidacao
from interface.resumo_logistico import exibir_resumo, ESTADOS, BASES


def limpar_editores():
    for chave in list(st.session_state):
        if chave.startswith('frete_item_'):
            del st.session_state[chave]


def editor(d,ids):
    prefixo='frete_item_'+d['id']+'_'
    with st.expander(d['nome'],expanded=d['id']=='frete_maritimo'):
        anterior=deepcopy(d)
        a,b=st.columns(2)
        garantir_selecao(st.session_state,prefixo+'estado',list(ESTADOS),d['estado'])
        st.session_state.setdefault(prefixo+'participa',d['participa_total'])
        d['estado']=a.selectbox('Estado',list(ESTADOS),format_func=ESTADOS.get,key=prefixo+'estado')
        d['participa_total']=b.checkbox('Participa do escopo selecionado',key=prefixo+'participa')
        a,b,c=st.columns(3)
        bases=['conteiner'] if d['id']=='frete_maritimo' else list(BASES)
        garantir_selecao(st.session_state,prefixo+'base',bases,d['base'])
        st.session_state.setdefault(prefixo+'moeda',d['moeda'])
        st.session_state.setdefault(prefixo+'valor',None if anterior.get('valor') is None else float(anterior['valor']))
        d['base']=a.selectbox('Base de cobrança',bases,format_func=BASES.get,key=prefixo+'base')
        d['moeda']=b.text_input('Moeda (código de três letras)',max_chars=3,key=prefixo+'moeda').strip().upper()
        d['valor']=c.number_input('Percentual (%)' if d['base']=='percentual' else 'Valor unitário',min_value=0.0,
            value=None,
            format='%.6f',key=prefixo+'valor',disabled=d['estado']!='conhecido')
        if d['estado']=='incluido':
            opcoes=[i for i in ids if i!=d['id']]
            garantir_selecao(st.session_state,prefixo+'incluido',opcoes,d.get('incluido_em'))
            d['incluido_em']=st.selectbox('Incluída em qual item?',opcoes,format_func=lambda i:ids[i],key=prefixo+'incluido')
        if d['base']=='percentual':
            opcoes=['mercadoria']+[i for i in ids if i!=d['id']]
            st.session_state.setdefault(prefixo+'componentes',[i for i in d.get('componentes_base',[]) if i in opcoes])
            d['componentes_base']=st.multiselect('Componentes explícitos da base (sem o próprio item ou impostos)',opcoes,
                format_func=lambda i:'Valor declarado da mercadoria' if i=='mercadoria' else ids[i],key=prefixo+'componentes')
        for campo in ('estado','participa_total','base','moeda','valor','incluido_em','componentes_base'):
            if d.get(campo)!=anterior.get(campo):
                # Comparar número por valor evita marcar 450 e 450.0 como distintos.
                d['natureza']='informado_manualmente'
        st.caption('Simulado' if d['natureza']=='simulado' else 'Informado manualmente' if d['natureza']=='informado_manualmente' else 'Não informado')
        if d.get('observacoes'):
            st.caption(d['observacoes'])
    return d


def selecionar_porto(base,config,iso,lado):
    texto=st.text_input('Buscar porto de '+lado+' por nome ou código',key='frete_busca_'+lado+'_'+iso)
    opcoes=buscar_portos(base,iso,texto,config['favoritos'])
    if not opcoes:
        st.info('Nenhum porto encontrado. Altere a busca.')
        st.stop()
    ids=[p['unlocode'] for p in opcoes]
    chave='frete_porto_'+lado
    garantir_selecao(st.session_state,chave,ids,config['paises'].get(iso,{}).get('porto_padrao'))
    return st.selectbox('Porto de '+lado,ids,format_func=lambda i:rotulo_porto(base['portos'][i]),key=chave)


def exibir():
    cabecalho('Fretes e rotas','Simule frete FCL e despesas selecionadas, mantendo fontes, moedas e pendências explícitas.','OPERAÇÕES')
    simulacao,consulta=st.tabs(['Simulação logística','Consulta de portos'])
    with consulta:
        from interface.painel import consultar_portos
        consultar_portos()
    with simulacao:
        exibir_simulacao()


def exibir_simulacao():
    # Remover a fotografia antes de qualquer possível interrupção ou erro de entrada.
    st.session_state.pop('logistica_ativa',None)
    try:
        catalogo,_=carregar_dados_simulador()
        base,config=carregar_portos()
        equipamentos={c['id']:c for c in carregar_conteineres()}
        tarifas=carregar_fretes()
    except ErroCatalogo as erro:
        st.error(str(erro))
        return
    produtos={p['id']:p for p in catalogo['produtos']}
    def importar_simulador():
        produto=st.session_state.get('entrada_produto')
        if not isinstance(produto,dict):
            return
        id_=produto['id']
        st.session_state['frete_produto']=id_
        v=st.session_state.get('variante_'+id_)
        if isinstance(v,dict):
            st.session_state['frete_variante_'+id_]=v['nome']
        st.session_state['frete_busca_origem_BR']=''
        destino_importado=st.session_state.get('entrada_destino_iso','IT')
        st.session_state['frete_busca_destino_'+destino_importado]=''
        for de,para in [('entrada_qtd','frete_quantidade'),('entrada_porto_origem','frete_porto_origem'),
                        ('entrada_destino_iso','frete_destino_iso'),('entrada_porto_destino','frete_porto_destino'),
                        ('entrada_moeda_apresentacao','frete_moeda'),('entrada_tipo_conteiner','frete_tipo')]:
            if de in st.session_state:
                st.session_state[para]=st.session_state[de]
    def importar_conteineres():
        id_=st.session_state.get('conteiner_produto')
        if id_ not in produtos:
            return
        st.session_state['frete_produto']=id_
        v=st.session_state.get('conteiner_variante_'+id_)
        if v:
            st.session_state['frete_variante_'+id_]=v
        for de,para in [('conteiner_quantidade','frete_quantidade'),('conteiner_tipo','frete_tipo'),('conteiner_manual','frete_manual')]:
            if de in st.session_state:
                st.session_state[para]=st.session_state[de]
        st.session_state['frete_modo']='Manual' if st.session_state.get('conteiner_modo')=='Avaliar quantidade informada' else 'Estimada'
    with st.container(border=True,key='card_frete_entradas'):
        st.subheader('Mercadoria e trajeto')
        a,b=st.columns(2)
        if isinstance(st.session_state.get('entrada_produto'),dict):
            a.button('Reaproveitar seleção do simulador',on_click=importar_simulador,key='importar_frete_simulador')
        if st.session_state.get('conteiner_produto'):
            b.button('Reaproveitar calculadora de contêineres',on_click=importar_conteineres,key='importar_frete_conteineres')
        a,b,c=st.columns(3)
        garantir_selecao(st.session_state,'frete_produto',list(produtos))
        id_=a.selectbox('Produto',list(produtos),format_func=lambda i:produtos[i]['nome'],key='frete_produto')
        variantes={v['nome']:v for v in produtos[id_]['variantes']}
        garantir_selecao(st.session_state,'frete_variante_'+id_,list(variantes))
        nome=b.selectbox('Variante',list(variantes),key='frete_variante_'+id_)
        quantidade=c.number_input('Quantidade de produtos',min_value=1,step=1,value=None if 'frete_quantidade' in st.session_state else 1,key='frete_quantidade')
        a,b=st.columns(2)
        with a:
            st.caption('País de origem: Brasil (BR)')
            origem=selecionar_porto(base,config,'BR','origem')
        with b:
            paises=[p for p in base['paises'] if p!='BR']
            garantir_selecao(st.session_state,'frete_destino_iso',paises,'IT')
            iso=st.selectbox('País de destino',paises,format_func=lambda i:nome_pais(base,config,i)+' · '+i,key='frete_destino_iso')
            destino=selecionar_porto(base,config,iso,'destino')
        a,b,c=st.columns(3)
        st.session_state.setdefault('frete_tipo',st.session_state.get('conteiner_tipo','dry20'))
        tipo=a.selectbox('Tipo de contêiner',list(equipamentos),format_func=lambda i:equipamentos[i]['nome'],key='frete_tipo')
        modo=b.selectbox('Quantidade de contêineres',['Estimada','Manual'],key='frete_modo')
        manual=None
        if modo=='Manual':
            manual=c.number_input('Contêineres informados',min_value=1,step=1,value=None if 'frete_manual' in st.session_state else 1,key='frete_manual')
            if manual is None:
                st.error('Informe uma quantidade inteira e positiva de contêineres no modo manual.')
                return
        apresentacao=st.selectbox('Moeda de apresentação',MOEDAS_SUPORTADAS,key='frete_moeda')
    variante=variantes[nome]
    tarifa=buscar_tarifa(tarifas,origem,destino,tipo)
    contexto_rota=(origem,destino,tipo)
    restaurar=st.button('Restaurar valores originais da rota',key='restaurar_frete')
    if st.session_state.get('frete_contexto_rota')!=contexto_rota or restaurar:
        limpar_editores()
        st.session_state['frete_contexto_rota']=contexto_rota
        st.session_state['frete_despesas']=despesas_da_rota(tarifas,tarifa)
        st.session_state['frete_inclusoes']=True
        st.session_state['frete_local_coleta']=''
        st.session_state['frete_local_entrega']=''
    if tarifa:
        st.badge('Tarifa original simulada · FCL por contêiner',color='violet')
        st.caption(f"{origem} → {destino} · {equipamentos[tipo]['nome']} · {tarifa['moeda']} {numero_br(tarifa['valor_unitario'])} por contêiner. {tarifa['referencia']} Validade: {tarifa['validade'] or 'Não aplicável ao exemplo didático'}.")
        inclusoes=st.checkbox('Manter as inclusões declaradas na tarifa original (documentação)',key='frete_inclusoes')
        if not inclusoes:
            tarifa=deepcopy(tarifa)
            tarifa.update(despesas_incluidas=[],natureza='informado_manualmente',observacoes=tarifa['observacoes']+' Inclusões originais removidas explicitamente pelo usuário.')
    else:
        st.info('Frete indisponível para esta rota e equipamento. Informe manualmente o frete marítimo; não há cotação automática.')
    itens=deepcopy(st.session_state['frete_despesas'])
    ids={d['id']:d['nome'] for d in itens}
    abas=st.tabs(['Origem','Frete marítimo','Seguro','Destino','Extras'])
    for indice,categorias in [(0,('terrestre_origem','origem','documentacao')),(1,('maritimo',)),(2,('seguro',)),(3,('destino','terrestre_destino'))]:
        with abas[indice]:
            if indice==0:
                st.text_input('Local de coleta (necessário para transporte terrestre)',key='frete_local_coleta')
            if indice==3:
                st.text_input('Local de entrega ao cliente (necessário para transporte terrestre)',key='frete_local_entrega')
            for i,d in enumerate(itens):
                if d['categoria'] in categorias:
                    itens[i]=editor(d,ids)
    with abas[4]:
        a,b=st.columns(2)
        extra_nome=a.text_input('Nome da nova despesa extra',key='frete_extra_nome')
        if b.button('Adicionar despesa extra',key='adicionar_extra',disabled=not extra_nome.strip()):
            itens.append(dict(id='extra_'+uuid4().hex[:12],nome=extra_nome.strip(),categoria='outras',base='operacao',valor=None,
                              moeda=apresentacao,natureza='informado_manualmente',estado='desconhecido',participa_total=True,
                              incluido_em=None,componentes_base=[],observacoes=''))
            st.session_state['frete_despesas']=itens
            st.rerun()
        for i,d in enumerate(itens):
            if d['categoria']=='outras':
                itens[i]=editor(d,ids)
                if st.button('Remover '+d['nome'],key='remover_'+d['id']):
                    removido=d['id']
                    itens=[x for x in itens if x['id']!=removido]
                    for x in itens:
                        x['componentes_base']=[v for v in x.get('componentes_base',[]) if v!=removido]
                        if x.get('incluido_em')==removido:
                            x.update(estado='desconhecido',incluido_em=None)
                    st.session_state['frete_despesas']=itens
                    limpar_editores()
                    st.rerun()
    st.session_state['frete_despesas']=itens
    with abas[2]:
        st.markdown('#### Valor declarado da mercadoria para bases percentuais')
        escolha=st.selectbox('Origem do valor declarado',['Não informado','Faixa de preço do catálogo (escolha explícita)','Valor declarado manualmente'],key='frete_declaracao')
        declaracao=None
        if escolha.startswith('Faixa'):
            if quantidade is not None:
                declaracao=dict(valor=calcular_subtotal_faixa(variante,quantidade),moeda=catalogo['moeda'],origem_escolha='Preço do catálogo escolhido explicitamente como valor declarado; não é custo de fabricação.')
        elif escolha.startswith('Valor declarado'):
            a,b,c=st.columns(3)
            minimo=a.number_input('Valor declarado mínimo',min_value=0.0,value=None,key='frete_declarado_minimo')
            maximo=b.number_input('Valor declarado máximo (vazio = faixa aberta)',min_value=0.0,value=None,key='frete_declarado_maximo')
            de=c.text_input('Moeda do valor declarado',value='BRL',max_chars=3,key='frete_declarado_moeda').strip().upper()
            if minimo is not None:
                declaracao=dict(valor=dict(minimo=minimo,maximo=maximo,referencia_superior=None),moeda=de,origem_escolha='Valor declarado informado explicitamente pelo usuário.')
        st.caption('Seguro fixo: escolha Por operação. Seguro percentual: escolha os componentes da base. O percentual simulado não é regra universal de contratação e o próprio seguro nunca pode integrar sua base.')
    locais=dict(terrestre_origem=st.session_state.get('frete_local_coleta',''),terrestre_destino=st.session_state.get('frete_local_entrega',''))
    cotacoes=obter_cache_sessao(st.session_state)
    entrada=dict(produto_id=id_,variante=deepcopy(variante),quantidade=quantidade,origem=origem,destino=destino,
                 conteiner=deepcopy(equipamentos[tipo]),moeda=apresentacao,despesas=deepcopy(itens),declaracao=declaracao,
                 quantidade_manual=manual,tarifa=deepcopy(tarifa),locais=locais)
    def calcular(taxas):
        return consolidar_operacao(variante,quantidade,catalogo['moeda'],apresentacao,taxas,logistica=entrada)
    try:
        consolidacao=calcular(list(cotacoes.values()))
    except ValueError as erro:
        st.error('Não foi possível calcular as despesas: '+str(erro))
        return
    if st.button('Consultar / atualizar câmbio desta simulação',key='consultar_cambio_frete'):
        with st.spinner('Consultando um conjunto coerente de referências Frankfurter…'):
            cotacoes,consolidacao,erros=atualizar_cotacoes(calcular,consultar_cotacao)
            st.session_state['cotacoes_sessao']=cotacoes
            for erro in erros:
                st.warning(erro)
    resultado=consolidacao['resultado_logistica']
    exibir_consolidacao(consolidacao)
    with st.container(border=True,key='card_frete_resultado'):
        st.subheader('Resumo logístico')
        exibir_resumo(resultado)
    entrada['cotacoes']=list(cotacoes.values())
    st.session_state['logistica_ativa']=dict(assinatura=assinatura_contexto(id_,variante,quantidade,origem,destino,tipo,apresentacao),
                                           entradas=serializar(entrada),resultado=serializar(resultado),consolidacao=serializar(consolidacao))
    def levar_ao_simulador():
        st.session_state['entrada_produto']=produtos[id_]
        st.session_state['variante_'+id_]=variante
        st.session_state['entrada_qtd']=quantidade
        st.session_state['entrada_origem_iso']='BR'
        st.session_state['entrada_porto_origem']=origem
        st.session_state['entrada_destino_iso']=destino[:2]
        st.session_state['entrada_porto_destino']=destino
        st.session_state['entrada_busca_origem_BR']=''
        st.session_state['entrada_busca_destino_'+destino[:2]]=''
        st.session_state['entrada_moeda_apresentacao']=apresentacao
        st.session_state['pais_moeda_atual']=destino[:2]
        st.session_state['entrada_tipo_conteiner']=tipo
    if st.button('Levar cenário ao simulador para salvar',on_click=levar_ao_simulador,key='levar_frete_simulador',type='primary'):
        st.switch_page('paginas/simulador.py')
    st.caption('Salvar simulação no simulador grava a fotografia logística compatível, incluindo entradas, tarifas, despesas, premissas, capacidade e cotações. Arquivos de tarifas nunca são sobrescritos.')
