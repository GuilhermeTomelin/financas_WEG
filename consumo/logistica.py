"""Validação não bloqueante de dados adicionais; null nunca autoriza operação."""
import math
from datetime import date


def validar_variante(variante):
    """Retorna mensagens de campos inválidos ou pendentes sem alterar a variante.

    Não valida nem modifica o preço de venda legado. Consumidores logísticos
    devem resolver as mensagens antes de usar os dados para acomodação real.
    """
    mensagens = []

    def aviso(campo, texto):
        mensagens.append(f"{campo}: {texto}")

    def objeto(pai, chave):
        valor = pai.get(chave)
        if not isinstance(valor, dict):
            aviso(chave, "não informado ou inválido; informe um objeto.")
            return {}
        return valor

    def numero(valor, campo, zero=False, inteiro=False):
        if valor is None:
            aviso(campo, "não informado.")
            return False
        if (type(valor) not in (int, float) or not math.isfinite(valor)
                or (valor < 0 if zero else valor <= 0)
                or (inteiro and type(valor) is not int)):
            aviso(campo, "deve ser inteiro positivo." if inteiro else
                  "deve ser número finito não negativo." if zero else "deve ser número finito positivo.")
            return False
        return True

    def escolha(obj, campo, opcoes):
        valor = obj.get(campo)
        if valor not in opcoes:
            aviso(campo, "não informado ou inválido.")

    def origem(obj, campo):
        escolha(obj, "natureza", ("real", "simulado", "nao_informado"))
        fonte = obj.get("fonte")
        if obj.get("natureza") != "nao_informado" and (not isinstance(fonte, str) or not fonte.strip()):
            aviso(campo + ".fonte", "informe a origem independente do preço de venda.")
        data = obj.get("data_referencia")
        if data is not None:
            try:
                date.fromisoformat(data)
            except (TypeError, ValueError):
                aviso(campo + ".data_referencia", "use uma data ISO AAAA-MM-DD ou null.")

    custo = objeto(variante, "custo_origem")
    origem(custo, "custo_origem")
    escolha(custo, "tipo", ("fabricacao", "compra"))
    moeda = custo.get("moeda")
    if not isinstance(moeda, str) or len(moeda) != 3 or not moeda.isascii() or not moeda.isupper() or not moeda.isalpha():
        aviso("custo_origem.moeda", "informe código de moeda com três letras, como BRL.")
    minimo, maximo = custo.get("minimo"), custo.get("maximo")
    baixo = numero(minimo, "custo_origem.minimo", zero=True)
    alto = numero(maximo, "custo_origem.maximo", zero=True) if maximo is not None else False
    if baixo and alto and minimo > maximo:
        aviso("custo_origem", "mínimo não pode superar máximo.")
    if custo.get("natureza") == "nao_informado" and (minimo is not None or maximo is not None):
        aviso("custo_origem.natureza", "custo preenchido exige natureza real ou simulado.")

    fisicos = objeto(variante, "dados_fisicos")
    origem(fisicos, "dados_fisicos")
    produto = objeto(fisicos, "produto")
    embarque = objeto(fisicos, "unidade_embarque")
    pilha = objeto(fisicos, "empilhamento")
    liquido = produto.get("peso_liquido_kg")
    bruto = embarque.get("peso_bruto_kg")
    qtd = embarque.get("quantidade_produtos")
    ok_liquido = numero(liquido, "peso_liquido_kg")
    ok_bruto = numero(bruto, "peso_bruto_kg")
    ok_qtd = numero(qtd, "quantidade_produtos", inteiro=True)
    if ok_liquido and ok_bruto and ok_qtd and bruto < liquido * qtd:
        aviso("peso_bruto_kg", "não pode ser menor que quantidade × peso líquido unitário.")
    for pai, chave in ((produto, "dimensoes"), (embarque, "dimensoes_externas")):
        dims = objeto(pai, chave)
        for eixo in ("comprimento_cm", "largura_cm", "altura_cm"):
            numero(dims.get(eixo), chave + "." + eixo)
    escolha(produto, "tipo_dimensoes", ("caixa_envolvente_aproximada", "retangular"))
    escolha(embarque, "tipo", ("caixa", "engradado", "palete", "outra"))
    escolha(embarque, "nivel_calculo", ("unidade_embarque",))
    for campo in ("usa_palete", "palete_incluido"):
        if type(embarque.get(campo)) is not bool:
            aviso(campo, "não informado; informe true ou false.")
    if embarque.get("usa_palete") is True and embarque.get("palete_incluido") is not True:
        aviso("palete_incluido", "inclua peso e dimensões do palete na unidade completa antes de calcular.")
    if embarque.get("usa_palete") is False and embarque.get("palete_incluido") is True:
        aviso("palete_incluido", "contradiz usa_palete=false.")
    if embarque.get("tipo") == "palete" and embarque.get("usa_palete") is not True:
        aviso("usa_palete", "tipo palete exige usa_palete=true.")

    permitido = pilha.get("permitido")
    camadas = pilha.get("maximo_camadas")
    carga = pilha.get("carga_sobreposta_maxima_kg")
    if type(permitido) is not bool:
        aviso("empilhamento.permitido", "não informado; não autoriza empilhar.")
    ok_camadas = numero(camadas, "maximo_camadas", inteiro=True)
    ok_carga = numero(carga, "carga_sobreposta_maxima_kg", zero=True)
    if ok_camadas and ((permitido is False and camadas != 1) or (permitido is True and camadas < 2)):
        aviso("maximo_camadas", "contradiz a permissão de empilhamento; o piso conta como camada 1.")
    if permitido is False and ok_carga and carga != 0:
        aviso("carga_sobreposta_maxima_kg", "empilhamento proibido exige carga sobreposta zero ou desconhecida.")
    if permitido is True and ok_camadas and ok_carga and ok_bruto and carga < (camadas - 1) * bruto:
        aviso("carga_sobreposta_maxima_kg", "insuficiente para as camadas declaradas de unidades iguais.")
    orientacoes = pilha.get("orientacoes_permitidas")
    if not isinstance(orientacoes, list) or not orientacoes or any(o not in ("vertical", "lateral", "invertida") for o in orientacoes):
        aviso("orientacoes_permitidas", "não informadas ou inválidas; não autorizam rotação.")
    restricoes = pilha.get("restricoes")
    if not isinstance(restricoes, str) or not restricoes.strip():
        aviso("restricoes", "não informadas; não presumir ausência de restrições.")
    return mensagens
