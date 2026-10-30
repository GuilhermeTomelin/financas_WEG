from datetime import date
from html import escape

import streamlit as st

from calculos.operacoes import calcular_estimativa
from consumo.cambio import ErroCambio, consultar_cotacao
from consumo.catalogo import ErroCatalogo, carregar_catalogo


CAMPO_PRECO = "preco_venda_demonstracao_usd"
MOEDA_PRECO = "USD"

DESTINOS = {
    "Brasil (BRL)": "BRL",
    "Itália (EUR)": "EUR",
}

SIMBOLOS = {"USD": "US$", "BRL": "R$", "EUR": "€"}
SEPARADORES_BR = str.maketrans(",.", ".,")


def numero_br(valor, casas=2):
    return f"{valor:,.{casas}f}".translate(SEPARADORES_BR)


def moeda(valor, codigo, casas=2):
    return f"{SIMBOLOS[codigo]} {numero_br(valor, casas)}"


def data_cotacao(cambio):
    referencia = cambio.get("data_referencia")

    if referencia:
        try:
            return date.fromisoformat(referencia).strftime("%d/%m/%Y")
        except ValueError:
            return str(referencia)

    if cambio["origem"] == cambio["destino"]:
        return "Mesma moeda"

    return "Não informada"


st.set_page_config(
    page_title="Operações internacionais",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html("""
<style>
    .block-container {
        max-width: 1480px;
        padding-top: 3.75rem;
        padding-bottom: 2rem;
    }

    [data-testid="stSidebar"] {
        border-right: 1px solid #303645;
    }

    .marca {
        display: flex;
        align-items: center;
        gap: .7rem;
        margin-bottom: 1.8rem;
        color: #F4F6FA;
        font-weight: 750;
        font-size: 1.2rem;
    }

    .marca-simbolo {
        display: grid;
        place-items: center;
        width: 38px;
        height: 38px;
        border-radius: 10px;
        background: #12382F;
        border: 1px solid #25896D;
        color: #40F0B4;
        font-size: 1.4rem;
    }

    .rotulo {
        margin: 0 0 .55rem;
        color: #A4ADBE;
        font-size: .72rem;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .secao-ativa {
        padding: .65rem .8rem;
        border: 1px solid #349B7C;
        border-radius: 7px;
        background: linear-gradient(100deg, #173C32, #202431);
        color: #EEFFF8;
        font-weight: 600;
    }

    .st-key-resumo, .st-key-controles, .st-key-detalhes {
        background: #202431;
        border: 1px solid #303645;
        border-radius: 12px;
        padding: clamp(1rem, 2vw, 1.6rem);
        box-shadow: 0 5px 18px #00000014;
    }

    .st-key-controles [data-baseweb="select"] > div,
    .st-key-controles [data-testid="stNumberInputContainer"] {
        background: #191D28;
        border-color: #353C4D;
        border-radius: 7px;
    }

    .st-key-controles button[kind="primary"] {
        min-height: 46px;
        background: linear-gradient(105deg, #39F4B6, #12D49B);
        color: #08251C;
        border: 1px solid #53EAB9;
        border-radius: 7px;
        font-weight: 750;
        box-shadow: 0 2px 12px #18D69A26;
    }

    .st-key-controles button[kind="primary"]:hover {
        filter: brightness(1.08);
        color: #08251C;
    }

    .valor-principal {
        color: #F7FAFF;
        font-size: clamp(2.1rem, 4.3vw, 4.4rem);
        line-height: 1.1;
        font-weight: 750;
        letter-spacing: -.055em;
        overflow-wrap: anywhere;
        font-variant-numeric: tabular-nums;
        margin: .15rem 0 .45rem;
    }

    .nota {
        color: #ACB5C6;
        font-size: .9rem;
        line-height: 1.45;
    }

    .rota {
        display: inline-block;
        color: #C1EADB;
        background: #1B332D;
        border: 1px solid #305248;
        border-radius: 6px;
        padding: .2rem .55rem;
        font-size: .8rem;
        font-weight: 650;
    }

    @media (max-width: 700px) {
        .block-container { padding-inline: 1rem; }
        .valor-principal { font-size: 2.5rem; }
    }
</style>
""")

with st.sidebar:
    st.html("""
    <div class="marca">
        <span class="marca-simbolo" aria-hidden="true">⇄</span>
        <span>Operações</span>
    </div>
    <div class="rotulo">Área de trabalho</div>
    <div class="secao-ativa">Conversão internacional</div>
    """)
    st.divider()
    st.caption("Moeda do catálogo")
    st.write("**USD · Dólar americano**")
    st.caption("Projeto educacional sem vínculo oficial com a WEG.")

st.title("Operações internacionais")
st.caption("Simule o valor dos produtos na moeda do país de destino.")

try:
    produtos = carregar_catalogo()
except ErroCatalogo as erro:
    st.error(f"Não foi possível carregar o catálogo: {erro}")
    st.stop()

if not produtos:
    st.info("O catálogo ainda não tem produtos cadastrados.")
    st.stop()

# Os controles são lidos primeiro, mas aparecem na coluna da direita.
principal, lateral = st.columns([1.6, 1], gap="medium")

with lateral.container(key="controles", border=True):
    st.html('<div class="rotulo">Configuração</div>')
    st.subheader("Montar operação")

    produto = st.selectbox(
        "Produto",
        produtos,
        format_func=lambda item: f'{item["nome"]} ({item["categoria"]})',
    )

    quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)
    nome_destino = st.selectbox("Destino", list(DESTINOS))
    destino = DESTINOS[nome_destino]

    preco = produto.get(CAMPO_PRECO)
    preco_valido = isinstance(preco, (int, float)) and preco > 0

    if not preco_valido:
        st.error("Este produto não tem um preço válido cadastrado.")

    calcular = st.button(
        "Calcular conversão",
        type="primary",
        width="stretch",
        disabled=not preco_valido,
    )

# Uma estimativa anterior só aparece enquanto os dados continuarem iguais.
selecao = (produto["nome"], produto["categoria"], preco, quantidade, destino)
if st.session_state.get("selecao_operacao") != selecao:
    st.session_state["selecao_operacao"] = selecao
    st.session_state.pop("estimativa", None)

erro_operacao = None

if calcular:
    st.session_state.pop("estimativa", None)
    try:
        cambio = consultar_cotacao(MOEDA_PRECO, destino)
        totais = calcular_estimativa(preco, quantidade, cambio["cotacao"])
    except ErroCambio as erro:
        erro_operacao = f"Não foi possível consultar a cotação. {erro}"
    except ValueError as erro:
        erro_operacao = f"Não foi possível calcular a estimativa. {erro}"
    else:
        st.session_state["estimativa"] = (cambio, totais)

estimativa = st.session_state.get("estimativa")

with principal.container(key="resumo", border=True):
    st.html('<div class="rotulo">Resumo da operação</div>')
    st.subheader(produto["nome"])
    st.html(f'<span class="rota">{MOEDA_PRECO} → {destino}</span>')
    st.divider()

    if estimativa:
        cambio, totais = estimativa
        titulo_valor = "Total convertido estimado"
        valor = moeda(totais["total_convertido"], destino)
        legenda = f'{nome_destino} · {numero_br(quantidade, 0)} un.'
    else:
        titulo_valor = "Preço unitário de demonstração"
        valor = moeda(preco, MOEDA_PRECO) if preco_valido else "Indisponível"
        legenda = "Calcule a conversão para ver o total na moeda do destino."

    st.html(f"""
    <div class="rotulo">{escape(titulo_valor)}</div>
    <div class="valor-principal">{escape(valor)}</div>
    <div class="nota">{escape(legenda)}</div>
    """)

    if erro_operacao:
        st.error(erro_operacao)

    st.divider()
    esquerda, direita = st.columns(2)

    if estimativa:
        esquerda.metric("Total original", moeda(totais["total_original"], MOEDA_PRECO))
        direita.metric("Quantidade", f"{numero_br(quantidade, 0)} un.")
    else:
        esquerda.metric("Quantidade", f"{numero_br(quantidade, 0)} un.")
        direita.metric("Moeda de destino", destino)

with st.container(key="detalhes", border=True):
    st.html('<div class="rotulo">Memória da operação</div>')
    st.subheader("Detalhes da conversão")

    item_preco, item_cambio, item_data = st.columns(3)

    item_preco.caption("Preço unitário de demonstração")
    item_preco.write(moeda(preco, MOEDA_PRECO) if preco_valido else "Indisponível")

    item_cambio.caption("Cotação aplicada")
    item_data.caption("Data de referência")

    if estimativa:
        cambio, _ = estimativa
        taxa = moeda(cambio["cotacao"], cambio["destino"], casas=4)
        item_cambio.write(f"US$ 1,00 = {taxa}")
        item_data.write(data_cotacao(cambio))
    else:
        item_cambio.write("Aguardando consulta")
        item_data.write("—")

    st.divider()
    if produto.get("preco_e_ficticio"):
        st.caption("Preço fictício para demonstração. O valor não representa um preço oficial da WEG.")
    st.caption("A estimativa considera apenas os produtos. Frete, impostos e taxas ficam fora do total.")

    if produto.get("peso_kg") is None or produto.get("dimensoes_mm") is None:
        st.caption("O catálogo não informa todos os dados de peso e dimensões deste produto.")