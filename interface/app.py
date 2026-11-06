from pathlib import Path
import streamlit as st
from interface.tema import aplicar

st.set_page_config(page_title="Finanças WEG · Comércio internacional", page_icon=":material/public:",
                   layout="wide", initial_sidebar_state="auto")
aplicar()
# Preserva seleções dos widgets que deixam de aparecer ao trocar de página.
for chave in list(st.session_state):
    if chave.startswith(("entrada_", "variante_", "catalogo_", "consulta_", "rel_", "conteiner_", "frete_", "fiscal_", "custo_")) or chave in ("periodo", "paises", "produtos"):
        st.session_state[chave] = st.session_state[chave]

st.logo(str(Path(__file__).parent / "assets" / "marca.svg"), size="large",
        icon_image=str(Path(__file__).parent / "assets" / "icone.svg"))

paginas = {
    "VISÃO GERAL": [
        st.Page("paginas/dashboard.py", title="Dashboard", icon=":material/space_dashboard:", default=True),
    ],
    "OPERAÇÕES": [
        st.Page("paginas/simulador.py", title="Simulador", icon=":material/calculate:", default=False),
        st.Page("paginas/conteineres.py", title="Contêineres", icon=":material/inventory_2:", default=False),
        st.Page("paginas/rotas.py", title="Fretes e rotas", icon=":material/route:", default=False),
        st.Page("paginas/impostos.py", title="Impostos", icon=":material/receipt_long:", default=False),
        st.Page("paginas/precificacao.py", title="Precificação", icon=":material/sell:", default=False),
    ],
    "DADOS E ANÁLISES": [
        st.Page("paginas/produtos.py", title="Produtos", icon=":material/category:", default=False),
        st.Page("paginas/historico.py", title="Histórico e relatórios", icon=":material/query_stats:", default=False),
    ],
    "SISTEMA": [
        st.Page("paginas/integracoes.py", title="Integrações", icon=":material/hub:", default=False),
    ],
}
pagina = st.navigation(paginas, expanded=True)
with st.sidebar:
    st.caption("AMBIENTE EDUCACIONAL")
    st.caption("Preços e dados físicos de demonstração. Projeto independente, sem vínculo oficial com a WEG.")
pagina.run()
