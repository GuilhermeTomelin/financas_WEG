def calcular_estimativa(preco_unitario, quantidade, cotacao):
    """Calcula os totais: preço unitário x quantidade x cotação."""
    if preco_unitario <= 0:
        raise ValueError("O preço unitário deve ser maior que zero.")
    if quantidade <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    if cotacao <= 0:
        raise ValueError("A cotação deve ser maior que zero.")

    total_original = preco_unitario * quantidade
    total_convertido = total_original * cotacao

    return {
        "total_original": total_original,
        "total_convertido": total_convertido,
    }
def calcular_subtotal_faixa(variante, quantidade):
    """Calcula a faixa de preço da mercadoria na moeda do catálogo."""
    if type(quantidade) is not int or quantidade < 1:
        raise ValueError("A quantidade deve ser um número inteiro maior que zero.")

    minimo = variante["minimo"]
    maximo = variante["maximo"]
    referencia = variante.get("referencia_superior")

    return {
        "minimo": minimo * quantidade,
        "maximo": maximo * quantidade if maximo is not None else None,
        "referencia_superior": referencia * quantidade if referencia is not None else None,
    }

def converter_faixa(subtotal, cotacao):
    """Converte os valores da faixa e preserva os limites em aberto."""
    if cotacao <= 0:
        raise ValueError("A cotação deve ser maior que zero.")

    return {
        campo: valor * cotacao if valor is not None else None
        for campo, valor in subtotal.items()
    }