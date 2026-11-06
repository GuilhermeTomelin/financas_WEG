from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from calculos.fretes import assinatura_contexto,serializar
from calculos.consolidacao import consolidar_operacao
from consumo.catalogo import carregar_dados_simulador
from consumo.conteineres import carregar_conteineres
from consumo import historico

ROOT=Path(__file__).resolve().parents[1]


class InterfaceCustosTests(unittest.TestCase):
    def abrir(self):
        a=AppTest.from_file(str(ROOT/'interface/app.py'),default_timeout=30).run().switch_page('paginas/simulador.py').run()
        a.selectbox(key='entrada_moeda_apresentacao').set_value('BRL').run()
        return a

    def widget(self,a,tipo,sufixo):
        return next(w for w in getattr(a,tipo) if w.key.startswith('custo_') and w.key.endswith(sufixo))

    def cobertura(self,a,lado='comprador'):
        self.widget(a,'text_input','_local_origem').set_value('Fábrica A').run()
        for trecho in ('origem','maritimo'):
            self.widget(a,'selectbox','_trecho_'+trecho).set_value('contemplado').run()
            self.widget(a,'text_input','_premissa_'+trecho).set_value('Incluído no escopo por declaração manual').run()
        self.widget(a,'selectbox','_tributos_'+lado).set_value('sem_adicionais').run()
        self.widget(a,'text_input','_tributos_premissa_'+lado).set_value('Sem adicionais tributários nesta hipótese').run()

    def test_comprador_completo_sem_custo_interno_vendedor_e_sem_rede(self):
        with patch('consumo.cambio.requests.get') as get:
            a=self.abrir()
            self.cobertura(a)
            self.assertFalse(a.exception)
            r=a.session_state['fotografia']['custos']
            self.assertEqual(r['perspectiva_selecionada'],'comprador')
            self.assertEqual(r['perspectivas']['comprador']['por_moeda']['BRL']['estado_dados'],'completo')
            self.assertEqual(r['perspectivas']['vendedor']['por_moeda']['BRL']['estado_dados'],'parcial')
            self.assertIsNone(r['perspectivas']['comprador']['por_moeda']['BRL']['percentual_acrescimo'])
            self.assertIn('Composição dos custos',[t.label for t in a.tabs])
            get.assert_not_called()

    def test_base_vendedor_manual_unitario_e_percentual_definido(self):
        a=self.abrir()
        self.cobertura(a,'vendedor')
        self.widget(a,'radio','_base_modo').set_value('manual').run()
        self.widget(a,'number_input','_base_minimo').set_value(100).run()
        self.widget(a,'checkbox','_base_definido').check().run()
        self.widget(a,'text_input','_base_fonte').set_value('Compra por produto explicitamente informada').run()
        a.selectbox(key='custo_perspectiva').set_value('vendedor').run()
        self.assertFalse(a.exception)
        r=a.session_state['fotografia']['custos']['perspectivas']['vendedor']['por_moeda']['BRL']
        self.assertEqual(r['total_estimado']['minimo'],'100.00')
        self.assertEqual(r['total_unitario']['minimo'],'100.00')
        self.assertEqual(float(r['percentual_acrescimo']['minimo']),0)
        self.widget(a,'text_input','_base_fonte').set_value('').run()
        self.assertIsNone(a.session_state['fotografia']['custos'])
        self.assertTrue(any('exige tipo e fonte' in x.value for x in a.error))

    def test_atualizador_central_inclui_par_do_custo_interno(self):
        a=self.abrir();self.cobertura(a,'vendedor')
        self.widget(a,'radio','_base_modo').set_value('manual').run()
        self.widget(a,'number_input','_base_minimo').set_value(20).run()
        self.widget(a,'checkbox','_base_definido').check().run()
        self.widget(a,'text_input','_base_fonte').set_value('Compra em USD').run()
        self.widget(a,'text_input','_base_moeda').set_value('USD').run()
        self.assertIsNone(a.session_state['fotografia']['custos']['perspectivas']['vendedor']['por_moeda']['BRL']['total_estimado'])
        q=dict(origem='USD',destino='BRL',cotacao=5,data_referencia='2026-11-05',fonte='Referência controlada do teste')
        with patch('interface.simulador.consultar_cotacao',return_value=q) as consultar:
            next(b for b in a.button if b.label=='Calcular conversão').click().run()
            self.assertEqual(consultar.call_count,1)
            self.assertEqual(consultar.call_args.args[:2],('USD','BRL'))
        self.assertFalse(a.exception)
        self.assertEqual(a.session_state['fotografia']['custos']['perspectivas']['vendedor']['por_moeda']['BRL']['total_estimado']['minimo'],'100.00')

    def test_edicao_estado_cliente_e_data_nao_reutiliza_resultado(self):
        a=self.abrir();self.cobertura(a)
        anterior=a.session_state['resultado_id']
        self.widget(a,'selectbox','_ate').set_value('cliente').run()
        r=a.session_state['fotografia']['custos']
        self.assertEqual(r['cobertura']['confirmada'],'porto_destino')
        self.assertIsNone(r['perspectivas']['comprador']['por_moeda']['BRL']['total_estimado'])
        self.assertNotEqual(a.session_state['resultado_id'],anterior)
        a.date_input(key='custo_data').set_value(date(2026,11,4)).run()
        self.assertEqual(a.session_state['fotografia']['custos']['configuracao']['escopo']['data_simulacao'],'2026-11-04')
        a.date_input(key='custo_data').set_value(None).run()
        self.assertFalse(a.exception)
        self.assertIsNone(a.session_state['fotografia']['custos'])

    def test_responsabilidade_e_inclusao_reconcilia_logistica_existente(self):
        a=self.abrir()
        cat,_=carregar_dados_simulador();produto=cat['produtos'][0];v=produto['variantes'][0]
        itens=[dict(id='frete_maritimo',nome='Frete do teste',valor=40,moeda='BRL',categoria='maritimo',base='conteiner',estado='conhecido',natureza='simulado',participa_total=True,incluido_em=None,componentes_base=[])]
        entrada=dict(produto_id=produto['id'],origem='BRSSZ',destino='ITGIT',conteiner=carregar_conteineres()[0],despesas=itens,moeda='BRL')
        base=consolidar_operacao(v,1,'BRL','BRL',logistica=entrada)
        a.session_state['logistica_ativa']=dict(assinatura=assinatura_contexto(produto['id'],v,1,'BRSSZ','ITGIT','dry20','BRL'),entradas=serializar(entrada),resultado=serializar(base['resultado_logistica']))
        a.run();self.cobertura(a)
        r=a.session_state['fotografia']['custos']['perspectivas']['comprador']['por_moeda']['BRL']
        self.assertEqual(r['estado_dados'],'parcial')
        self.widget(a,'selectbox','_item_frete_maritimo_responsavel').set_value('comprador').run()
        r=a.session_state['fotografia']['custos']['perspectivas']['comprador']['por_moeda']['BRL']
        self.assertEqual(r['total_estimado']['minimo'],'1840.00')
        self.widget(a,'selectbox','_item_frete_maritimo_tratamento').set_value('incluido_preco').run()
        self.assertIsNone(a.session_state['fotografia']['custos'])
        self.widget(a,'text_input','_item_frete_maritimo_justificativa').set_value('Frete já está no preço de 1800 a 2600').run()
        r=a.session_state['fotografia']['custos']['perspectivas']['comprador']['por_moeda']['BRL']
        self.assertEqual(r['total_estimado']['minimo'],'1800.00')
        self.assertFalse(a.exception)

    def test_historico_copia_estado_e_navegacao_preserva_entradas(self):
        with tempfile.TemporaryDirectory() as pasta,patch.object(historico,'BANCO',Path(pasta)/'teste.sqlite3'),patch('consumo.cambio.requests.get') as get:
            a=self.abrir();self.cobertura(a)
            custos=deepcopy(a.session_state['fotografia']['custos'])
            rid=a.session_state['resultado_id']
            a.switch_page('paginas/produtos.py').run().switch_page('paginas/simulador.py').run()
            self.assertEqual(a.session_state['resultado_id'],rid)
            next(b for b in a.button if b.label=='Salvar simulação').click().run()
            self.assertEqual(historico.listar()[0]['custos'],custos)
            self.widget(a,'text_input','_local_origem').set_value('Outro local').run()
            a.switch_page('paginas/historico.py').run()
            self.assertFalse(a.exception)
            self.assertTrue(any('Consolidação de custos salva' in c.value for c in a.caption))
            self.assertEqual(historico.listar()[0]['custos'],custos)
            get.assert_not_called()

    def test_quantidade_vazia_remove_fotografia_sem_excecao(self):
        a=self.abrir()
        a.number_input(key='entrada_qtd').set_value(None).run()
        self.assertFalse(a.exception)
        with self.assertRaises(KeyError):a.session_state['fotografia']


if __name__=='__main__':unittest.main()
