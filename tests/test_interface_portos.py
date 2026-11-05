import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from consumo.portos import carregar_portos

ROOT = Path(__file__).resolve().parents[1]


class InterfacePortosTests(unittest.TestCase):
    def abrir(self):
        app = AppTest.from_file(str(ROOT / "interface/app.py"), default_timeout=30).run()
        app.switch_page("paginas/simulador.py").run()
        self.assertFalse(app.exception)
        return app

    def test_destinos_dependentes_e_moedas(self):
        app = self.abrir()
        self.assertEqual(app.selectbox(key="entrada_porto_origem").value, "BRSSZ")
        for iso, porto, moeda in (("IT", "ITGIT", "EUR"), ("US", "USLAX", "USD"),
                                   ("DE", "DEHAM", "EUR"), ("MX", "MXZLO", "MXN"),
                                   ("CL", "CLSAI", "CLP"), ("ZA", "ZADUR", "ZAR")):
            app.selectbox(key="entrada_destino_iso").set_value(iso).run()
            self.assertFalse(app.exception)
            self.assertEqual(app.selectbox(key="entrada_porto_destino").value, porto)
            self.assertEqual(app.selectbox(key="entrada_moeda_apresentacao").value, moeda)
        self.assertTrue(any("Frete indisponível para esta rota" == m.value for m in app.markdown))

    def test_cambio_invalida_ao_mudar_porto_ou_moeda(self):
        app = self.abrir()
        fake = dict(origem="BRL", destino="EUR", cotacao=.2, data_referencia="2026-11-05")
        with patch("interface.simulador.consultar_cotacao", return_value=fake):
            next(b for b in app.button if b.label == "Calcular conversão").click().run()
        self.assertEqual(float(app.session_state["cambio_simulador"]["cotacao"]), .2)
        outro = next(c for c in carregar_portos()[0]["portos"] if c.startswith("IT") and c != "ITGIT")
        app.selectbox(key="entrada_porto_destino").set_value(outro).run()
        with self.assertRaises(KeyError):
            app.session_state["cambio_simulador"]
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["fotografia"]["destino_unlocode"], outro)
        self.assertEqual(app.session_state["fotografia"]["consolidacao"]["moeda_apresentacao"], "EUR")
        with patch("interface.simulador.consultar_cotacao", return_value=fake):
            next(b for b in app.button if b.label == "Calcular conversão").click().run()
        app.selectbox(key="entrada_destino_iso").set_value("DE").run()
        with self.assertRaises(KeyError):
            app.session_state["cambio_simulador"]
        self.assertEqual(app.selectbox(key="entrada_moeda_apresentacao").value, "EUR")
        with patch("interface.simulador.consultar_cotacao", return_value=fake):
            next(b for b in app.button if b.label == "Calcular conversão").click().run()
        app.selectbox(key="entrada_moeda_apresentacao").set_value("USD").run()
        with self.assertRaises(KeyError):
            app.session_state["cambio_simulador"]

    def test_busca_favorito_e_sem_resultados(self):
        app = self.abrir()
        app.text_input(key="entrada_busca_origem_BR").set_value("BRRIO").run()
        self.assertEqual(app.selectbox(key="entrada_porto_origem").value, "BRRIO")
        app.button(key="favorito_origem").click().run()
        self.assertIn("BRRIO", app.session_state["favoritos_portos"])
        app.text_input(key="entrada_busca_origem_BR").set_value("não existe 123").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)

    def test_pais_sem_moeda_e_moeda_nao_suportada(self):
        app = self.abrir()
        app.selectbox(key="entrada_destino_iso").set_value("JP").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="entrada_moeda_apresentacao").value, "USD")
        base, config = carregar_portos()
        config = copy.deepcopy(config)
        config["paises"]["IT"]["moeda"] = "XXX"
        with patch("interface.simulador.carregar_portos", return_value=(base, config)):
            app = self.abrir()
        self.assertTrue(any("XXX não suportada" in w.value for w in app.warning))
        self.assertEqual(app.selectbox(key="entrada_moeda_apresentacao").value, "USD")


if __name__ == "__main__":
    unittest.main()
