import math
import sqlite3
from uuid import uuid4
from consumo.historico import salvar
from interface.relatorios import exibir
from datetime import date
from html import escape

import streamlit as st

from calculos.operacoes import calcular_subtotal_faixa, converter_faixa
from consumo.cambio import ErroCambio, consultar_cotacao
from consumo.catalogo import ErroCatalogo, carregar_dados_simulador


SIMBOLOS = {"BRL": "R$", "USD": "US$", "EUR": "€"}
SEPARADORES_BR = str.maketrans(",.", ".,")


def numero_br(valor, casas=2):
    return f"{valor:,.{casas}f}".translate(SEPARADORES_BR)


def moeda(valor, codigo, casas=2):
    simbolo = SIMBOLOS.get(codigo, codigo)
    return f"{simbolo} {numero_br(valor, casas)}"


def mostrar_faixa(faixa, codigo):
    minimo = moeda(faixa["minimo"], codigo)
    if faixa["maximo"] is None:
        return f"A partir de {minimo}"
    return f"{minimo} a {moeda(faixa['maximo'], codigo)}"


def mostrar_referencia(faixa, codigo):
    referencia = faixa.get("referencia_superior")
    if referencia is not None:
        st.caption(
            f"Referência superior em {codigo}: {moeda(referencia, codigo)}. "
            "O valor pode ultrapassar essa referência."
        )


def data_cotacao(cambio):
    referencia = cambio.get("data_referencia")
    if not referencia:
        return "Não informada"
    try:
        return date.fromisoformat(referencia).strftime("%d/%m/%Y")
    except ValueError:
        return str(referencia)


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
.extremos {display:flex;flex-wrap:wrap;gap:.75rem 2rem;margin:.35rem 0 .8rem}
    .extremos div {max-width:100%;overflow-x:auto}
    .extremos small {display:block;color:#ACB5C6}
    .extremos strong {white-space:nowrap;font-size:clamp(1.25rem,2vw,2.25rem);font-variant-numeric:tabular-nums}
    @media(max-width:700px){.extremos {flex-direction:column}}
</style>
""")

try:
    catalogo, rotas = carregar_dados_simulador()
except ErroCatalogo as erro:
    st.error(str(erro))
    st.stop()

moeda_base = catalogo["moeda"]
origem = rotas["origem"]

with st.sidebar:
    st.html("""
    <div class="marca">
        <span class="marca-simbolo" aria-hidden="true">⇄</span>
        <span>Operações</span>
    </div>
    <div class="rotulo">Área de trabalho</div>
    
    """)
    pagina = st.radio("Navegação", ["Simulador", "Relatórios"])
    st.divider()
    st.caption("Moeda do catálogo")
    st.write("**BRL · Real brasileiro**" if moeda_base == "BRL" else moeda_base)
    st.caption("Porto de origem")
    st.write(f"{origem['porto']} · {origem['pais']}")
    st.caption("Projeto educacional sem vínculo oficial com a WEG.")

if pagina == "Relatórios":
    # Evita a limpeza automática dos widgets ocultos do simulador.
    for chave in list(st.session_state):
        if chave.startswith(("entrada_", "variante_")):
            st.session_state[chave] = st.session_state[chave]
    exibir(moeda, mostrar_faixa, numero_br)
    st.stop()

st.title("Operações internacionais")
st.caption("Escolha a mercadoria e o destino para simular a operação.")

principal, lateral = st.columns([1.6, 1], gap="medium")

with lateral.container(key="controles", border=True):
    st.html('<div class="rotulo">Configuração</div>')
    st.subheader("Montar operação")

    produto = st.selectbox(
        "Produto",
        catalogo["produtos"], key="entrada_produto",
        format_func=lambda item: item["nome"],
    )
    variante = st.selectbox(
        "Variante",
        produto["variantes"],
        format_func=lambda item: item["nome"],
        key=f"variante_{produto['id']}",
    )
    quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1, key="entrada_qtd")

    pais = st.selectbox("País de destino", list(rotas["destinos"]), key="entrada_pais")
    destino = rotas["destinos"][pais]
    moeda_destino = destino["moeda"]
    rota = f"{origem['porto']} → {destino['porto']}"

    st.caption(f"Rota marítima · {rota}")
    st.caption(f"Moeda do destino · {moeda_destino}")

    calcular = st.button(
        "Calcular conversão",
        type="primary",
        width="stretch",
    )

subtotal = calcular_subtotal_faixa(variante, quantidade)

# Só a cotação é reutilizada. O subtotal acompanha a seleção atual.
par = (moeda_base, moeda_destino)
if st.session_state.get("par_cambio") != par:
    st.session_state["par_cambio"] = par
    st.session_state.pop("cambio_simulador", None)
    st.session_state.pop("falha_cambio", None)

if calcular:
    st.session_state.pop("cambio_simulador", None)
    st.session_state.pop("falha_cambio", None)
    try:
        with st.spinner("Consultando a Frankfurter…"):
            st.session_state["cambio_simulador"] = consultar_cotacao(*par)
    except ErroCambio:
        st.session_state["falha_cambio"] = True

cambio = st.session_state.get("cambio_simulador")

with principal.container(key="resumo", border=True):
    st.html('<div class="rotulo">Resumo da operação</div>')
    st.subheader(produto["nome"])
    st.caption(f"{variante['nome']} · {numero_br(quantidade, 0)} un.")
    st.html(f'<span class="rota">{escape(rota)} · {escape(moeda_destino)}</span>')
    st.divider()

    if cambio:
        faixa_destaque = converter_faixa(subtotal, cambio["cotacao"])
        codigo_destaque = moeda_destino
    else:
        faixa_destaque = subtotal
        codigo_destaque = moeda_base

    st.caption(f"Subtotal da mercadoria em {codigo_destaque} · preço simulado")
    extremos = [("A partir de", faixa_destaque["minimo"])] if faixa_destaque["maximo"] is None else [
        ("Mínimo", faixa_destaque["minimo"]), ("Máximo", faixa_destaque["maximo"])]
    blocos = "".join(
        f'<div><small>{rotulo}</small><strong>{escape(moeda(valor, codigo_destaque))}</strong></div>'
        for rotulo, valor in extremos)
    st.html(f'<div class="extremos">{blocos}</div>')
    mostrar_referencia(faixa_destaque, codigo_destaque)

    if cambio:
        st.divider()
        st.write(f"**Subtotal em reais:** {mostrar_faixa(subtotal, moeda_base)}")
        mostrar_referencia(subtotal, moeda_base)
    elif st.session_state.get("falha_cambio"):
        st.warning(
            "Cotação indisponível. Clique em Calcular conversão para tentar novamente."
        )
    else:
        st.caption("Clique em Calcular conversão para consultar o câmbio.")

with lateral:
    comparacao = None
    valido = bool(cambio)
    if cambio:
        with st.expander("Comparar taxa negociada"):
            if st.checkbox("Usar taxa manual", key=f"entrada_comparar_{moeda_destino}"):
                manual = st.number_input(f"Quantos {moeda_destino} correspondem a 1 BRL?",
                                         value=None, format="%.6f", key=f"entrada_taxa_{moeda_destino}")
                valido = manual is not None and math.isfinite(manual) and manual > 0
                if valido:
                    negociado = converter_faixa(subtotal, manual)
                    diferenca = negociado["minimo"] - faixa_destaque["minimo"]
                    percentual = (manual / cambio["cotacao"] - 1) * 100
                    comparacao = dict(taxa=manual, negociado=negociado, diferenca=diferenca,
                                      percentual=percentual)
                    st.write("Referência", mostrar_faixa(faixa_destaque, moeda_destino))
                    st.write("Hipótese negociada", mostrar_faixa(negociado, moeda_destino))
                    st.caption(f"Impacto sobre o mínimo: {moeda(diferenca, moeda_destino)} "
                               f"({numero_br(percentual)}%).")
                else:
                    st.caption("Informe uma taxa positiva para comparar e salvar.")

    operacao = dict(produto_id=produto["id"], produto=produto["nome"], categoria=produto["categoria"],
                    variante=variante["nome"], quantidade=quantidade, origem=origem, pais=pais,
                    destino=destino, moeda=moeda_destino, moeda_base=moeda_base, unitario=variante,
                    subtotal=subtotal, convertido=faixa_destaque, cambio=cambio, fonte_cambio="Frankfurter",
                    tipo_preco="simulado", fonte_preco=catalogo["fonte_preco"], comparacao=comparacao)
    if calcular or operacao != st.session_state.get("fotografia"):
        st.session_state.fotografia = operacao
        st.session_state.resultado_id = uuid4().hex
        st.session_state.pop("registro_salvo", None)
    registro = st.session_state.get("registro_salvo")
    if st.button("Salvar simulação", disabled=not valido or bool(registro), width="stretch"):
        try:
            st.session_state.registro_salvo = salvar(st.session_state.resultado_id, operacao)
            st.rerun()
        except (sqlite3.Error, OSError):
            st.error("Falha ao gravar. Confira a pasta dados e tente salvar novamente.")
    if registro:
        st.success(f"Simulação #{registro} salva.")

with st.container(key="detalhes", border=True):
    st.html('<div class="rotulo">Memória da operação</div>')
    st.subheader("Detalhes da simulação")

    item_preco, item_cambio, item_data = st.columns(3)

    with item_preco:
        st.caption("Preço unitário simulado")
        st.write(mostrar_faixa(variante, moeda_base))
        mostrar_referencia(variante, moeda_base)
        st.caption(f"Fonte do preço: {catalogo['fonte_preco']}")

    with item_cambio:
        st.caption("Cotação aplicada · API Frankfurter")
        if cambio:
            taxa = moeda(cambio["cotacao"], cambio["destino"], casas=4)
            st.write(f"{moeda(1, cambio['origem'])} = {taxa}")
        elif st.session_state.get("falha_cambio"):
            st.write("Consulta indisponível")
        else:
            st.write("Aguardando consulta")

    with item_data:
        st.caption("Data de referência do câmbio")
        st.write(data_cotacao(cambio) if cambio else "—")

    st.divider()

    frete, prazo = st.columns(2)
    frete.caption("Frete marítimo")
    frete.write("Cotação pendente")
    prazo.caption("Prazo entre portos")
    prazo.write("Aguardando estimativa")

    st.caption(
        "O subtotal inclui apenas a mercadoria. Frete, seguro, impostos "
        "e despesas portuárias estão fora do cálculo."
    )
