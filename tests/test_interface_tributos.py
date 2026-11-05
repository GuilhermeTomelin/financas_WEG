from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from consumo import historico

ROOT=Path(__file__).resolve().parents[1]


class InterfaceTributosTests(unittest.TestCase):
    def abrir(self):
        return AppTest.from_file(str(ROOT/'interface/app.py'),default_timeout=30).run().switch_page('paginas/impostos.py').run()

    def exemplo(self):
        a=self.abrir()
        a.selectbox(key='fiscal_modo').set_value('exemplo_didatico').run()
        a.button(key='carregar_cenario_fiscal').click().run()
        a.selectbox(key='fiscal_moeda').set_value('BRL').run()
        self.assertFalse(a.exception)
        return a

    def test_manual_adicionar_editar_remover_sem_api(self):
        with patch('consumo.cambio.requests.get') as get:
            a=self.abrir()
            self.assertEqual([t.label for t in a.tabs],['Cenário','Classificação fiscal','Regras e bases','Resultado e memória'])
            r=a.session_state['fiscal_regras'][0];p='fiscal_regra_'+r['id']+'_'
            a.number_input(key=p+'aliquota').set_value(10).run()
            a.multiselect(key=p+'componentes').set_value(['mercadoria']).run()
            self.assertFalse(a.exception)
            resultado=a.session_state['tributos_ativos']['resultado']
            self.assertEqual(resultado['por_moeda']['BRL']['total_tributario']['minimo'],'180.00')
            self.assertEqual(resultado['por_moeda']['BRL']['total_tributario']['maximo'],'260.00')
            self.assertEqual(resultado['estado'],'parcial')  # Logística não configurada.
            self.assertIn('manual',resultado['natureza_resultado'])
            a.button(key='adicionar_tributo').click().run()
            self.assertEqual(len(a.session_state['fiscal_regras']),2)
            novo=a.session_state['fiscal_regras'][1]
            a.button(key='remover_tributo_'+novo['id']).click().run()
            self.assertEqual(len(a.session_state['fiscal_regras']),1)
            self.assertFalse(a.exception)
            get.assert_not_called()

    def test_edicao_didatica_identificada_e_config_preservada(self):
        with patch('consumo.cambio.requests.get') as get:
            a=self.exemplo()
            self.assertIn('didático',a.session_state['tributos_ativos']['resultado']['natureza_resultado'])
            a.number_input(key='fiscal_regra_did_a_aliquota').set_value(7).run()
            self.assertFalse(a.exception)
            r=a.session_state['fiscal_regras'][0]
            self.assertEqual(r['estado_regra'],'manual')
            self.assertEqual(r['substitui_regra']['versao'],'1.0')
            self.assertEqual(a.session_state['tributos_ativos']['entradas']['config']['regras'][0]['aliquota'],5)
            self.assertIn('manual',a.session_state['tributos_ativos']['resultado']['natureza_resultado'])
            get.assert_not_called()

    def test_mudanca_classificacao_data_pais_e_valor_recalcula(self):
        a=self.exemplo()
        a.text_input(key='fiscal_class_codigo').set_value('000002').run()
        r=a.session_state['tributos_ativos']['resultado']
        self.assertIsNone(r['por_moeda']['BRL']['total_tributario'])
        self.assertEqual(r['regras'][0]['estado_calculo'],'nao_suportado')
        a.text_input(key='fiscal_class_codigo').set_value('000001').run()
        a.date_input(key='fiscal_data').set_value(date(2027,1,1)).run()
        self.assertEqual(a.session_state['tributos_ativos']['resultado']['regras'][0]['estado_calculo'],'fora_vigencia')
        a.date_input(key='fiscal_data').set_value(date(2026,11,5)).run()
        a.number_input(key='fiscal_quantidade').set_value(2).run()
        self.assertEqual(a.session_state['tributos_ativos']['resultado']['por_moeda']['BRL']['total_tributario']['minimo'],'560.50')
        a.selectbox(key='fiscal_pais_destino').set_value('MX').run()
        self.assertFalse(a.session_state['tributos_ativos']['resultado']['compatibilidade']['compativel'])
        self.assertFalse(a.exception)

    def test_documentados_indisponiveis_nao_sao_exemplos_oficiais(self):
        a=self.exemplo()
        a.selectbox(key='fiscal_modo').set_value('documentado').run()
        self.assertFalse(a.exception)
        self.assertTrue(any('Nenhum cenário legal documentado' in x.value for x in a.info))
        with self.assertRaises(KeyError):a.session_state['tributos_ativos']

    def test_transferencia_invalida_quantidade_e_preserva_historico(self):
        with tempfile.TemporaryDirectory() as pasta,patch.object(historico,'BANCO',Path(pasta)/'simulacoes.sqlite3'),patch('consumo.cambio.requests.get') as get:
            a=self.exemplo()
            a.button(key='levar_fiscal_simulador').click().run()
            a.switch_page('paginas/simulador.py').run()
            self.assertFalse(a.exception)
            foto=deepcopy(a.session_state['fotografia'])
            self.assertIsNotNone(foto['tributacao'])
            next(b for b in a.button if b.label=='Salvar simulação').click().run()
            salvos=historico.listar()
            self.assertEqual(len(salvos),1)
            self.assertEqual(salvos[0]['tributacao'],foto['tributacao'])
            a.number_input(key='entrada_qtd').set_value(2).run()
            self.assertIsNone(a.session_state['fotografia']['tributacao'])
            a.switch_page('paginas/historico.py').run()
            self.assertFalse(a.exception)
            self.assertTrue(any('Fotografia tributária salva' in x.value for x in a.caption))
            self.assertEqual(historico.listar()[0]['tributacao'],foto['tributacao'])
            get.assert_not_called()


if __name__=='__main__':
    unittest.main()
