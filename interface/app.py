import streamlit as st

from calculos.operacoes import calcular_estimativa
from consumo.cambio import ErroCambio, consultar_cotacao
from consumo.catalogo import ErroCatalogo, carregar_catalogo

# O JSON não tem um campo "moeda": a moeda está no nome do campo do preço (_usd).
CAMPO_PRECO = "preco_venda_demonstracao_usd"
MOEDA_PRECO = "USD"

DESTINOS = {
    "Brasil (BRL)": "BRL",
    "Itália (EUR)": "EUR",
}


def formatar(valor, moeda):
    return f"{valor:,.2f} {moeda}"


st.set_page_config(page_title="financas_WEG", page_icon="🧮")
st.title("Simulador de valor convertido estimado")
st.caption("Projeto educacional, sem vínculo oficial com a WEG.")

try:
    produtos = carregar_catalogo()
except ErroCatalogo as erro:
    st.error(f"Não foi possível carregar o catálogo: {erro}")
    st.stop()

produto = st.selectbox(
    "Produto",
    produtos,
    format_func=lambda item: f'{item["nome"]} ({item["categoria"]})',
)

preco_unitario = produto.get(CAMPO_PRECO)
if not isinstance(preco_unitario, (int, float)) or preco_unitario <= 0:
    st.error("Este produto não tem um preço válido cadastrado.")
    st.stop()

st.write(f'**Modelo:** {produto["nome"]}')
st.write(f"**Preço cadastrado:** {formatar(preco_unitario, MOEDA_PRECO)}")
if produto.get("preco_e_ficticio"):
    st.warning("Preço FICTÍCIO, apenas para demonstração. Não é preço de venda da WEG.")

quantidade = st.number_input("Quantidade", min_value=1, step=1, value=1)
nome_destino = st.selectbox("Destino", list(DESTINOS))
moeda_destino = DESTINOS[nome_destino]

if st.button("Calcular estimativa"):
    try:
        cambio = consultar_cotacao(MOEDA_PRECO, moeda_destino)
        resultado = calcular_estimativa(preco_unitario, quantidade, cambio["cotacao"])
    except ErroCambio as erro:
        st.error(f"Não foi possível obter a cotação. Nenhum valor foi calculado. Detalhe: {erro}")
    except ValueError as erro:
        st.error(f"Dados inválidos para o cálculo: {erro}")
    else:
        st.subheader("Resultado")
        st.write(f'**Produto:** {produto["nome"]}')
        st.write(f"**Quantidade:** {quantidade}")
        st.write(f"**Preço unitário (moeda original):** {formatar(preco_unitario, MOEDA_PRECO)}")
        st.write(f"**Total (moeda original):** {formatar(resultado['total_original'], MOEDA_PRECO)}")
        st.write(f"**Cotação usada:** 1 {cambio['origem']} = {cambio['cotacao']:.4f} {cambio['destino']}")
        if cambio["data_referencia"]:
            st.write(f"**Data de referência:** {cambio['data_referencia']}")
        else:
            st.write("**Data de referência:** não se aplica (mesma moeda, cotação 1).")
        st.success(
            f"Valor convertido estimado: {formatar(resultado['total_convertido'], cambio['destino'])}"
        )

        if produto.get("peso_kg") is None or produto.get("dimensoes_mm") is None:
            st.info("Peso e/ou dimensões não cadastrados; nada foi estimado a partir deles.")
        st.caption("Frete, impostos e taxas ainda NÃO estão incluídos neste valor.")