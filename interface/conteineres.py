"""Calculadora didática: apresentação separada dos cálculos e das fontes."""
import streamlit as st
from consumo.catalogo import carregar_dados_simulador, ErroCatalogo
from consumo.conteineres import carregar_conteineres
from consumo.portos import garantir_selecao
from calculos.conteineres import calcular_conteineres, DadosLogisticosInvalidos
from interface.componentes import cabecalho, numero_br


def formato(valor, unidade="", casas=2):
    return "Não disponível" if valor is None else f"{numero_br(valor, casas)} {unidade}".strip()


def linhas_distribuicao(resultado):
    linhas=[]
    expandir=resultado["quantidade_avaliada"] <= 200
    for faixa in resultado["distribuicao"]:
        indices=range(faixa["primeiro"],faixa["ultimo"]+1) if expandir else [None]
        for indice in indices:
            rotulo=str(indice) if indice is not None else (str(faixa["primeiro"]) if faixa["primeiro"]==faixa["ultimo"] else f"{faixa['primeiro']} a {faixa['ultimo']} (mesma carga em cada um)")
            linhas.append({"Contêiner":rotulo,"Unidades de embarque":faixa["unidades_embarque"],
                           "Volume (m³)":formato(faixa["volume_m3"],casas=3),
                           "Peso bruto da carga (kg)":formato(faixa["peso_kg"]),
                           "Volume ocupado":formato(faixa["ocupacao_volumetrica_pct"],"%"),
                           "Carga útil utilizada":formato(faixa["utilizacao_carga_util_pct"],"%"),
                           "Posições utilizadas":formato(faixa["posicoes_utilizadas_pct"],"%"),
                           "Volume restante (m³)":formato(faixa["volume_restante_m3"],casas=3),
                           "Carga útil restante (kg)":formato(faixa["carga_util_restante_kg"])})
    return linhas


def exibir():
    cabecalho("Contêineres", "Estime peso, volume, ocupação e quantidade de equipamentos para uma única variante.", "OPERAÇÕES")
    st.caption("Estimativa por grade uniforme; não é plano certificado de estufagem nem avaliação de segurança operacional.")
    try:
        catalogo,_=carregar_dados_simulador()
        equipamentos=carregar_conteineres()
    except ErroCatalogo as erro:
        st.error(str(erro))
        return
    produtos={p["id"]:p for p in catalogo["produtos"]}
    def usar_simulador():
        selecionado=st.session_state.get("entrada_produto")
        if isinstance(selecionado,dict) and selecionado.get("id") in produtos:
            id_=selecionado["id"]
            st.session_state["conteiner_produto"]=id_
            variante=st.session_state.get(f"variante_{id_}")
            if isinstance(variante,dict):
                st.session_state[f"conteiner_variante_{id_}"]=variante["nome"]
            st.session_state["conteiner_quantidade"]=st.session_state.get("entrada_qtd",1)
    with st.container(border=True,key="card_entradas_conteiner"):
        st.subheader("Entradas da estimativa")
        if isinstance(st.session_state.get("entrada_produto"),dict):
            st.button("Reaproveitar seleção do simulador",on_click=usar_simulador,key="usar_selecao_simulador",icon=":material/input:")
        a,b,c=st.columns([1.3,1.6,1])
        garantir_selecao(st.session_state,"conteiner_produto",list(produtos))
        id_=a.selectbox("Produto",list(produtos),format_func=lambda i:produtos[i]["nome"],key="conteiner_produto")
        variantes={v["nome"]:v for v in produtos[id_]["variantes"]}
        garantir_selecao(st.session_state,f"conteiner_variante_{id_}",list(variantes))
        nome=b.selectbox("Variante",list(variantes),key=f"conteiner_variante_{id_}")
        quantidade=c.number_input("Quantidade de produtos",min_value=1,step=1,
                                  value=None if "conteiner_quantidade" in st.session_state else 1,key="conteiner_quantidade")
        a,b,c=st.columns(3)
        por_id={e["id"]:e for e in equipamentos}
        tipo=a.selectbox("Tipo de contêiner",list(por_id),format_func=lambda i:por_id[i]["nome"],key="conteiner_tipo")
        modo=b.selectbox("Modo de cálculo",["Estimar quantidade necessária","Avaliar quantidade informada"],key="conteiner_modo")
        manual=None
        if modo=="Avaliar quantidade informada":
            manual=c.number_input("Quantidade de contêineres",min_value=1,step=1,
                                  value=None if "conteiner_manual" in st.session_state else 1,key="conteiner_manual")
        else:
            c.caption("Os resultados acompanham as entradas automaticamente. Nenhum dado do catálogo é alterado.")
    variante=variantes[nome]
    try:
        # Não há cache de resultados: cada seleção usa exatamente as entradas atuais.
        comparacoes={e["id"]:calcular_conteineres(variante,quantidade,e,manual) for e in equipamentos}
    except DadosLogisticosInvalidos as erro:
        st.error(f"Não foi possível estimar esta carga. {erro}")
        st.info("Complete os dados logísticos necessários na base do catálogo. Informação desconhecida não é substituída por zero.")
        return
    resultado=comparacoes[tipo]
    carga=resultado["carga"]
    equipamento=por_id[tipo]
    with st.container(border=True,key="card_resumo_carga"):
        st.subheader("Resumo da carga")
        st.badge("Dados físicos simulados" if carga["natureza"]=="simulado" else "Consulte a origem dos dados físicos",color="violet")
        st.caption("Fonte física: " + str(variante["dados_fisicos"].get("fonte") or "Não informada"))
        a,b,c=st.columns(3)
        a.metric("Unidades de embarque",formato(carga["unidades_embarque"],casas=0))
        b.metric("Volume externo total",formato(carga["volume_total_m3"],"m³",3))
        c.metric("Peso bruto total da carga",formato(carga["peso_total_kg"],"kg"))
        dimensoes=" × ".join(formato(d,casas=2) for d in carga["dimensoes_cm"])
        st.write(f"**Por unidade de embarque:** {carga['produtos_por_unidade']} produto(s) · {dimensoes} cm (C × L × A) · {formato(carga['peso_unidade_kg'],'kg')} · {formato(carga['volume_unidade_m3'],'m³',4)}")
        embarque=variante["dados_fisicos"]["unidade_embarque"]
        st.caption(f"Embalagem: {embarque.get('tipo','Não informado')}. "+("Palete já incluído no peso e nas dimensões; não é somado novamente." if embarque['usa_palete'] else "Unidade sem palete adicional."))
        for aviso in carga["avisos"]:
            st.info(aviso)
    st.subheader("Resultado do equipamento selecionado")
    if not resultado["compativel"]:
        for motivo in resultado["motivos"]:
            st.error(motivo)
        st.warning("Sem quantidade finita estimada para este equipamento. Selecione outro tipo ou reveja os dados da unidade de embarque.")
    else:
        a,b,c,d=st.columns(4)
        a.metric("Capacidade por contêiner",formato(resultado["capacidade_final"],casas=0),help="Unidades de embarque, pelo menor limite aplicável.")
        b.metric("Contêineres necessários",formato(resultado["quantidade_necessaria"],casas=0))
        c.metric("Contêineres avaliados",formato(resultado["quantidade_avaliada"],casas=0))
        d.metric("Unidades não atendidas",formato(resultado["unidades_nao_atendidas"],casas=0))
        if resultado["atende"]:
            st.success("A quantidade avaliada atende ao lote pela grade e pelos limites cadastrados.")
        else:
            st.warning(f"Capacidade insuficiente: {resultado['unidades_nao_atendidas']} unidade(s) de embarque excedem a capacidade estimada. Os percentuais abaixo representam somente a carga alocada.")
        st.caption("Limites determinantes: "+", ".join(resultado["limites"])+". Peso bruto máximo do equipamento não é sua carga útil.")
        a,b,c=st.columns(3)
        a.metric("Ocupação volumétrica",formato(resultado["ocupacao_volumetrica_pct"],"%"))
        b.metric("Utilização da carga útil",formato(resultado["utilizacao_carga_util_pct"],"%"))
        c.metric("Posições de embarque utilizadas",formato(resultado["posicoes_utilizadas_pct"],"%"))
        st.caption(f"Saldo nos contêineres avaliados: {formato(resultado['volume_restante_m3'],'m³',3)} de volume e {formato(resultado['carga_util_restante_kg'],'kg')} de carga útil. Volume livre não significa espaço contíguo aproveitável.")
        st.subheader("Distribuição por contêiner")
        st.caption("Preenchimento sequencial: os primeiros recebem a capacidade estimada; o último pode ficar parcialmente ocupado. Embalagens ficam apoiadas em colunas, com camadas superiores apenas sobre unidades já apoiadas.")
        st.dataframe(linhas_distribuicao(resultado),hide_index=True,width="stretch")
        if resultado["quantidade_avaliada"]>200:
            st.caption("Faixas com carga idêntica foram agrupadas; os valores apresentados são de cada contêiner, não a soma da faixa. O último parcialmente ocupado permanece separado.")
    st.subheader("Comparação dos três tipos")
    st.caption("Mesma variante, lote, restrições e modo de cálculo. A ocupação usa a carga alocada nos contêineres avaliados, sem incluir o excedente. Não há comparação de preço ou frete.")
    st.dataframe([{"Equipamento":e["nome"],"Compatível": "Sim" if comparacoes[e["id"]]["compativel"] else "Não",
                   "Capacidade por contêiner":comparacoes[e["id"]]["capacidade_final"],
                   "Contêineres necessários":formato(comparacoes[e["id"]]["quantidade_necessaria"],casas=0),
                   "Atende ao lote": "Sim" if comparacoes[e["id"]]["atende"] else "Não",
                   "Volume ocupado":formato(comparacoes[e["id"]].get("ocupacao_volumetrica_pct"),"%"),
                   "Carga útil utilizada":formato(comparacoes[e["id"]].get("utilizacao_carga_util_pct"),"%"),
                   "Limite / motivo":", ".join(comparacoes[e["id"]]["limites"] or comparacoes[e["id"]]["motivos"])} for e in equipamentos],hide_index=True,width="stretch")
    with st.expander("Disposição, fontes e limitações",expanded=False):
        if resultado["disposicao"]:
            grade=resultado["disposicao"]
            st.write(f"**Grade escolhida:** {grade['no_comprimento']} no comprimento × {grade['na_largura']} na largura × {grade['camadas']} camada(s). Orientação: {grade['orientacao']}.")
            st.write("Dimensões orientadas (C × L × A): "+" × ".join(formato(v) for v in grade["dimensoes_cm"])+" cm.")
            st.write(f"Capacidade geométrica: {resultado['capacidade_geometrica']} unidades. Por carga útil: {resultado['capacidade_peso']} unidades. Capacidade final: {resultado['capacidade_final']} unidades.")
        st.write("Vertical mantém a altura original para cima e permite giro horizontal; invertida mantém o mesmo eixo vertical, com topo para baixo; lateral coloca comprimento ou largura na vertical. Somente posições cadastradas são avaliadas. A unidade inteira precisa atravessar a porta na mesma posição.")
        st.write("Grade uniforme com unidades retangulares iguais, sem mistura de orientações. Pode deixar espaços aproveitáveis por outros métodos; não é máximo global, garantia de carregamento ou avaliação de estabilidade, piso, amarração e manobra.")
        st.write("Ocupação volumétrica, utilização de carga útil e posições utilizadas são indicadores diferentes. Nenhum deles comprova distribuição segura de peso.")
        for e in equipamentos:
            st.markdown(f"**{e['nome']}** · {e['fonte']} · consulta em {e['consultado_em'][8:10]}/{e['consultado_em'][5:7]}/{e['consultado_em'][:4]}")
            dims=e["dimensoes_internas_cm"]
            st.caption("Internas: "+" × ".join(formato(dims[x]) for x in ("comprimento","largura","altura"))+" cm · Porta: "+" × ".join(formato(e["porta_cm"][x]) for x in ("largura","altura"))+f" cm · Tara {formato(e['tara_kg'],'kg')} · Peso bruto máximo {formato(e['peso_bruto_maximo_kg'],'kg')} · Carga útil {formato(e['carga_util_kg'],'kg')}")
            st.link_button("Consultar especificações · "+e["nome"],e["url"])
        st.caption(equipamento["observacao"])
