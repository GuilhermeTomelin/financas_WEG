from datetime import datetime
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from consumo.historico import listar


def limpar():
    for chave in ("periodo", "paises", "produtos"):
        st.session_state.pop(chave, None)


def exibir(moeda, faixa, numero):
    st.title("Relatórios de simulações")
    st.caption("Análise das operações salvas neste simulador")
    try:
        registros = listar()
    except (OSError, sqlite3.Error):
        st.error("Não foi possível abrir o histórico local. Confira o acesso à pasta dados.")
        return
    if not registros:
        st.info("Abra Simulador na lateral, calcule uma conversão e clique em Salvar simulação.")
        return

    for r in registros:
        r["local"] = datetime.fromisoformat(r["salvo"]).astimezone()
    datas = [r["local"].date() for r in registros]
    a, b, c = st.columns(3)
    periodo = a.date_input("Período de salvamento", (min(datas), max(datas)), key="periodo", format="DD/MM/YYYY")
    paises = b.multiselect("País", sorted({r["pais"] for r in registros}), key="paises")
    produtos = c.multiselect("Produto", sorted({r["produto"] for r in registros}), key="produtos")
    st.button("Limpar filtros", on_click=limpar)
    if len(periodo) != 2:
        st.info("Selecione o início e o fim do período.")
        return
    registros = [r for r in registros if periodo[0] <= r["local"].date() <= periodo[1]
                 and (not paises or r["pais"] in paises) and (not produtos or r["produto"] in produtos)]
    if not registros:
        st.info("Nenhuma simulação neste recorte. Use Limpar filtros para voltar.")
        return

    df = pd.DataFrame([{"País": r["pais"], "Produto": r["produto"], "Unidades": r["quantidade"],
                        "Simulações": 1, "Mínimo em BRL": r["subtotal"]["minimo"],
                        "Dia": r["local"].date().isoformat()} for r in registros])
    a, b, c = st.columns(3)
    a.metric("Simulações salvas", numero(len(df), 0))
    b.metric("Unidades simuladas", numero(df["Unidades"].sum(), 0))
    c.metric("Valor mínimo da mercadoria", moeda(df["Mínimo em BRL"].sum(), "BRL"))

    st.subheader("Destinos mais simulados")
    metrica = st.radio("Comparar por", ["Unidades", "Simulações", "Mínimo em BRL"], horizontal=True)
    grupo = df.groupby("País", as_index=False)[metrica].sum()
    grupo["Total"] = [moeda(x, "BRL") if metrica == "Mínimo em BRL" else numero(x, 0) for x in grupo[metrica]]
    st.altair_chart(alt.Chart(grupo, title=f"{metrica} por destino").mark_bar(color="#20D99A").encode(
        y=alt.Y("País:N", sort="-x"), x=alt.X(metrica, type="quantitative"),
        tooltip=["País", "Total"]), width="stretch")

    a, b = st.columns(2)
    with a:
        st.subheader("Participação por produto")
        tipos = df.groupby("Produto", as_index=False)["Unidades"].sum()
        tipos["Participação"] = [numero(n / tipos["Unidades"].sum() * 100, 1) + "%" for n in tipos["Unidades"]]
        st.altair_chart(alt.Chart(tipos).mark_arc(innerRadius=50).encode(
            theta="Unidades:Q", color="Produto:N", tooltip=["Produto","Unidades","Participação"]), width="stretch")
    with b:
        st.subheader("Valor simulado da mercadoria")
        valores = []
        for pais in grupo["País"]:
            faixas = [r["subtotal"] for r in registros if r["pais"] == pais]
            minimo = sum(f["minimo"] for f in faixas)
            maximo = None if any(f["maximo"] is None for f in faixas) else sum(f["maximo"] for f in faixas)
            valores.append({"País": pais, "Mínimo em BRL": minimo,
                            "Faixa": faixa({"minimo": minimo, "maximo": maximo}, "BRL")})
        st.altair_chart(alt.Chart(pd.DataFrame(valores)).mark_bar(color="#86B5EF").encode(
            x="País:N", y="Mínimo em BRL:Q", tooltip=["País","Faixa"]), width="stretch")
    st.subheader("Simulações por dia de salvamento")
    st.bar_chart(df.groupby("Dia")["Simulações"].sum(), color="#20D99A")

    st.subheader("Impacto da taxa negociada")
    elegiveis = [r for r in registros if r.get("comparacao")]
    if elegiveis:
        codigo = st.selectbox("Moeda da comparação", sorted({r["moeda"] for r in elegiveis}))
        linhas = [{"Operação": f"#{r['id']}", "Diferença": r["comparacao"]["diferenca"],
                   "Impacto": moeda(r["comparacao"]["diferenca"], codigo)}
                  for r in elegiveis if r["moeda"] == codigo]
        st.caption(f"{len(linhas)} operação(ões) · Subtotal mínimo · Taxa manual menos referência, em {codigo}")
        st.altair_chart(alt.Chart(pd.DataFrame(linhas)).mark_bar().encode(
            x="Operação:N", y=alt.Y("Diferença:Q", title=f"Diferença ({codigo})"),
            color=alt.condition("datum['Diferença'] < 0",alt.value("#ED908D"),alt.value("#20D99A")),
            tooltip=["Operação","Impacto"]), width="stretch")
    else:
        st.caption("Ative Comparar taxa negociada no simulador e salve uma operação com a taxa manual.")

    st.subheader("Histórico detalhado")
    st.dataframe([{"ID": r["id"], "Salvamento (local)": r["local"].strftime("%d/%m/%Y %H:%M"),
                   "Produto": r["produto"], "Variante": r["variante"], "Unidades": r["quantidade"],
                   "País": r["pais"], "Subtotal BRL": faixa(r["subtotal"], "BRL"),
                   "Subtotal convertido": faixa(r["convertido"], r["moeda"]), "Moeda": r["moeda"],
                   "Taxa": numero(r["cambio"]["cotacao"], 6)} for r in registros], hide_index=True)
    with st.expander("Consultar registro completo"):
        registro = st.selectbox("Simulação", registros, format_func=lambda r: f"#{r['id']} · {r['produto']} · {r['pais']}")
        st.json({k:v for k,v in registro.items() if k != "local"})
