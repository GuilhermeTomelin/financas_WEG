from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]


class InterfaceCambioTests(unittest.TestCase):
    def abrir(self,pagina='simulador'):
        return AppTest.from_file(str(ROOT/'interface/app.py'),default_timeout=30).run().switch_page('paginas/'+pagina+'.py').run()

    def test_compartilha_taxa_entre_paginas_sem_consulta_ao_navegar(self):
        app=self.abrir('rotas')
        q=dict(origem='USD',destino='BRL',cotacao=5,data_referencia='2026-11-05',
               consultado_em='2026-11-05T12:00:00+00:00',provedor='Teste controlado',fonte='Simulado em teste',metodo='direta')
        with patch('interface.fretes.consultar_cotacao',return_value=q) as consultar:
            app.button(key='consultar_cambio_frete').click().run()
            self.assertEqual(consultar.call_count,1)
        app.button(key='levar_frete_simulador').click().run()
        app.switch_page('paginas/simulador.py').run()
        with patch('consumo.cambio.requests.get') as get:
            app.selectbox(key='entrada_moeda_apresentacao').set_value('USD').run()
            self.assertFalse(app.exception)
            snapshot=app.session_state['fotografia']['consolidacao']
            self.assertEqual(list(snapshot['por_moeda']),['BRL','USD'])
            self.assertIsNotNone(app.session_state['fotografia']['logistica'])
            mercadoria=snapshot['itens'][0]
            self.assertEqual(mercadoria['taxas']['USD']['metodo'],'inversa')
            self.assertEqual(mercadoria['taxas']['USD']['data_referencia'],'2026-11-05')
            get.assert_not_called()

    def test_taxa_manual_comparativa_identificada(self):
        app=self.abrir()
        q=dict(origem='BRL',destino='EUR',cotacao=.2,data_referencia='2026-11-05')
        with patch('interface.simulador.consultar_cotacao',return_value=q):
            next(b for b in app.button if b.label=='Calcular conversão').click().run()
        app.checkbox(key='entrada_comparar_EUR').check().run()
        app.number_input(key='entrada_taxa_EUR').set_value(.25).run()
        self.assertFalse(app.exception)
        foto=app.session_state['fotografia']
        self.assertEqual(foto['comparacao']['cotacao_manual']['metodo'],'manual')
        self.assertEqual(foto['consolidacao']['itens'][0]['taxas']['EUR']['cotacao'],'0.2')
        self.assertEqual(foto['comparacao']['negociado']['minimo'],'450.00')

    def test_moeda_brl_coluna_unica_e_originais_intactos(self):
        app=self.abrir()
        app.selectbox(key='entrada_moeda_apresentacao').set_value('BRL').run()
        self.assertFalse(app.exception)
        r=app.session_state['fotografia']['consolidacao']
        self.assertEqual(list(r['por_moeda']),['BRL'])
        self.assertEqual(r['itens'][0]['moeda'],'BRL')
        self.assertEqual(r['itens'][0]['valor_original']['minimo'],'1800')


if __name__=='__main__':
    unittest.main()
