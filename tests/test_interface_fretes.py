from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from consumo import historico

ROOT=Path(__file__).resolve().parents[1]


class InterfaceFretesTests(unittest.TestCase):
    def abrir(self):
        a=AppTest.from_file(str(ROOT/'interface/app.py'),default_timeout=30).run()
        return a.switch_page('paginas/rotas.py').run()

    def test_pagina_parcial_edicao_restauracao_e_extras_sem_rede(self):
        arquivo=ROOT/'dados/fretes_simulados.json'
        original=arquivo.read_bytes()
        with patch('consumo.cambio.requests.get') as get:
            a=self.abrir()
            self.assertFalse(a.exception)
            self.assertEqual(a.session_state['logistica_ativa']['resultado']['estado'],'parcial')
            a.number_input(key='frete_item_frete_maritimo_valor').set_value(1234.0).run()
            self.assertFalse(a.exception)
            r=a.session_state['logistica_ativa']['resultado']
            self.assertEqual(r['frete_maritimo']['valor'],1234.0)
            self.assertEqual(r['frete_maritimo']['natureza'],'informado_manualmente')
            a.button(key='restaurar_frete').click().run()
            self.assertEqual(a.number_input(key='frete_item_frete_maritimo_valor').value,2000)
            a.text_input(key='frete_extra_nome').set_value('Despesa de teste').run()
            a.button(key='adicionar_extra').click().run()
            self.assertFalse(a.exception)
            extra=next(d for d in a.session_state['frete_despesas'] if d['categoria']=='outras')
            a.button(key='remover_'+extra['id']).click().run()
            self.assertFalse(a.exception)
            self.assertFalse(any(d['categoria']=='outras' for d in a.session_state['frete_despesas']))
            get.assert_not_called()
        self.assertEqual(arquivo.read_bytes(),original)

    def test_escopo_completo_sem_cambio_e_mudanca_de_moeda(self):
        with patch('consumo.cambio.requests.get') as get:
            a=self.abrir()
            for id_ in ('terrestre_origem','terrestre_destino'):
                a.selectbox(key='frete_item_'+id_+'_estado').set_value('nao_aplicavel').run()
            a.selectbox(key='frete_item_seguro_base').set_value('operacao').run()
            a.number_input(key='frete_item_seguro_valor').set_value(20.0).run()
            a.text_input(key='frete_item_porto_origem_moeda').set_value('USD').run()
            a.selectbox(key='frete_moeda').set_value('USD').run()
            self.assertFalse(a.exception)
            r=a.session_state['logistica_ativa']['resultado']
            self.assertEqual(r['estado'],'completo')
            self.assertEqual(r['total_consolidado']['minimo'],'2720.00')
            a.selectbox(key='frete_moeda').set_value('EUR').run()
            r=a.session_state['logistica_ativa']['resultado']
            self.assertEqual(r['estado'],'parcial')
            self.assertIsNone(r['total_consolidado'])
            self.assertEqual(r['moeda_apresentacao'],'EUR')
            get.assert_not_called()

    def test_rota_sem_tarifa_e_mudanca_de_rota_nao_reutiliza_edicao(self):
        a=self.abrir()
        a.number_input(key='frete_item_frete_maritimo_valor').set_value(1234.0).run()
        a.selectbox(key='frete_destino_iso').set_value('ZA').run()
        self.assertFalse(a.exception)
        self.assertTrue(any('Frete indisponível' in m.value for m in a.info))
        self.assertEqual(a.session_state['logistica_ativa']['resultado']['frete_maritimo']['estado'],'desconhecido')
        a.selectbox(key='frete_item_frete_maritimo_estado').set_value('conhecido').run()
        self.assertNotIn('logistica_ativa',a.session_state)
        a.number_input(key='frete_item_frete_maritimo_valor').set_value(800.0).run()
        self.assertFalse(a.exception)
        self.assertEqual(a.session_state['logistica_ativa']['resultado']['frete_maritimo']['total_original']['minimo'],'800.00')

    def test_cambio_sob_demanda_e_transferencia_salva_fotografia(self):
        with tempfile.TemporaryDirectory() as pasta,patch.object(historico,'BANCO',Path(pasta)/'teste.sqlite3'):
            a=self.abrir()
            fake=dict(origem='USD',destino='BRL',cotacao=5,data_referencia='2026-11-05')
            with patch('interface.fretes.consultar_cotacao',return_value=fake) as consultar:
                a.button(key='consultar_cambio_frete').click().run()
                self.assertEqual(consultar.call_count,1)
            self.assertFalse(a.exception)
            a.button(key='levar_frete_simulador').click().run()
            self.assertFalse(a.exception)
            self.assertEqual(a.title[0].value,'Simulador')
            # AppTest mantém o hash inicial após st.switch_page; fixe o destino
            # para que os próximos eventos sejam enviados à página correta.
            a.switch_page('paginas/simulador.py').run()
            with patch('interface.simulador.consultar_cotacao',return_value=dict(origem='BRL',destino='BRL',cotacao=1,data_referencia=None)):
                next(b for b in a.button if b.label=='Calcular conversão').click().run()
            next(b for b in a.button if b.label=='Salvar simulação').click().run()
            self.assertFalse(a.exception)
            salvos=historico.listar()
            self.assertEqual(len(salvos),1)
            self.assertIsNotNone(salvos[0]['logistica'])
            self.assertEqual(salvos[0]['logistica']['resultado']['frete_maritimo']['valor'],2000)
            a.number_input(key='entrada_qtd').set_value(2).run()
            self.assertIsNone(a.session_state['fotografia']['logistica'])
            self.assertFalse(a.exception)


if __name__=='__main__':
    unittest.main()
