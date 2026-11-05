"""Estimativa de grade uniforme para unidades de embarque retangulares iguais."""
from decimal import Decimal, InvalidOperation
from consumo.logistica import validar_variante

D = Decimal
EIXOS = ("comprimento", "largura", "altura")


class DadosLogisticosInvalidos(ValueError):
    pass


def numero(valor, campo, zero=False):
    if type(valor) not in (int, float, Decimal):
        raise DadosLogisticosInvalidos(f"{campo}: informe um número {'não negativo' if zero else 'positivo'}.")
    try:
        n = D(str(valor))
    except InvalidOperation as erro:
        raise DadosLogisticosInvalidos(f"{campo}: número inválido.") from erro
    if not n.is_finite() or (n < 0 if zero else n <= 0):
        raise DadosLogisticosInvalidos(f"{campo}: número finito {'não negativo' if zero else 'positivo'} necessário.")
    return n


def inteiro(valor, campo):
    if type(valor) is not int or valor < 1:
        raise DadosLogisticosInvalidos(f"{campo}: informe um inteiro positivo.")
    return valor


def objeto(pai, campo):
    if not isinstance(pai, dict):
        raise DadosLogisticosInvalidos(f"{campo}: estrutura de dados inválida.")
    valor = pai.get(campo)
    if not isinstance(valor, dict):
        raise DadosLogisticosInvalidos(f"{campo}: dados não informados ou inválidos.")
    return valor


def volume_m3(dimensoes_cm):
    """C × L × A em cm³ convertido para m³, sem arredondamento intermediário."""
    c, l, a = (numero(v, "Dimensão em cm") for v in dimensoes_cm)
    return c * l * a / D(1000000)


def piso(espaco, unidade):
    return int(espaco // unidade)


def teto_divisao(total, capacidade):
    return (total + capacidade - 1) // capacidade


def validar_conteiner(conteiner):
    internas = objeto(conteiner, "dimensoes_internas_cm")
    dimensoes = tuple(numero(internas.get(e), f"Dimensão interna: {e} (cm)") for e in EIXOS)
    porta = objeto(conteiner, "porta_cm")
    abertura = tuple(numero(porta.get(e), f"Porta: {e} (cm)") for e in ("largura", "altura"))
    tara = numero(conteiner.get("tara_kg"), "Tara (kg)")
    bruto = numero(conteiner.get("peso_bruto_maximo_kg"), "Peso bruto máximo (kg)")
    util = numero(conteiner.get("carga_util_kg"), "Carga útil (kg)")
    if tara + util > bruto:
        raise DadosLogisticosInvalidos("Tara mais carga útil ultrapassa o peso bruto máximo do equipamento.")
    return dimensoes, abertura, util


def preparar_carga(variante, quantidade):
    inteiro(quantidade, "Quantidade de produtos")
    fisicos = objeto(variante, "dados_fisicos")
    embarque = objeto(fisicos, "unidade_embarque")
    if embarque.get("tipo") not in ("caixa", "engradado", "palete"):
        raise DadosLogisticosInvalidos("Esta etapa exige unidade de embarque retangular: caixa, engradado ou palete completo com dimensões externas confirmadas.")
    dim = objeto(embarque, "dimensoes_externas")
    dimensoes = tuple(numero(dim.get(e + "_cm"), f"Embalagem: {e} externo (cm)") for e in EIXOS)
    bruto = numero(embarque.get("peso_bruto_kg"), "Peso bruto da unidade de embarque (kg)")
    produtos = inteiro(embarque.get("quantidade_produtos"), "Produtos por unidade de embarque")
    if embarque.get("nivel_calculo") != "unidade_embarque":
        raise DadosLogisticosInvalidos("Defina a unidade de embarque completa como nível do cálculo.")
    for campo in ("usa_palete", "palete_incluido"):
        if type(embarque.get(campo)) is not bool:
            raise DadosLogisticosInvalidos(f"{campo}: confirme se há palete e se já está incluído.")
    if embarque["usa_palete"] != embarque["palete_incluido"]:
        raise DadosLogisticosInvalidos("Peso e dimensões do palete devem estar incluídos uma única vez na unidade completa.")
    if embarque.get("tipo") == "palete" and not embarque["usa_palete"]:
        raise DadosLogisticosInvalidos("Unidade do tipo palete exige confirmação de palete incluído.")
    produto = fisicos.get("produto")
    if produto is not None and not isinstance(produto, dict):
        raise DadosLogisticosInvalidos("Produto sem embalagem: estrutura de dados inválida.")
    liquido = (produto or {}).get("peso_liquido_kg")
    if liquido is not None and bruto < numero(liquido, "Peso líquido unitário (kg)") * produtos:
        raise DadosLogisticosInvalidos("Peso bruto inferior ao peso líquido de todos os produtos na embalagem.")
    pilha = objeto(fisicos, "empilhamento")
    orientacoes = pilha.get("orientacoes_permitidas")
    if (not isinstance(orientacoes, list) or not orientacoes
            or any(o not in ("vertical", "lateral", "invertida") for o in orientacoes)):
        raise DadosLogisticosInvalidos("Informe orientações permitidas: vertical, lateral e/ou invertida. Ausência não autoriza rotação.")
    restricoes = pilha.get("restricoes")
    if restricoes is not None and not isinstance(restricoes, str):
        raise DadosLogisticosInvalidos("Restrições de posição devem ser texto ou não informadas.")
    texto = (restricoes or "").casefold()
    if any(t in texto for t in ("não tombar", "na vertical", "em pé")) and any(o != "vertical" for o in orientacoes):
        raise DadosLogisticosInvalidos("Orientações contradizem a restrição explícita de transporte em pé.")
    permitido = pilha.get("permitido")
    if permitido is not None and type(permitido) is not bool:
        raise DadosLogisticosInvalidos("Permissão de empilhamento deve ser true, false ou desconhecida.")
    maximo = pilha.get("maximo_camadas")
    if maximo is not None:
        inteiro(maximo, "Máximo de camadas (incluindo o piso)")
    carga = pilha.get("carga_sobreposta_maxima_kg")
    if carga is not None:
        carga = numero(carga, "Carga suportada sobre a embalagem (kg)", zero=True)
    if permitido is False and ((maximo is not None and maximo != 1) or (carga is not None and carga != 0)):
        raise DadosLogisticosInvalidos("Empilhamento proibido contradiz camadas ou carga sobreposta declaradas.")
    if permitido is True and maximo == 1:
        raise DadosLogisticosInvalidos("Empilhamento permitido contradiz máximo de uma camada.")
    avisos = []
    if permitido is not True:
        limite_camadas = 1
        if permitido is None:
            avisos.append("Empilhamento desconhecido: adotada somente a camada apoiada no piso.")
    else:
        if maximo is None or carga is None:
            limite_camadas = 1
            avisos.append("Limite de camadas ou carga suportada desconhecido: adotada somente uma camada, sem autorizar empilhamento.")
        else:
            limite_camadas = min(maximo, 1 + piso(carga, bruto))
            if limite_camadas < maximo:
                avisos.append("O limite de carga sobre a embalagem reduz o número de camadas informado.")
    if not restricoes:
        avisos.append("Restrições adicionais não informadas; foram usadas somente as orientações explicitamente cadastradas.")
    unidades = teto_divisao(quantidade, produtos)
    parcial = quantidade % produtos != 0
    if parcial:
        avisos.append("Última embalagem parcial: considerados peso bruto e dimensões de uma embalagem completa, sem redução proporcional.")
    return dict(quantidade_produtos=quantidade, produtos_por_unidade=produtos,
                unidades_embarque=unidades, embalagem_parcial=parcial,
                produtos_ultima_embalagem=quantidade % produtos or produtos,
                dimensoes_cm=dimensoes, peso_unidade_kg=bruto,
                volume_unidade_m3=volume_m3(dimensoes), volume_total_m3=unidades * volume_m3(dimensoes),
                peso_total_kg=unidades * bruto, limite_camadas=limite_camadas,
                orientacoes=orientacoes, avisos=avisos, natureza=fisicos.get("natureza"),
                validacao_catalogo=validar_variante(variante))


def orientacoes_dimensoes(dimensoes, permitidas):
    """Vertical/invertida: H no eixo Z, com giro horizontal. Lateral: C ou L em Z.

    Cada candidato mantém a mesma orientação em todas as posições. Não combina
    orientações nem permite manobras para atravessar a porta em outra posição.
    """
    c, l, a = dimensoes
    candidatos = {
        "vertical": ((c,l,a),(l,c,a)),
        "invertida": ((c,l,a),(l,c,a)),
        "lateral": ((c,a,l),(a,c,l),(l,a,c),(a,l,c)),
    }
    for nome in ("vertical", "invertida", "lateral"):
        if nome in permitidas:
            for dimensoes in candidatos[nome]:
                yield nome, dimensoes


def avaliar_grade(carga, internas, porta, orientacoes, verificar_porta=True):
    candidatas = []
    for nome, dimensoes in orientacoes_dimensoes(carga["dimensoes_cm"], orientacoes):
        c, l, a = dimensoes
        nx, ny, altura = (piso(espaco, tamanho) for espaco, tamanho in zip(internas, dimensoes))
        if not nx or not ny or not altura:
            continue
        if verificar_porta and (l > porta[0] or a > porta[1]):
            continue
        camadas = min(altura, carga["limite_camadas"])
        candidatas.append(dict(orientacao=nome, dimensoes_cm=dimensoes,
                               no_comprimento=nx, na_largura=ny, camadas=camadas,
                               camadas_pela_altura=altura, capacidade_geometrica=nx*ny*camadas))
    return candidatas


def distribuir(unidades, quantidade_conteineres, capacidade, carga, volume_interno, carga_util):
    """Faixas de contêineres com carga idêntica, sem criar listas gigantes.

    A última carga parcial é sempre uma linha separada. Volume/peso são POR
    contêiner da faixa; multiplicar por quantidade_conteineres para os totais.
    """
    carregadas = min(unidades, quantidade_conteineres * capacidade)
    cheios, resto = divmod(carregadas, capacidade)
    faixas = []
    if cheios:
        faixas.append((1, cheios, capacidade))
    if resto:
        faixas.append((cheios+1, cheios+1, resto))
    inicio_vazios = cheios + bool(resto) + 1
    if inicio_vazios <= quantidade_conteineres:
        faixas.append((inicio_vazios, quantidade_conteineres, 0))
    linhas = []
    for inicio, fim, qtd in faixas:
        volume, peso = qtd*carga["volume_unidade_m3"], qtd*carga["peso_unidade_kg"]
        linhas.append(dict(primeiro=inicio, ultimo=fim, quantidade_conteineres=fim-inicio+1,
                           unidades_embarque=qtd, volume_m3=volume, peso_kg=peso,
                           ocupacao_volumetrica_pct=volume/volume_interno*100,
                           utilizacao_carga_util_pct=peso/carga_util*100,
                           posicoes_utilizadas_pct=D(qtd)/capacidade*100,
                           volume_restante_m3=volume_interno-volume, carga_util_restante_kg=carga_util-peso))
    return carregadas, linhas


def calcular_conteineres(variante, quantidade, conteiner, quantidade_manual=None):
    if quantidade_manual is not None:
        inteiro(quantidade_manual, "Quantidade de contêineres")
    carga = preparar_carga(variante, quantidade)
    internas, porta, util = validar_conteiner(conteiner)
    volume = volume_m3(internas)
    por_peso = piso(util, carga["peso_unidade_kg"])
    candidatas = avaliar_grade(carga, internas, porta, carga["orientacoes"])
    base = dict(carga=carga, conteiner_id=conteiner.get("id"), volume_interno_m3=volume,
                carga_util_kg=util, capacidade_peso=por_peso, alternativas=candidatas)
    if not candidatas or por_peso == 0:
        motivos=[]
        sem_porta=avaliar_grade(carga, internas, porta, carga["orientacoes"], verificar_porta=False)
        if not sem_porta:
            motivos.append("Unidade de embarque incompatível com as dimensões internas nas orientações permitidas.")
        elif not candidatas:
            motivos.append("Unidade de embarque incompatível com a abertura da porta na posição avaliada.")
        if por_peso == 0:
            motivos.append("Peso bruto de uma unidade de embarque supera a carga útil do contêiner.")
        return dict(base, compativel=False, motivos=motivos, capacidade_final=0,
                    capacidade_geometrica=max((c["capacidade_geometrica"] for c in candidatas), default=0),
                    quantidade_necessaria=None, quantidade_avaliada=quantidade_manual,
                    atende=False, unidades_nao_atendidas=carga["unidades_embarque"],
                    unidades_carregadas=0, distribuicao=[], disposicao=None, limites=[])
    # A carga útil é igual para todos os candidatos; maior grade maximiza a
    # capacidade final. No empate, prefere menos camadas, depois a ordem acima.
    melhor=max(candidatas,key=lambda c:(c["capacidade_geometrica"], -c["camadas"]))
    geometria=melhor["capacidade_geometrica"]
    capacidade=min(geometria,por_peso)
    limites=[]
    if capacidade==por_peso:
        limites.append("peso")
    if capacidade==geometria:
        limites.append("geometria")
        if melhor["camadas"] < melhor["camadas_pela_altura"]:
            limites.append("empilhamento")
        irrestritas=avaliar_grade(carga,internas,porta,("vertical","lateral","invertida"))
        if max((c["capacidade_geometrica"] for c in irrestritas),default=0)>geometria:
            limites.append("orientação")
        sem_porta=avaliar_grade(carga,internas,porta,carga["orientacoes"],verificar_porta=False)
        if max(c["capacidade_geometrica"] for c in sem_porta)>geometria:
            limites.append("porta")
    necessaria=teto_divisao(carga["unidades_embarque"],capacidade)
    avaliada=quantidade_manual if quantidade_manual is not None else necessaria
    carregadas,distribuicao=distribuir(carga["unidades_embarque"],avaliada,capacidade,carga,volume,util)
    return dict(base, compativel=True, motivos=[], capacidade_geometrica=geometria,
                capacidade_final=capacidade, quantidade_necessaria=necessaria,
                quantidade_avaliada=avaliada, atende=carregadas==carga["unidades_embarque"],
                unidades_carregadas=carregadas, unidades_nao_atendidas=carga["unidades_embarque"]-carregadas,
                distribuicao=distribuicao, disposicao=melhor, limites=limites,
                ocupacao_volumetrica_pct=carregadas*carga["volume_unidade_m3"]/(avaliada*volume)*100,
                utilizacao_carga_util_pct=carregadas*carga["peso_unidade_kg"]/(avaliada*util)*100,
                posicoes_utilizadas_pct=D(carregadas)/(avaliada*capacidade)*100,
                volume_restante_m3=avaliada*volume-carregadas*carga["volume_unidade_m3"],
                carga_util_restante_kg=avaliada*util-carregadas*carga["peso_unidade_kg"])
