"""Apresentação compartilhada; cálculos e validações permanecem na camada original."""
from datetime import date
from html import escape
import streamlit as st
from consumo.logistica import validar_variante

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



def cabecalho(titulo, descricao, grupo="VISÃO GERAL"):
    st.html(f'<div class="rotulo">{escape(grupo)} / FINANÇAS WEG</div>')
    st.title(titulo)
    st.caption(descricao)


def estado(titulo, descricao, planejado=False):
    with st.container(border=True):
        st.badge("Planejado" if planejado else "Comece por aqui", icon=":material/schedule:" if planejado else ":material/info:", color="violet" if planejado else "blue")
        st.subheader(titulo)
        st.write(descricao)


def dados_logisticos(variante):
    st.caption("Dados físicos simulados pelo projeto para demonstração; não são especificações oficiais WEG.")
    avisos = validar_variante(variante)
    custo_pendente = variante.get("custo_origem") or {}
    apenas_custo_pendente = custo_pendente.get("natureza") == "nao_informado" and custo_pendente.get("minimo") is None and custo_pendente.get("maximo") is None
    if apenas_custo_pendente:
        st.info("Custo de origem não informado. O preço de venda não substitui o custo de fabricação ou compra.")
        avisos = [a for a in avisos if not a.startswith(("custo_origem.", "tipo:"))]
    if avisos:
        st.warning("Há pendências ou inconsistências nos dados adicionais. O subtotal e a conversão continuam disponíveis.")
        for aviso in avisos:
            st.caption(aviso)

    def objeto_logistico(pai, chave):
        valor = pai.get(chave)
        return valor if isinstance(valor, dict) else {}

    def valor_logistico(valor, unidade=""):
        if valor is None:
            return "Não informado"
        if isinstance(valor, str):
            valor = {"nao_informado": "Não informado", "simulado": "Simulado", "real": "Real",
                     "fabricacao": "Fabricação", "compra": "Compra",
                     "caixa_envolvente_aproximada": "Caixa envolvente aproximada", "retangular": "Retangular"}.get(valor, valor)
        if type(valor) in (int, float):
            valor = numero_br(valor, 0 if float(valor).is_integer() else 2)
        return f"{valor} {unidade}".strip()

    def dimensoes_logisticas(valor):
        return " × ".join(valor_logistico(valor.get(eixo)) for eixo in
                          ("comprimento_cm", "largura_cm", "altura_cm")) + " cm (C × L × A)"

    custo = objeto_logistico(variante, "custo_origem")
    fisicos = objeto_logistico(variante, "dados_fisicos")
    item = objeto_logistico(fisicos, "produto")
    embarque = objeto_logistico(fisicos, "unidade_embarque")
    pilha = objeto_logistico(fisicos, "empilhamento")
    st.write("**Custo de origem unitário · separado do preço de venda**")
    st.write(f"Tipo: {valor_logistico(custo.get('tipo'))} · Natureza: {valor_logistico(custo.get('natureza'))}")
    st.write(f"Mínimo: {valor_logistico(custo.get('minimo'), custo.get('moeda') or '')} · "
             f"Máximo: {valor_logistico(custo.get('maximo'), custo.get('moeda') or '')}")
    st.caption(f"Fonte do custo: {valor_logistico(custo.get('fonte'))} · Data: {valor_logistico(custo.get('data_referencia'))}")
    a, b = st.columns(2)
    with a:
        st.write("**Produto sem embalagem**")
        st.write(f"Peso líquido unitário: {valor_logistico(item.get('peso_liquido_kg'), 'kg')}")
        st.write(dimensoes_logisticas(objeto_logistico(item, 'dimensoes')))
        st.caption(f"Formato das dimensões: {valor_logistico(item.get('tipo_dimensoes'))}")
        st.write("**Unidade de embarque completa**")
        st.write(f"Tipo: {valor_logistico(embarque.get('tipo'))} · Produtos por unidade: {valor_logistico(embarque.get('quantidade_produtos'))}")
        st.write(dimensoes_logisticas(objeto_logistico(embarque, 'dimensoes_externas')))
        st.write(f"Peso bruto completo: {valor_logistico(embarque.get('peso_bruto_kg'), 'kg')}")
        booleanos = {True: "Sim", False: "Não", None: "Não informado"}
        st.caption(f"Usa palete: {booleanos.get(embarque.get('usa_palete'), 'Inválido')} · "
                   f"Palete incluído no peso e nas dimensões: {booleanos.get(embarque.get('palete_incluido'), 'Inválido')}")
    with b:
        st.write("**Empilhamento da unidade de embarque**")
        st.write(f"Permitido: {booleanos.get(pilha.get('permitido'), 'Inválido')}")
        st.write(f"Máximo de camadas, incluindo o piso: {valor_logistico(pilha.get('maximo_camadas'))}")
        orientacoes = pilha.get('orientacoes_permitidas')
        st.write("Orientações: " + (", ".join(map(str, orientacoes)) if isinstance(orientacoes, list) and orientacoes else "Não informado"))
        st.write(f"Restrições: {valor_logistico(pilha.get('restricoes'))}")
        st.write(f"Carga máxima sobre a embalagem: {valor_logistico(pilha.get('carga_sobreposta_maxima_kg'), 'kg')}")
    st.caption(f"Origem dos dados físicos: {valor_logistico(fisicos.get('natureza'))} · "
               f"{valor_logistico(fisicos.get('fonte'))} · Data: {valor_logistico(fisicos.get('data_referencia'))}")
    st.caption("A unidade de embarque completa é o nível previsto para acomodação. Não adicionar outro palete. Informação desconhecida não autoriza empilhar ou girar.")
