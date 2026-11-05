import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


class InterfaceConteineresTests(unittest.TestCase):
    def abrir(self):
        app=AppTest.from_file(str(ROOT/"interface/app.py"),default_timeout=30).run()
        return app.switch_page("paginas/conteineres.py").run()

    def test_pagina_comparacao_e_modo_manual(self):
        with patch("consumo.cambio.requests.get") as get:
            app=self.abrir()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.dataframe[-1].value),3)
            app.selectbox(key="conteiner_modo").set_value("Avaliar quantidade informada").run()
            app.number_input(key="conteiner_quantidade").set_value(100000).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Capacidade insuficiente" in w.value for w in app.warning))
            get.assert_not_called()

    def test_reaproveita_simulador_e_preserva_ao_navegar(self):
        app=self.abrir().switch_page("paginas/simulador.py").run()
        app.number_input(key="entrada_qtd").set_value(17).run()
        app.switch_page("paginas/conteineres.py").run()
        app.button(key="usar_selecao_simulador").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.number_input(key="conteiner_quantidade").value,17)
        app.switch_page("paginas/produtos.py").run()
        app.switch_page("paginas/conteineres.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.number_input(key="conteiner_quantidade").value,17)


if __name__=="__main__":
    unittest.main()
