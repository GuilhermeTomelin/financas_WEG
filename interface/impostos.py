"""Página fiscal: entrada manual e exercícios, sem API de tributos."""
from copy import deepcopy
from datetime import date,datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
import streamlit as st

from consumo.catalogo import carregar_dados_simulador,ErroCatalogo
from consumo.portos import carregar_portos,nome_pais,buscar_portos,rotulo_porto,garantir_selecao
from consumo.conteineres import carregar_conteineres
from consumo.tributos import carregar_cenarios_tributarios
from consumo.cambio import obter_cache_sessao,atualizar_cotacoes,consultar_cotacao,MOEDAS_SUPORTADAS
from calculos.fretes import cenario_compativel,serializar
from calculos.consolidacao import consolidar_operacao
from calculos.tributos import calcular_tributos,assinatura_base_tributaria
from interface.componentes import cabecalho
from interface.conversao import texto_faixa
from interface.resumo_tributario import exibir_resumo_tributario

SITUACOES={'aplicavel':'Aplicável (inclusive alíquota zero)','nao_informado':'Não informado','nao_aplicavel':'Não aplicável',
           'incluido':'Incluído em outra despesa/tributo','isento':'Isento — exige cenário documentado e fundamentação'}


def limpar_editores():
    for k in list(st.session_state):
        if k.startswith('fiscal_regra_'):
            del st.session_state[k]


def nova_regra(destino,moeda):
    return dict(id='manual_'+uuid4().hex[:10],versao='manual-1',nome='Tributo manual',jurisdicao=destino,
      escopo='importacao_destino',tipo_calculo='percentual',aliquota=None,valor_fixo=None,moeda=moeda,
      componentes_base=[],situacao='aplicavel',participa_total=True,incluido_em=None,
      inicio_vigencia=None,fim_vigencia=None,estado_regra='manual',revisao_especialista='nao_revisada',
      fonte=None,consultado_em=None,fundamentacao=None,cambio_base='referencia',arredondamento='politica_monetaria',observacoes='Informado pelo usuário; sem validação legal.')


def editor_regra(r,cenario,itens,nomes_tributos):
    p='fiscal_regra_'+r['id']+'_'
    anterior=deepcopy(r)
    def texto(chave,rotulo,valor):
        st.session_state.setdefault(p+chave,valor or '')
        return st.text_input(rotulo,key=p+chave)
    def opcao(chave,rotulo,opcoes,valor,format_func=lambda x:x):
        garantir_selecao(st.session_state,p+chave,opcoes,valor)
        return st.selectbox(rotulo,opcoes,key=p+chave,format_func=format_func)
    with st.expander(r['nome'],expanded=False):
        r['nome']=texto('nome','Nome do tributo',r['nome'])
        r['situacao']=opcao('situacao','Situação',list(SITUACOES),r['situacao'],SITUACOES.get)
        st.session_state.setdefault(p+'participa',r['participa_total'])
        r['participa_total']=st.checkbox('Participa do escopo configurado',key=p+'participa')
        a,b=st.columns(2)
        with a:
            r['tipo_calculo']=opcao('tipo','Cálculo',['percentual','fixo'],r['tipo_calculo'],lambda x:'Percentual sobre base explícita' if x=='percentual' else 'Valor fixo por operação')
        with b:
            r['moeda']=texto('moeda','Moeda do tributo (ISO)',r['moeda']).strip().upper()
        campo='aliquota' if r['tipo_calculo']=='percentual' else 'valor_fixo'
        st.session_state.setdefault(p+campo,None if r.get(campo) is None else float(r[campo]))
        r[campo]=st.number_input('Alíquota (%)' if campo=='aliquota' else 'Valor fixo na moeda informada',min_value=0.0,value=None,key=p+campo,format='%.6f')
        escopo=opcao('escopo','Escopo',['importacao_destino','exportacao_origem'],r['escopo'],lambda x:'Importação no destino' if x=='importacao_destino' else 'Exportação no país de embarque')
        if escopo!=r['escopo']:
            r['jurisdicao']=cenario['pais_destino'] if escopo=='importacao_destino' else cenario['pais_procedencia']
        r['escopo']=escopo
        esperado=cenario['pais_destino'] if escopo=='importacao_destino' else cenario['pais_procedencia']
        st.caption('Jurisdição informada da regra: '+r['jurisdicao'])
        if r['jurisdicao']!=esperado and st.button('Reatribuir manualmente esta regra ao país atual',key='reatribuir_'+r['id']):
            r['jurisdicao']=esperado
        bases={i['id']:i['nome'] for i in itens}
        bases['valor_aduaneiro']='Valor aduaneiro explicitamente informado'
        bases.update({'tributo:'+id_:nome for id_,nome in nomes_tributos.items() if id_!=r['id']})
        for antiga in r.get('componentes_base',[]):
            bases.setdefault(antiga,antiga+' (indisponível neste contexto)')
        st.session_state.setdefault(p+'componentes',list(r.get('componentes_base',[])))
        if r['tipo_calculo']=='percentual':
            r['componentes_base']=st.multiselect('Componentes da base (não há CIF automático)',list(bases),key=p+'componentes',format_func=bases.get)
            r['cambio_base']=opcao('cambio','Câmbio exigido para a base',['referencia','aduaneiro'],r['cambio_base'],lambda x:'Referência da simulação (Frankfurter)' if x=='referencia' else 'Aduaneiro específico — informar separadamente')
        if r['situacao']=='incluido':
            inclusoes={'despesa:'+i['id']:i['nome'] for i in itens if i['id']!='mercadoria'}
            inclusoes.update({'tributo:'+id_:nome for id_,nome in nomes_tributos.items() if id_!=r['id']})
            if r.get('incluido_em'):
                inclusoes.setdefault(r['incluido_em'],r['incluido_em']+' (verificar disponibilidade)')
            if inclusoes:
                r['incluido_em']=opcao('incluido','Já incluído em',list(inclusoes),r.get('incluido_em'),inclusoes.get)
            else:
                st.info('Nenhuma despesa ou outro tributo disponível para declarar inclusão.')
        a,b=st.columns(2)
        with a:
            inicio=st.date_input('Início da janela de aplicação informada',value=date.fromisoformat(r['inicio_vigencia']) if p+'inicio' not in st.session_state and r.get('inicio_vigencia') else None,key=p+'inicio')
        with b:
            fim=st.date_input('Fim da janela de aplicação informada',value=date.fromisoformat(r['fim_vigencia']) if p+'fim' not in st.session_state and r.get('fim_vigencia') else None,key=p+'fim')
        r['inicio_vigencia']=inicio.isoformat() if inicio else None
        r['fim_vigencia']=fim.isoformat() if fim else None
        r['fonte']=texto('fonte','Fonte informada (não comprova revisão legal)',r.get('fonte')) or None
        r['fundamentacao']=texto('fundamentacao','Fundamentação/observações da hipótese',r.get('fundamentacao')) or None
        campos=('nome','jurisdicao','escopo','tipo_calculo','aliquota','valor_fixo','moeda','componentes_base','situacao','participa_total','incluido_em','inicio_vigencia','fim_vigencia','fonte','fundamentacao','cambio_base')
        if any(r.get(c)!=anterior.get(c) for c in campos):
            if anterior['estado_regra']!='manual':
                r['substitui_regra']=dict(id=anterior['id'],versao=anterior['versao'],estado=anterior['estado_regra'],fonte=anterior.get('fonte'))
            r.update(estado_regra='manual',versao='manual-1',revisao_especialista='nao_revisada')
        st.caption('Regra: '+r['estado_regra']+' · versão '+r['versao']+' · revisão especialista: '+r.get('revisao_especialista','Não registrada'))
        if r.get('substitui_regra'):
            st.caption('Alteração manual substitui o parâmetro original do cenário: '+str(r['substitui_regra']))
    return r


def exibir():
    st.session_state.pop('tributos_ativos',None)
    cabecalho('Impostos','Simule tributos por cenário, classificação e data, com bases e premissas explícitas.','OPERAÇÕES')
    try:
        catalogo,_=carregar_dados_simulador()
        base,rotas=carregar_portos()
        equipamentos={c['id']:c for c in carregar_conteineres()}
        config=carregar_cenarios_tributarios()
    except ErroCatalogo as erro:
        st.error(str(erro))
        return
    produtos={p['id']:p for p in catalogo['produtos']}
    modo=st.selectbox('Modo tributário',['manual','exemplo_didatico','documentado'],format_func=lambda x:{'manual':'Simulação manual — regras não validadas','exemplo_didatico':'Exemplo didático — sem validade legal','documentado':'Cenário documentado'}[x],key='fiscal_modo')
    disponiveis=[c for c in config['cenarios'] if c['estado']==modo]
    st.caption('Cenários legais documentados ativados: '+str(sum(c['estado']=='documentado' for c in config['cenarios']))+'. Fontes de formato SH/NCM não comprovam alíquotas, existência do código ou enquadramento do produto.')
    escolhido=None
    if modo!='manual':
        if not disponiveis:
            st.info('Nenhum cenário legal documentado disponibilizado nesta versão. Use o modo manual ou os exercícios didáticos; regras oficiais dependem de confirmação documental e classificação adequada.')
            return
        por_id={c['id']:c for c in disponiveis}
        cid=st.selectbox('Cenário configurado',list(por_id),format_func=lambda i:por_id[i]['nome'],key='fiscal_cenario_id')
        escolhido=por_id[cid]
        def carregar_exemplo():
            st.session_state['fiscal_config_carregado']=cid
            st.session_state['fiscal_regras']=deepcopy(escolhido['regras'])
            for c in ('pais_origem','pais_procedencia','pais_destino'):
                st.session_state['fiscal_'+c]=escolhido[c]
            classe=escolhido['classificacao']
            for de,para in [('sistema','sistema'),('codigo','codigo'),('versao','versao'),('codigo_sintetico','sintetico')]:
                st.session_state['fiscal_class_'+para]=classe.get(de)
            st.session_state['fiscal_class_fonte']='Código sintético do exercício; não é classificação real.'
            st.session_state['fiscal_regime']=escolhido['condicoes']['regime']
            st.session_state['fiscal_nova']=escolhido['condicoes']['mercadoria_nova']
            adu=escolhido.get('valor_aduaneiro_exemplo') or {}
            st.session_state['fiscal_adu_valor']=None if adu.get('valor') is None else float(adu['valor'])
            st.session_state['fiscal_adu_moeda']=adu.get('moeda','BRL')
            st.session_state['fiscal_adu_fonte']=adu.get('fonte','')
            limpar_editores()
        st.button('Carregar explicitamente o cenário',on_click=carregar_exemplo,key='carregar_cenario_fiscal')
        if st.session_state.get('fiscal_config_carregado')!=cid:
            st.info('Carregue o cenário para preencher seus parâmetros explícitos. Não há seleção automática por produto ou código semelhante.')
            return
    def importar_simulador():
        produto=st.session_state.get('entrada_produto')
        if not isinstance(produto,dict): return
        id_=produto['id']
        st.session_state['fiscal_produto']=id_
        v=st.session_state.get('variante_'+id_)
        if isinstance(v,dict):st.session_state['fiscal_variante_'+id_]=v['nome']
        for de,para in [('entrada_qtd','fiscal_quantidade'),('entrada_destino_iso','fiscal_pais_destino'),
                        ('entrada_porto_origem','fiscal_porto_origem'),('entrada_porto_destino','fiscal_porto_destino'),
                        ('entrada_tipo_conteiner','fiscal_tipo'),('entrada_moeda_apresentacao','fiscal_moeda')]:
            if de in st.session_state:st.session_state[para]=st.session_state[de]
        st.session_state['fiscal_pais_procedencia']='BR'
    if isinstance(st.session_state.get('entrada_produto'),dict):
        st.button('Reaproveitar operação do simulador',on_click=importar_simulador,key='importar_cenario_fiscal')
    aba_cenario,aba_class,aba_regras,aba_resultado=st.tabs(['Cenário','Classificação fiscal','Regras e bases','Resultado e memória'])
    with aba_cenario:
        a,b,c=st.columns(3)
        garantir_selecao(st.session_state,'fiscal_produto',list(produtos))
        id_=a.selectbox('Produto',list(produtos),format_func=lambda i:produtos[i]['nome'],key='fiscal_produto')
        variantes={v['nome']:v for v in produtos[id_]['variantes']}
        garantir_selecao(st.session_state,'fiscal_variante_'+id_,list(variantes))
        nome=b.selectbox('Variante',list(variantes),key='fiscal_variante_'+id_)
        quantidade=c.number_input('Quantidade de produtos',min_value=1,step=1,value=None if 'fiscal_quantidade' in st.session_state else 1,key='fiscal_quantidade')
        a,b,c=st.columns(3)
        paises=list(base['paises'])
        garantir_selecao(st.session_state,'fiscal_pais_origem',paises,'BR')
        origem=a.selectbox('Origem da mercadoria (não é país de embarque)',paises,format_func=lambda p:nome_pais(base,rotas,p)+' · '+p,key='fiscal_pais_origem')
        b.text('Procedência/embarque: Brasil (BR). O fluxo atual não suporta importação para o Brasil.')
        destinos=[p for p in paises if p!='BR']
        garantir_selecao(st.session_state,'fiscal_pais_destino',destinos,'IT')
        destino=c.selectbox('Destino/importação',destinos,format_func=lambda p:nome_pais(base,rotas,p)+' · '+p,key='fiscal_pais_destino')
        a,b=st.columns(2)
        for coluna,iso,lado in ((a,'BR','origem'),(b,destino,'destino')):
            opcoes=buscar_portos(base,iso,favoritos=rotas['favoritos'])
            codigos=[p['unlocode'] for p in opcoes]
            garantir_selecao(st.session_state,'fiscal_porto_'+lado,codigos,rotas['paises'].get(iso,{}).get('porto_padrao'))
            coluna.selectbox('Porto de '+lado,codigos,format_func=lambda p:rotulo_porto(base['portos'][p]),key='fiscal_porto_'+lado)
        a,b,c=st.columns(3)
        dia=a.date_input('Data de referência da operação',value=None if 'fiscal_data' in st.session_state else datetime.now(ZoneInfo('America/Sao_Paulo')).date(),key='fiscal_data',format='DD/MM/YYYY')
        tipo=b.selectbox('Equipamento da operação',list(equipamentos),format_func=lambda i:equipamentos[i]['nome'],key='fiscal_tipo')
        apresentacao=c.selectbox('Moeda de apresentação',MOEDAS_SUPORTADAS,key='fiscal_moeda')
        regime=st.text_input('Regime/condições informadas',key='fiscal_regime')
        nova=st.checkbox('Mercadoria nova (condição declarada)',key='fiscal_nova')
    with aba_class:
        a,b,c=st.columns(3)
        sistema=a.selectbox('Sistema de classificação',['HS_SH','NCM','nacional_destino'],format_func=lambda x:{'HS_SH':'SH/HS — seis dígitos','NCM':'NCM — oito dígitos, Mercosul','nacional_destino':'Classificação nacional do destino'}[x],key='fiscal_class_sistema')
        codigo=b.text_input('Código como texto, sem pontuação',key='fiscal_class_codigo')
        versao=c.text_input('Versão/edição da classificação',key='fiscal_class_versao')
        fonte=st.text_input('Fonte informada para a classificação',key='fiscal_class_fonte')
        sintetico=st.checkbox('Código hipotético/sintético de exercício',key='fiscal_class_sintetico')
        tamanho=None
        if sistema=='nacional_destino':
            tamanho=st.number_input('Tamanho nacional declarado (não confirma padrão oficial)',min_value=1,max_value=16,value=None,key='fiscal_class_tamanho')
        st.info('O sistema verifica apenas formato. Não classifica pelo nome comercial, não confirma existência do código e não converte NCM em código nacional do destino. Uma classificação não revisada pode ser usada somente como hipótese manual/didática.')
    if quantidade is None or dia is None:
        st.error('Informe quantidade e data da operação.')
        return
    variante=variantes[nome]
    contexto=dict(produto_id=id_,variante=variante,quantidade=quantidade,
                  origem_unlocode=st.session_state['fiscal_porto_origem'],destino_unlocode=st.session_state['fiscal_porto_destino'],conteiner_id=tipo)
    log=st.session_state.get('logistica_ativa')
    moeda_antiga=(log or {}).get('entradas',{}).get('moeda',apresentacao)
    log=cenario_compativel(log,id_,variante,quantidade,contexto['origem_unlocode'],contexto['destino_unlocode'],tipo,moeda_antiga)
    cotacoes=obter_cache_sessao(st.session_state)
    def base_monetaria(taxas):
        return consolidar_operacao(variante,quantidade,catalogo['moeda'],apresentacao,taxas,logistica=log['entradas'] if log else None)
    base_atual=base_monetaria(list(cotacoes.values()))
    cenario=dict(pais_origem=origem,pais_procedencia='BR',pais_destino=destino,data_referencia=dia.isoformat(),
      produto_id=id_,variante=nome,quantidade=quantidade,classificacao=dict(codigo=codigo or None,sistema=sistema,versao=versao or None,
      fonte=fonte or None,pais=destino if sistema=='nacional_destino' else None,validacao_conteudo='nao_revisada',codigo_sintetico=sintetico,tamanho_declarado=tamanho),
      condicoes={'regime':regime,'mercadoria_nova':nova})
    with aba_regras:
        st.caption('Base comercial atual: '+texto_faixa(base_atual['itens'][0]['valor_original'],catalogo['moeda'])+'. Não é custo de fabricação nem valor aduaneiro automaticamente.')
        if not log:
            st.info('Sem cenário logístico compatível. Bases de frete/despesas podem estar indisponíveis; configure Fretes e rotas para completar o subtotal antes dos tributos.')
        a,b=st.columns(2)
        with a:
            adu_valor=st.number_input('Valor aduaneiro informado/hipotético (total)',min_value=0.0,value=None,key='fiscal_adu_valor')
            st.session_state.setdefault('fiscal_adu_moeda','BRL')
            adu_moeda=st.text_input('Moeda do valor aduaneiro',key='fiscal_adu_moeda').strip().upper()
        with b:
            adu_fonte=st.text_input('Fonte/premissa do valor aduaneiro',key='fiscal_adu_fonte')
            st.caption('Não é derivado automaticamente de produto + frete + seguro ou de custo de fabricação.')
        if adu_valor is not None:
            cenario['valor_aduaneiro']=dict(valor=adu_valor,moeda=adu_moeda,fonte=adu_fonte,origem='informado_manualmente' if not escolhido else 'hipotese_editavel_do_exercicio')
        if 'fiscal_regras' not in st.session_state:
            st.session_state['fiscal_regras']=[nova_regra(destino,apresentacao)]
        if st.button('Restaurar regras do modo atual',key='restaurar_fiscal'):
            st.session_state['fiscal_regras']=deepcopy(escolhido['regras']) if escolhido else [nova_regra(destino,apresentacao)]
            limpar_editores()
        regras=deepcopy(st.session_state['fiscal_regras'])
        if st.button('Adicionar tributo manual',key='adicionar_tributo'):
            regras.append(nova_regra(destino,apresentacao))
            st.session_state['fiscal_regras']=regras
            st.rerun()
        nomes={r['id']:r['nome'] for r in regras}
        for i,r in enumerate(regras):
            regras[i]=editor_regra(r,cenario,base_atual['itens'],nomes)
            if st.button('Remover '+r['nome'],key='remover_tributo_'+r['id']):
                st.session_state['fiscal_regras']=[x for x in regras if x['id']!=r['id']]
                limpar_editores()
                st.rerun()
        st.session_state['fiscal_regras']=regras
        cotacoes_adu=[]
        with st.expander('Taxa aduaneira específica informada pelo usuário'):
            st.caption('Só é usada por regras que exigem câmbio aduaneiro. Não é buscada na Frankfurter nem validada como taxa legal pelo sistema.')
            a,b,c=st.columns(3)
            de=a.text_input('Moeda de origem da taxa aduaneira',key='fiscal_cambio_adu_origem').strip().upper()
            para=b.text_input('Moeda de destino da taxa aduaneira',key='fiscal_cambio_adu_destino').strip().upper()
            valor=c.number_input('Taxa aduaneira informada (1 origem = taxa × destino)',min_value=0.0,value=None,key='fiscal_cambio_adu_valor',format='%.8f')
            data_adu=st.date_input('Data aduaneira requerida e informada',value=None if 'fiscal_cambio_adu_data' in st.session_state else dia,key='fiscal_cambio_adu_data',format='DD/MM/YYYY')
            fonte_adu=st.text_input('Fonte da taxa aduaneira informada',key='fiscal_cambio_adu_fonte')
            confirmado=st.checkbox('Informo esta taxa como aduaneira; não foi verificada pelo sistema',key='fiscal_cambio_adu_confirmado')
            cenario['data_cambio_aduaneiro']=data_adu.isoformat() if data_adu else dia.isoformat()
            if confirmado and valor is not None and de and para and fonte_adu and data_adu:
                cotacoes_adu=[dict(origem=de,destino=para,cotacao=valor,data_referencia=data_adu.isoformat(),fonte=fonte_adu,
                                  provedor='Informado pelo usuário — aduaneiro não verificado',metodo='manual',consultado_em=None,tipo_cambio='aduaneiro')]
    def calcular(taxas):
        monetario=base_monetaria(taxas)
        resultado=calcular_tributos(cenario,regras,monetario,taxas,cotacoes_adu,escolhido)
        return dict(monetario,resultado_tributario=resultado,pares_faltantes=[list(p) for p in sorted({tuple(p) for p in monetario['pares_faltantes']+resultado['pares_faltantes']})])
    with aba_resultado:
        try:
            calculo=calcular(list(cotacoes.values()))
            if st.button('Consultar / atualizar câmbio de referência',key='atualizar_cambio_fiscal'):
                with st.spinner('Atualizando o conjunto de câmbio de referência…'):
                    cotacoes,calculo,erros=atualizar_cotacoes(calcular,consultar_cotacao)
                    st.session_state['cotacoes_sessao']=cotacoes
                    for erro in erros:st.warning(erro)
            resultado=calculo['resultado_tributario']
        except ValueError as erro:
            st.error('Não foi possível calcular os tributos: '+str(erro))
            return
        snapshot=dict(assinatura_base=assinatura_base_tributaria(contexto,calculo),
          entradas=dict(cenario=cenario,regras=regras,cotacoes_aduaneiras=cotacoes_adu,config=deepcopy(escolhido),contexto=contexto),
          base_monetaria=serializar({k:v for k,v in calculo.items() if k!='resultado_tributario'}),resultado=serializar(resultado))
        st.session_state['tributos_ativos']=snapshot
        exibir_resumo_tributario(snapshot)
        def levar_simulador():
            st.session_state['entrada_produto']=produtos[id_]
            st.session_state['variante_'+id_]=variante
            st.session_state['entrada_qtd']=quantidade
            st.session_state['entrada_origem_iso']='BR'
            st.session_state['entrada_porto_origem']=contexto['origem_unlocode']
            st.session_state['entrada_destino_iso']=destino
            st.session_state['entrada_porto_destino']=contexto['destino_unlocode']
            st.session_state['entrada_tipo_conteiner']=tipo
            st.session_state['entrada_moeda_apresentacao']=apresentacao
            st.session_state['pais_moeda_atual']=destino
            st.session_state['entrada_busca_origem_BR']=''
            st.session_state['entrada_busca_destino_'+destino]=''
        if st.button('Levar cenário tributário ao simulador para salvar',key='levar_fiscal_simulador',on_click=levar_simulador,type='primary'):
            st.switch_page('paginas/simulador.py')
        st.caption('Salvar simulação no simulador grava uma cópia do cenário fiscal compatível. Editar tributos não altera o arquivo de regras nem registros anteriores.')
