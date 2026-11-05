def calcular_estimativa(preco_unitario, quantidade, cotacao):
    """Calcula os totais: preço unitário x quantidade x cotação."""
    if preco_unitario <= 0:
        raise ValueError("O preço unitário deve ser maior que zero.")
    if quantidade <= 0:
        raise ValueError("A quantidade deve ser maior que zero.")
    if cotacao <= 0:
        raise ValueError("A cotação deve ser maior que zero.")

    total_original = preco_unitario * quantidade
    total_convertido = converter_faixa(dict(minimo=total_original,maximo=total_original,referencia_superior=None),cotacao)["minimo"]

    return {
        "total_original": total_original,
        "total_convertido": total_convertido,
    }
def calcular_subtotal_faixa(variante, quantidade):
    """Calcula a faixa de preço da mercadoria na moeda do catálogo."""
    if type(quantidade) is not int or quantidade < 1:
        raise ValueError("A quantidade deve ser um número inteiro maior que zero.")

    from decimal import Decimal
    from calculos.monetario import faixa, multiplicar
    totais=multiplicar(faixa(variante),Decimal(quantidade))
    # Preserva os tipos numéricos do contrato legado, calculando em decimal.
    return {campo: None if valor is None else int(valor) if type(variante.get(campo)) is int
            else float(valor) if type(variante.get(campo)) is float else valor
            for campo,valor in totais.items()}


def converter_faixa(subtotal, cotacao, moeda_destino=None):
    """Adaptador compatível: sem moeda mantém saída numérica sem arredondar.

    Novas telas usam a consolidação com moeda explícita e valores Decimal.
    """
    from calculos.monetario import decimal, multiplicar, faixa, arredondar
    convertido=multiplicar(faixa(subtotal),decimal(cotacao,"Cotação",positivo=True))
    if moeda_destino is not None:
        return arredondar(convertido,moeda_destino)
    return {k:float(v) if v is not None else None for k,v in convertido.items()}
