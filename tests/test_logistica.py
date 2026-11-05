import copy
import json
from pathlib import Path
import unittest

from calculos.operacoes import calcular_subtotal_faixa, converter_faixa
from consumo.catalogo import carregar_dados_simulador
from consumo.logistica import validar_variante

ROOT = Path(__file__).resolve().parents[1]


class LogisticaTests(unittest.TestCase):
    def setUp(self):
        self.catalogo, _ = carregar_dados_simulador()
        self.v = copy.deepcopy(self.catalogo["produtos"][0]["variantes"][0])

    def test_todas_variantes(self):
        self.assertEqual(len(self.catalogo["produtos"]), 10)
        variantes = [v for p in self.catalogo["produtos"] for v in p["variantes"]]
        self.assertEqual(len(variantes), 20)
        for v in variantes:
            with self.subTest(variante=v["nome"]):
                avisos = validar_variante(v)
                self.assertTrue(avisos)  # Somente custo pendente.
                self.assertTrue(all(a.startswith("custo_origem.") or a.startswith("tipo:") for a in avisos), avisos)
                self.assertEqual(v["dados_fisicos"]["natureza"], "simulado")
                self.assertEqual(v["custo_origem"]["natureza"], "nao_informado")

    def test_compatibilidade_com_catalogo_anterior(self):
        anterior = json.loads((ROOT / "tests" / "catalogo_precos_original.json").read_text(encoding="utf-8-sig"))
        atual_sem_novos = copy.deepcopy(self.catalogo)
        for p in atual_sem_novos["produtos"]:
            for v in p["variantes"]:
                v.pop("custo_origem")
                v.pop("dados_fisicos")
        self.assertEqual(atual_sem_novos, anterior)
        for antigo, novo in zip(anterior["produtos"], self.catalogo["produtos"]):
            for a, n in zip(antigo["variantes"], novo["variantes"]):
                for qtd in (1, 5, 100):
                    esperado = {k: a.get(k) * qtd if a.get(k) is not None else None
                                for k in ("minimo", "maximo", "referencia_superior")}
                    self.assertEqual(calcular_subtotal_faixa(n, qtd), esperado)
                    self.assertEqual(converter_faixa(esperado, 0.25),
                                     {k: v * .25 if v is not None else None for k, v in esperado.items()})

    def test_dados_ausentes_nao_quebram_preco(self):
        antigo = dict(nome="Legado", minimo=10, maximo=None, referencia_superior=20)
        self.assertTrue(validar_variante(antigo))
        self.assertEqual(calcular_subtotal_faixa(antigo, 2),
                         dict(minimo=20, maximo=None, referencia_superior=40))

    def test_pesos_dimensoes_quantidades_invalidos(self):
        for valor in (0, -1, True, "5", float("nan"), float("inf")):
            with self.subTest(valor=valor):
                v = copy.deepcopy(self.v)
                v["dados_fisicos"]["produto"]["peso_liquido_kg"] = valor
                self.assertTrue(any(a.startswith("peso_liquido_kg:") for a in validar_variante(v)))
                v["dados_fisicos"]["unidade_embarque"]["dimensoes_externas"]["altura_cm"] = valor
                self.assertTrue(any("dimensoes_externas.altura_cm:" in a for a in validar_variante(v)))
        for valor in (0, -1, 1.5, True, None):
            self.v["dados_fisicos"]["unidade_embarque"]["quantidade_produtos"] = valor
            self.assertTrue(any(a.startswith("quantidade_produtos:") for a in validar_variante(self.v)))

    def test_peso_bruto_insuficiente(self):
        self.v["dados_fisicos"]["unidade_embarque"]["peso_bruto_kg"] = 1
        self.assertTrue(any("quantidade ×" in a for a in validar_variante(self.v)))

    def test_custo_independente_e_faixas(self):
        self.v["custo_origem"] = dict(tipo="compra", minimo=50, maximo=80,
            moeda="BRL", natureza="simulado", fonte="Hipótese de teste", data_referencia=None)
        self.assertEqual(validar_variante(self.v), [])
        self.v["custo_origem"]["maximo"] = 40
        self.assertTrue(any("mínimo não" in a for a in validar_variante(self.v)))
        self.v["custo_origem"]["maximo"] = None
        self.assertEqual(validar_variante(self.v), [])
        self.v["custo_origem"]["data_referencia"] = "data inventada"
        self.assertTrue(any("data_referencia" in a for a in validar_variante(self.v)))

    def test_empilhamento_e_palete(self):
        fis = self.v["dados_fisicos"]
        fis["empilhamento"]["permitido"] = False
        self.assertTrue(any("contradiz" in a for a in validar_variante(self.v)))
        fis["empilhamento"]["permitido"] = None
        self.assertTrue(any("não autoriza empilhar" in a for a in validar_variante(self.v)))
        fis["empilhamento"]["permitido"] = True
        fis["empilhamento"]["carga_sobreposta_maxima_kg"] = 1
        self.assertTrue(any("insuficiente" in a for a in validar_variante(self.v)))
        fis["unidade_embarque"]["usa_palete"] = True
        self.assertTrue(any("inclua peso" in a for a in validar_variante(self.v)))
        fis["empilhamento"]["orientacoes_permitidas"] = None
        self.assertTrue(any("não autorizam rotação" in a for a in validar_variante(self.v)))

    def test_objetos_incompletos(self):
        for chave in ("produto", "unidade_embarque", "empilhamento"):
            v = copy.deepcopy(self.v)
            v["dados_fisicos"][chave] = "inválido"
            self.assertTrue(validar_variante(v))


if __name__ == "__main__":
    unittest.main()
