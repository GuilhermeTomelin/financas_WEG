"""Páginas de consulta e visão geral; não cria regras de negócio novas."""
from datetime import datetime
from html import escape
import sqlite3
import altair as alt
import pandas as pd
import streamlit as st

from consumo.catalogo import carregar_dados_simulador, ErroCatalogo
from consumo import historico as armazenamento
from consumo.portos import carregar_portos, buscar_portos, nome_pais, garantir_selecao
from consumo.cambio import MOEDAS_SUPORTADAS
from interface.componentes import cabecalho, estado, numero_br, moeda, mostrar_faixa, mostrar_referencia, dados_logisticos


def dados():
    try:
        catalogo, _ = carregar_dados_simulador()
        base, config = carregar_portos()
        return catalogo, base, config
    except ErroCatalogo as erro:
        st.error(str(erro))
        st.stop()


def registros():
    # Abrir uma página de consulta não cria um banco vazio.
    try:
        return armazenamento.listar() if armazenamento.BANCO.exists() else []
    except (OSError, sqlite3.Error, ValueError, KeyError) as erro:
        st.error("Não foi possível ler o histórico local. Confira o acesso e a integridade do arquivo de simulações.")
        return None


def linhas_historico(itens):
    return [{"ID": r["id"], "Salvamento": datetime.fromisoformat(r["salvo"]).astimezone().strftime("%d/%m/%Y %H:%M"),
             "Produto": r["produto"], "Destino": r["pais"], "Quantidade": r["quantidade"],
             "Moeda": r["moeda"]} for r in itens]


def dashboard():
    cabecalho("Dashboard", "Seu ponto de partida para simular e consultar operações internacionais.")
    catalogo, base, config = dados()
    salvos = registros()
    a,b,c,d = st.columns(4)
    a.metric("Produtos no catálogo", numero_br(len(catalogo["produtos"]), 0), icon=":material/category:")
    b.metric("Variantes disponíveis", numero_br(sum(len(p["variantes"]) for p in catalogo["produtos"]), 0), icon=":material/view_module:")
    c.metric("Países com portos", numero_br(len(base["paises"]) - 1, 0), icon=":material/public:", help="Países de destino. Exclui o Brasil, origem habilitada. Não representa cobertura de frete ou impostos.")
    d.metric("Simulações salvas", numero_br(len(salvos), 0) if salvos is not None else "Indisponível", icon=":material/history:")
    st.write("")
    esquerda, direita = st.columns([1.5,1], gap="large")
    with esquerda.container(border=True, key="card_comecar"):
        st.badge("Pronto para simular", color="blue", icon=":material/calculate:")
        st.subheader("Da mercadoria ao valor convertido")
        st.write("Escolha uma variante, monte o trajeto e compare o subtotal com uma cotação de referência.")
        st.page_link("paginas/simulador.py", label="Iniciar simulação", icon=":material/arrow_forward:")
        st.caption("Subtotal de mercadoria. Frete, seguro e impostos ainda não compõem um custo completo.")
    with direita.container(border=True, key="card_bases"):
        st.subheader("Bases disponíveis")
        st.write(f"**{numero_br(len(base['portos']), 0)}** localidades portuárias · UN/LOCODE {base['metadados']['publicacao']}")
        st.caption("Função portuária não confirma terminal de contêineres ou serviço comercial.")
        st.badge("Catálogo de demonstração", color="violet")
        st.caption("Preços e características físicas simulados. Custo de origem pendente.")
        st.page_link("paginas/produtos.py", label="Explorar produtos", icon=":material/category:")
    st.subheader("Atividade recente")
    if salvos is None:
        return
    if not salvos:
        estado("Sua primeira operação começa no simulador", "Ainda não há simulações salvas. Selecione produto e destino, calcule a conversão e use Salvar simulação.")
    else:
        with st.container(border=True, key="card_recentes"):
            st.dataframe(linhas_historico(salvos[:5]), hide_index=True, width="stretch")
            st.page_link("paginas/historico.py", label="Ver histórico e relatórios", icon=":material/query_stats:")
        contagem = pd.DataFrame([{"País":r["pais"],"Simulações":1} for r in salvos]).groupby("País",as_index=False)["Simulações"].sum()
        with st.container(border=True, key="card_atividade"):
            st.subheader("Simulações por país de destino")
            st.altair_chart(alt.Chart(contagem).mark_bar(color="#3B63F6", cornerRadiusEnd=4).encode(
                y=alt.Y("País:N",sort="-x"),x="Simulações:Q",tooltip=["País","Simulações"]),width="stretch")


def produtos():
    cabecalho("Produtos", "Consulte o catálogo comercial e as informações logísticas por variante.", "DADOS E ANÁLISES")
    catalogo, _, _ = dados()
    a,b=st.columns([2,1])
    busca=a.text_input("Buscar produto ou variante",key="catalogo_busca",placeholder="Nome, categoria ou identificador")
    categoria=b.selectbox("Categoria",["Todas"]+sorted({p["categoria"] for p in catalogo["produtos"]}),key="catalogo_categoria")
    itens=[p for p in catalogo["produtos"] if (categoria=="Todas" or p["categoria"]==categoria)
           and busca.casefold() in (p["id"]+" "+p["nome"]+" "+p["categoria"]+" "+" ".join(v["nome"] for v in p["variantes"])).casefold()]
    if not itens:
        estado("Nenhum produto encontrado", "Altere a busca ou selecione outra categoria.")
        return
    por_id={p["id"]:p for p in itens}
    garantir_selecao(st.session_state,"catalogo_produto",list(por_id))
    id_=st.selectbox("Produto",list(por_id),format_func=lambda i:por_id[i]["nome"],key="catalogo_produto")
    produto=por_id[id_]
    variantes={v["nome"]:v for v in produto["variantes"]}
    nome=st.selectbox("Variante",list(variantes),key=f"catalogo_variante_{id_}")
    variante=variantes[nome]
    comercial,logistica=st.tabs(["Comercial","Logística"])
    with comercial, st.container(border=True,key="card_comercial"):
        st.badge("Preço simulado",color="violet")
        st.subheader(produto["nome"])
        st.caption(produto["categoria"]+" · "+variante["nome"])
        st.caption("Preço unitário do catálogo")
        st.html('<div class="preco-catalogo">' + escape(mostrar_faixa(variante,catalogo["moeda"])) + "</div>")
        mostrar_referencia(variante,catalogo["moeda"])
        st.caption("Fonte do preço: "+catalogo["fonte_preco"])
        custo=variante.get("custo_origem") or {}
        st.markdown("#### Custo de origem unitário")
        if custo.get("minimo") is None:
            st.info("Custo de fabricação ou compra não informado. O preço do catálogo não é custo de origem.")
        else:
            st.write(mostrar_faixa(custo,custo["moeda"]))
            st.caption(f"Tipo: {custo.get('tipo')} · Natureza: {custo.get('natureza')} · Fonte: {custo.get('fonte') or 'Não informada'} · Data: {custo.get('data_referencia') or 'Não informada'}")
    with logistica:
        dados_logisticos(variante)


def consultar_portos():
    _,base,config=dados()
    a,b,c=st.columns(3)
    a.metric("Países/territórios na base",numero_br(len(base["paises"]),0))
    b.metric("Localidades elegíveis",numero_br(len(base["portos"]),0))
    c.metric("Rotas comerciais legadas",numero_br(len(config["rotas"]),0))
    with st.container(border=True,key="card_consulta_portos"):
        garantir_selecao(st.session_state,"consulta_pais",list(base["paises"]),"BR")
        pais=st.selectbox("País para consulta",list(base["paises"]),key="consulta_pais",
                          format_func=lambda iso:f"{nome_pais(base,config,iso)} · {iso}")
        busca=st.text_input("Pesquisar nome, subdivisão ou UN/LOCODE",key="consulta_busca")
        opcoes=buscar_portos(base,pais,busca,st.session_state.get("favoritos_portos",config["favoritos"]))
        if opcoes:
            st.caption(f"{numero_br(len(opcoes),0)} localidades encontradas")
            st.dataframe([{"UN/LOCODE":p["unlocode"],"Localidade":p["nome"],"País ISO":p["pais_iso"],
                           "Subdivisão":p["subdivisao"] or "Não informada","Nome da subdivisão":p["nome_subdivisao"] or "Não informado",
                           "Função":p["funcao"],"Status":p["status"]} for p in opcoes],hide_index=True,width="stretch")
        else:
            estado("Nenhuma localidade encontrada", "Altere a busca ou o país para continuar.")
    with st.container(border=True,key="card_fretes"):
        st.subheader("Disponibilidade comercial")
        if config["rotas"]:
            st.dataframe(config["rotas"],hide_index=True,width="stretch")
        else:
            st.info("Sem cotações comerciais reais cadastradas. Os exemplos didáticos e a entrada manual estão na aba Simulação logística.")
        st.caption("Uma localidade cadastrada não é uma rota atendida. Nenhuma tarifa é criada ou replicada automaticamente.")
    with st.expander("Fonte e critérios da base"):
        meta=base["metadados"]
        st.write(f"UNECE / UN/LOCODE {meta['publicacao']} · Obtida em {datetime.fromisoformat(meta['obtido_em']).strftime('%d/%m/%Y')}")
        st.link_button("Publicação oficial UNECE",meta["pagina_publicacao"],icon=":material/open_in_new:")
        st.write("Filtro marítimo: função 1 e status AA, AC, AF, AI, AM, AS ou RL; remoções, referências e conflitos excluídos.")
        st.caption("Status RL confirma localidade, sem confirmar relevância comercial. A base não garante terminais de contêineres ou serviços regulares.")


def historico():
    from interface.relatorios import exibir
    cabecalho("Histórico e relatórios", "Consulte as operações salvas e analise os dados disponíveis.", "DADOS E ANÁLISES")
    salvos=registros()
    if salvos is None:
        return
    if not salvos:
        # Mantém a organização também no estado vazio.
        a,b=st.tabs(["Histórico","Relatórios"])
        with a:
            estado("Nenhuma simulação salva", "Abra o simulador, calcule uma conversão e salve o resultado para consultá-lo aqui.")
            st.page_link("paginas/simulador.py",label="Abrir simulador",icon=":material/calculate:")
        with b:
            estado("Os relatórios aparecem com seus dados", "Salve uma operação para analisar destinos, produtos, valores e comparações de taxas.")
        return
    exibir(moeda,mostrar_faixa,numero_br,salvos)


def conteineres():
    from interface.conteineres import exibir
    exibir()


def impostos():
    cabecalho("Impostos", "Visão tributária das operações internacionais.", "OPERAÇÕES")
    estado("Tributação da operação", "Organizar os tributos aplicáveis conforme origem, destino e características da mercadoria. Alíquotas e fórmulas ainda não foram implementadas.", planejado=True)


def precificacao():
    cabecalho("Precificação", "Análise de custos e formação de preço.", "OPERAÇÕES")
    estado("Custo, margem e preço sugerido", "Reunir os custos disponíveis para uma futura análise unitária, de margem e de preço. Ainda faltam custos de origem e componentes da operação.", planejado=True)


def integracoes():
    cabecalho("Integrações", "Fontes existentes e conexões previstas para o projeto.", "SISTEMA")
    with st.container(border=True,key="card_frankfurter"):
        st.badge("Implementada · consulta sob demanda",color="blue",icon=":material/currency_exchange:")
        st.subheader("Frankfurter")
        st.write("Câmbio de referência consultado ao calcular uma conversão no simulador.")
        cambio=st.session_state.get("cambio_simulador") or next(iter(st.session_state.get("cotacoes_sessao",{}).values()),None)
        if st.session_state.get("falha_cambio"):
            st.warning("A última consulta desta sessão falhou. Uma nova tentativa pode ser feita no simulador.")
        elif cambio:
            st.write(f"Última referência da sessão: {cambio['origem']} → {cambio['destino']} · {numero_br(cambio['cotacao'],6)}")
            st.caption("Data da referência: "+ (datetime.fromisoformat(cambio["data_referencia"]).strftime("%d/%m/%Y") if cambio.get("data_referencia") else "Não informada; conversão na mesma moeda pode usar fator local 1."))
        else:
            st.caption("Disponibilidade atual não verificada. Nenhuma consulta é disparada ao abrir esta página.")
        st.caption("Moedas habilitadas no aplicativo: "+", ".join(MOEDAS_SUPORTADAS))
    estado("ThingSpeak", "Integração prevista, ainda não implementada.", planejado=True)
    estado("API do outro projeto", "Integração futura — escopo a definir.", planejado=True)


def rotas():
    from interface.fretes import exibir
    exibir()
