import math
import sqlite3
from uuid import uuid4
from consumo.historico import salvar
from datetime import date
from html import escape

import streamlit as st

from calculos.operacoes import calcular_subtotal_faixa, converter_faixa
from consumo.cambio import ErroCambio, consultar_cotacao, MOEDAS_SUPORTADAS, atualizar_cotacoes, obter_cache_sessao
from consumo.catalogo import ErroCatalogo, carregar_dados_simulador
from consumo.logistica import validar_variante
from consumo.conteineres import carregar_conteineres
from consumo.fretes import carregar_fretes, buscar_tarifa
from calculos.fretes import cenario_compativel, serializar, assinatura_contexto
from calculos.consolidacao import consolidar_operacao
from calculos.cambio import ConjuntoCotacoes
from calculos.monetario import decimal
from interface.conversao import exibir_consolidacao
from interface.resumo_logistico import exibir_resumo, texto_faixa
from consumo.portos import (carregar_portos, nome_pais, rotulo_porto, buscar_portos,
                            garantir_selecao, invalidar_resultado, consultar_rota, dados_localidade)


from interface.componentes import (numero_br, moeda, mostrar_faixa, mostrar_referencia, data_cotacao, cabecalho, dados_logisticos)

def exibir():
    try:
        catalogo, rotas = carregar_dados_simulador()
        base_portos, navegacao = carregar_portos()
        equipamentos = {c["id"]:c for c in carregar_conteineres()}
    except ErroCatalogo as erro:
        st.error(str(erro))
        return
    obter_cache_sessao(st.session_state)
    moeda_base = catalogo["moeda"]
    cabecalho("Simulador", "Monte a operação e compare o valor da mercadoria em outra moeda.", "OPERAÇÕES")

    lateral, principal = st.columns([1.15, 1], gap="large")

    with lateral.container(key="controles", border=True):
        st.html('<div class="rotulo">Configuração</div>')
        st.subheader("Montar operação")

        aba_mercadoria, aba_trajeto = st.tabs(["Mercadoria", "Trajeto e moeda"])
        with aba_mercadoria:
            st.markdown("#### Mercadoria")
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
            quantidade = st.number_input("Quantidade", min_value=1, value=None if "entrada_qtd" in st.session_state else 1, step=1, key="entrada_qtd")

        def selecionar_porto(lado, iso):
            busca = st.text_input(f"Buscar porto de {lado} por nome ou código", key=f"entrada_busca_{lado}_{iso}")
            favoritos = st.session_state.setdefault("favoritos_portos", list(navegacao["favoritos"]))
            opcoes = buscar_portos(base_portos, iso, busca, favoritos)
            if not opcoes:
                st.info("Nenhuma localidade encontrada. Limpe ou altere a busca.")
                invalidar_resultado(st.session_state, None)
                st.stop()
            codigos = [p["unlocode"] for p in opcoes]
            chave = f"entrada_porto_{lado}"
            padrao = navegacao["paises"].get(iso, {}).get("porto_padrao")
            garantir_selecao(st.session_state, chave, codigos, padrao)
            codigo = st.selectbox(f"Porto de {lado}", codigos, key=chave,
                                  format_func=lambda c: ("★ " if c in favoritos else "") + rotulo_porto(base_portos["portos"][c]))
            def alternar_favorito():
                lista = st.session_state["favoritos_portos"]
                if codigo in lista:
                    lista.remove(codigo)
                else:
                    lista.append(codigo)
            st.button("Remover dos favoritos" if codigo in favoritos else "Destacar como favorito",
                      key=f"favorito_{lado}", on_click=alternar_favorito)
            return codigo

        with aba_trajeto:
            st.markdown("#### Origem e destino")
            origem_iso = st.selectbox("País de origem", ["BR"], key="entrada_origem_iso",
                                     format_func=lambda iso: f"{nome_pais(base_portos, navegacao, iso)} · {iso}")
            origem_codigo = selecionar_porto("origem", origem_iso)
            opcoes_paises = [iso for iso in base_portos["paises"] if iso != origem_iso]
            opcoes_paises.sort(key=lambda iso: (iso not in navegacao["paises"], nome_pais(base_portos, navegacao, iso)))
            garantir_selecao(st.session_state, "entrada_destino_iso", opcoes_paises, navegacao["destino_padrao"][:2])
            destino_iso = st.selectbox("País de destino", opcoes_paises, key="entrada_destino_iso",
                                      format_func=lambda iso: f"{nome_pais(base_portos, navegacao, iso)} · {iso}")
            destino_codigo = selecionar_porto("destino", destino_iso)
            origem = dados_localidade(base_portos, navegacao, origem_codigo)
            destino = dados_localidade(base_portos, navegacao, destino_codigo)
            pais = destino["pais"]
            moeda_local = destino["moeda"]
            if st.session_state.get("pais_moeda_atual") != destino_iso:
                st.session_state["pais_moeda_atual"] = destino_iso
                st.session_state["entrada_moeda_apresentacao"] = moeda_local if moeda_local in MOEDAS_SUPORTADAS else "USD"
            if moeda_local is None:
                st.caption("Moeda local não configurada para este país. Escolha a moeda de apresentação.")
            elif moeda_local not in MOEDAS_SUPORTADAS:
                st.warning(f"Moeda local {moeda_local} não suportada pelo aplicativo. Escolha uma moeda suportada.")
            garantir_selecao(st.session_state, "entrada_moeda_apresentacao", list(MOEDAS_SUPORTADAS), "USD")
            st.divider()
            st.markdown("#### Apresentação do resultado")
            moeda_destino = st.selectbox("Moeda de apresentação", MOEDAS_SUPORTADAS, key="entrada_moeda_apresentacao")
            garantir_selecao(st.session_state, "entrada_tipo_conteiner", list(equipamentos), st.session_state.get("conteiner_tipo", "dry20"))
            tipo_conteiner = st.selectbox("Tipo de contêiner para logística", list(equipamentos), format_func=lambda i:equipamentos[i]["nome"], key="entrada_tipo_conteiner")
        rota = f"{origem['porto']} ({origem_codigo}) → {destino['porto']} ({destino_codigo})"
        rota_comercial = consultar_rota(navegacao, origem_codigo, destino_codigo)
        invalidar_resultado(st.session_state, (produto["id"], variante["nome"], quantidade,
                                              origem_codigo, destino_codigo, moeda_destino, tipo_conteiner))
        st.caption(f"Trajeto selecionado · {rota}")
        st.caption("Localidade portuária cadastrada não comprova terminal de contêineres ou serviço comercial.")

        calcular = st.button(
            "Calcular conversão",
            type="primary",
            width="stretch",
        )

    subtotal = calcular_subtotal_faixa(variante, quantidade)
    logistica = cenario_compativel(st.session_state.get("logistica_ativa"), produto["id"], variante, quantidade,
                                  origem_codigo, destino_codigo, tipo_conteiner, moeda_destino)

    # A moeda pode mudar mantendo despesas de um contexto físico idêntico.
    if logistica is None:
        ativa=st.session_state.get("logistica_ativa")
        antiga=(ativa or {}).get("entradas",{}).get("moeda")
        if antiga:
            logistica=cenario_compativel(ativa,produto["id"],variante,quantidade,origem_codigo,destino_codigo,tipo_conteiner,antiga)
    cotacoes=obter_cache_sessao(st.session_state)
    def calcular_conjunto(taxas):
        return consolidar_operacao(variante,quantidade,moeda_base,moeda_destino,taxas,
                                    logistica=logistica["entradas"] if logistica else None)
    consolidacao=calcular_conjunto(list(cotacoes.values()))
    if calcular:
        with st.spinner("Consultando a Frankfurter…"):
            cotacoes,consolidacao,erros=atualizar_cotacoes(calcular_conjunto,consultar_cotacao)
            st.session_state["cotacoes_sessao"]=cotacoes
            if erros:
                st.session_state["falha_cambio"]=True
                for erro in erros:
                    st.warning(erro)
            else:
                st.session_state.pop("falha_cambio",None)
    cambio=consolidacao["itens"][0]["taxas"][moeda_destino]
    if calcular:
        if cambio:
            st.session_state["cambio_simulador"]=cambio
        else:
            st.session_state.pop("cambio_simulador",None)
    if logistica:
        logistica["entradas"]["moeda"]=moeda_destino
        logistica["entradas"]["cotacoes"]=serializar(list(cotacoes.values()))
        logistica.update(assinatura=assinatura_contexto(produto["id"],variante,quantidade,origem_codigo,destino_codigo,tipo_conteiner,moeda_destino),
                         resultado=serializar(consolidacao["resultado_logistica"]),consolidacao=serializar(consolidacao))
        st.session_state["logistica_ativa"]=logistica

    with principal.container(key="resumo", border=True):
        st.html('<div class="rotulo">Resumo da operação</div>')
        st.subheader(produto["nome"])
        st.caption(f"{variante['nome']} · {numero_br(quantidade, 0)} un.")
        st.html(f'<span class="rota">{escape(rota)} · {escape(moeda_destino)}</span>')
        st.divider()

        if cambio:
            faixa_destaque = consolidacao["itens"][0]["convertidos"][moeda_destino]
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
            if moeda_destino != moeda_base:
                st.divider()
                st.html("<p><strong>Subtotal em BRL:</strong> " + escape(mostrar_faixa(subtotal, moeda_base)) + "</p>")
                mostrar_referencia(subtotal, moeda_base)
            else:
                st.caption("Mesma moeda: fator 1 local, sem consulta externa.")
        elif st.session_state.get("falha_cambio"):
            st.warning(
                "Cotação indisponível. Clique em Calcular conversão para tentar novamente."
            )
        else:
            st.caption("Clique em Calcular conversão para consultar o câmbio.")

    exibir_consolidacao(consolidacao, compacto=True)

    with principal.container(border=True, key="card_logistica_simulador"):
        st.subheader("Logística selecionada")
        if logistica:
            exibir_resumo(logistica["resultado"], compacto=True)
        else:
            st.info("Nenhum cenário logístico compatível com produto, lote, portos, equipamento e moeda atuais. Configure-o em Fretes e rotas.")
        st.page_link("paginas/rotas.py", label="Configurar frete e despesas", icon=":material/route:")

    with principal:
        comparacao = None
        valido = bool(cambio)
        if cambio:
            with st.expander("Comparar taxa negociada"):
                if st.checkbox("Usar taxa manual", key=f"entrada_comparar_{moeda_destino}"):
                    manual = st.number_input(f"Quantos {moeda_destino} correspondem a 1 BRL?",
                                             value=None, format="%.6f", key=f"entrada_taxa_{moeda_destino}")
                    valido = manual is not None and math.isfinite(manual) and manual > 0
                    if valido:
                        negociado = converter_faixa(subtotal, manual, moeda_destino)
                        diferenca = negociado["minimo"] - faixa_destaque["minimo"]
                        percentual = (decimal(manual,"Taxa manual") / decimal(cambio["cotacao"],"Cotação") - 1) * 100
                        comparacao = dict(taxa=manual, negociado=negociado, diferenca=diferenca,
                                          percentual=percentual, cotacao_manual=dict(origem=moeda_base,destino=moeda_destino,cotacao=manual,metodo="manual",provedor="Usuário",fonte="Informado manualmente para comparação; não substitui o conjunto automático",data_referencia=None,consultado_em=None))
                        st.write("Referência", mostrar_faixa(faixa_destaque, moeda_destino))
                        st.write("Hipótese negociada", mostrar_faixa(negociado, moeda_destino))
                        st.caption(f"Impacto sobre o mínimo: {moeda(diferenca, moeda_destino)} "
                                   f"({numero_br(percentual)}%).")
                    else:
                        st.caption("Informe uma taxa positiva para comparar e salvar.")

        operacao = dict(produto_id=produto["id"], produto=produto["nome"], categoria=produto["categoria"],
                        variante=variante["nome"], quantidade=quantidade, origem=origem, pais=pais, pais_iso=destino_iso,
                        origem_unlocode=origem_codigo, destino_unlocode=destino_codigo, rota_comercial=rota_comercial,
                        destino=destino, moeda=moeda_destino, moeda_base=moeda_base, unitario=variante,
                        subtotal=subtotal, convertido=faixa_destaque, cambio=cambio, fonte_cambio=cambio.get("provedor") if cambio else None,
                        tipo_preco="simulado", fonte_preco=catalogo["fonte_preco"], comparacao=comparacao,
                        tipo_conteiner=tipo_conteiner, logistica=logistica, consolidacao=consolidacao)
        operacao=serializar(operacao)
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
            st.caption("Cotação aplicada · " + (cambio.get("provedor", "Metadados legados") if cambio else "Referência indisponível"))
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
        if logistica:
            item_frete = logistica["resultado"].get("frete_maritimo")
            frete.text(texto_faixa(item_frete["total_original"], item_frete["moeda"]) if item_frete else "Frete não incluído no escopo")
        else:
            try:
                tarifa_disponivel = buscar_tarifa(carregar_fretes(), origem_codigo, destino_codigo, tipo_conteiner)
                frete.write("Tarifa simulada disponível; configure as despesas em Fretes e rotas." if tarifa_disponivel else "Frete indisponível para esta rota")
            except ErroCatalogo:
                frete.write("Configuração de tarifas indisponível; o subtotal da mercadoria permanece disponível.")
        prazo.caption("Prazo entre portos")
        prazo.write("Prazo indisponível para esta rota" if not rota_comercial or rota_comercial.get("prazo") is None
                    else rota_comercial["prazo"])

        st.caption(
            "O subtotal da mercadoria e as despesas logísticas são apresentados separadamente. "
            "Impostos ainda não estão implementados; os valores não são um custo completo ao cliente."
        )



    with st.expander("Custo de origem e dados logísticos da variante"):
        dados_logisticos(variante)
