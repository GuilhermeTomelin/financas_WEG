import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from consumo.catalogo import carregar_dados_simulador
from consumo.portos import carregar_portos

ROOT=Path(__file__).resolve().parents[1]


class NavegacaoTests(unittest.TestCase):
    def abrir(self):
        return AppTest.from_file(str(ROOT / "interface/app.py"),default_timeout=30).run()

    def test_paginas_sem_historico_sem_rede(self):
        with patch("interface.painel.registros",return_value=[]), patch("consumo.cambio.requests.get") as get:
            app=self.abrir()
            self.assertFalse(app.exception)
            self.assertEqual([m.value for m in app.metric][:2],["10","20"])
            for nome in ("simulador","conteineres","rotas","impostos","precificacao","produtos","historico","integracoes","dashboard"):
                app.switch_page(f"paginas/{nome}.py").run()
                self.assertFalse(app.exception, nome)
            get.assert_not_called()

    def test_navegar_preserva_selecao_e_resultado(self):
        app=self.abrir().switch_page("paginas/simulador.py").run()
        app.number_input(key="entrada_qtd").set_value(7).run()
        app.selectbox(key="entrada_destino_iso").set_value("MX").run()
        cotacao=dict(origem="BRL",destino="MXN",cotacao=3.0,data_referencia="2026-11-05")
        with patch("interface.simulador.consultar_cotacao",return_value=cotacao):
            next(b for b in app.button if b.label=="Calcular conversão").click().run()
        resultado=app.session_state["resultado_id"]
        with patch("interface.painel.registros",return_value=[]),patch("consumo.cambio.requests.get") as get:
            app.switch_page("paginas/produtos.py").run()
            app.switch_page("paginas/integracoes.py").run()
            app.switch_page("paginas/dashboard.py").run()
            app.switch_page("paginas/simulador.py").run()
            get.assert_not_called()
        self.assertFalse(app.exception)
        self.assertEqual(app.number_input(key="entrada_qtd").value,7)
        self.assertEqual(app.selectbox(key="entrada_destino_iso").value,"MX")
        self.assertEqual(float(app.session_state["cambio_simulador"]["cotacao"]),cotacao["cotacao"])
        self.assertEqual(app.session_state["cambio_simulador"]["data_referencia"],cotacao["data_referencia"])
        self.assertEqual(app.session_state["resultado_id"],resultado)
        app.number_input(key="entrada_qtd").set_value(8).run()
        with self.assertRaises(KeyError):
            app.session_state["cambio_simulador"]

    def test_catalogo_filtro_vazio(self):
        app=self.abrir().switch_page("paginas/produtos.py").run()
        app.text_input(key="catalogo_busca").set_value("produto inexistente 123").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Nenhum produto encontrado"==h.value for h in app.subheader))

    def test_historico_e_dashboard_com_dados_legados(self):
        catalogo,_=carregar_dados_simulador()
        registro=dict(id=1,salvo="2026-11-05T12:00:00+00:00",produto="Motor W22",variante="2 CV",quantidade=5,
                      pais="Itália",moeda="EUR",subtotal=dict(minimo=9000,maximo=13000,referencia_superior=None),
                      convertido=dict(minimo=1800,maximo=2600,referencia_superior=None),
                      cambio=dict(cotacao=.2,origem="BRL",destino="EUR",data_referencia="2026-11-05"),
                      origem=dict(pais="Brasil",porto="Santos"),destino=dict(porto="Gioia Tauro"))
        antes=copy.deepcopy(registro)
        with patch("interface.painel.registros",return_value=[registro]):
            app=self.abrir()
            self.assertEqual(app.metric[3].value,"1")
            app.switch_page("paginas/historico.py").run()
            self.assertFalse(app.exception)
            self.assertEqual([t.label for t in app.tabs],["Histórico","Relatórios"])
            self.assertTrue(app.dataframe)
        self.assertEqual(registro,antes)


if __name__=="__main__":
    unittest.main()
