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