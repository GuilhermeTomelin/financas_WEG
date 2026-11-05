from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import requests

from calculos.cambio import ConjuntoCotacoes,normalizar_cotacao
from calculos.monetario import faixa,arredondar,ErroMonetario
from calculos.consolidacao import consolidar_operacao
from calculos.fretes import serializar
from consumo.cambio import consultar_cotacao,atualizar_cotacoes,ErroCambio,MOEDAS_SUPORTADAS,obter_cache_sessao
from consumo.catalogo import carregar_dados_simulador
from consumo.conteineres import carregar_conteineres
from consumo import historico


def taxa(de='USD',para='BRL',valor=5,data='2026-11-05'):
    return dict(origem=de,destino=para,cotacao=valor,data_referencia=data,
                consultado_em='2026-11-05T12:00:00+00:00',provedor='Teste controlado',fonte='Simulado no teste',metodo='direta')


def despesa(id_,valor,moeda='USD',categoria='outras',base='operacao',**extras):
    return dict(id=id_,nome=id_,valor=valor,moeda=moeda,categoria=categoria,base=base,estado='conhecido',
                natureza='simulado',participa_total=True,incluido_em=None,componentes_base=[],**extras)


class CambioUnificadoTests(unittest.TestCase):
    def setUp(self):
        c,_=carregar_dados_simulador()
        self.v=deepcopy(c['produtos'][0]['variantes'][0])
        self.v.update(minimo=100,maximo=100)
        self.e=carregar_conteineres()[0]

    def entrada(self,itens):
        return dict(origem='BRSSZ',destino='ITGIT',conteiner=self.e,despesas=itens)

    def test_identidade_sem_api(self):
        with patch('consumo.cambio.requests.get') as get:
            q=consultar_cotacao('BRL','BRL')
            self.assertEqual(q['cotacao'],1)
            self.assertEqual(q['metodo'],'identidade')
            self.assertEqual(ConjuntoCotacoes().converter(12,'BRL','BRL')['minimo'],12)
            get.assert_not_called()

    def test_direta_inversa_precisao_e_originais(self):
        original=dict(minimo=10,maximo=None,referencia_superior=20)
        antes=deepcopy(original)
        c=ConjuntoCotacoes([taxa(valor=3)])
        self.assertEqual(c.converter(original,'USD','BRL'),dict(minimo=D(30),maximo=None,referencia_superior=D(60)))
        inversa=c.resolver('BRL','USD')
        self.assertEqual(inversa['metodo'],'inversa')
        self.assertEqual(inversa['componentes'][0]['cotacao'],3)
        self.assertGreater(len(str(inversa['cotacao'])),30)
        self.assertEqual(arredondar(c.converter(10,'BRL','USD'),'USD')['minimo'],D('3.33'))
        self.assertEqual(original,antes)

    def test_sem_cruzamento_ou_taxa_ficticia(self):
        c=ConjuntoCotacoes([taxa('USD','BRL'),taxa('USD','EUR',.8)])
        self.assertIsNone(c.converter(10,'BRL','EUR'))
        self.assertIn(('BRL','EUR'),c.faltantes)

    def test_datas_incompativeis_e_sem_data(self):
        c=ConjuntoCotacoes([taxa(),taxa('EUR','BRL',6,'2026-11-04')])
        self.assertIsNone(c.converter(1,'USD','BRL'))
        self.assertTrue(c.problemas)
        self.assertEqual(c.converter(1,'BRL','BRL')['minimo'],1)
        self.assertIsNone(ConjuntoCotacoes([taxa(data=None)]).converter(1,'USD','BRL'))
        manual=taxa(data=None);manual['metodo']='manual'
        self.assertEqual(ConjuntoCotacoes([manual]).converter(1,'USD','BRL')['minimo'],5)

    def test_taxas_invalidas_e_metadados(self):
        for valor in (0,-1,True,float('inf'),float('nan')):
            with self.subTest(valor=valor),self.assertRaises(ErroMonetario):
                normalizar_cotacao(taxa(valor=valor))
        legado=normalizar_cotacao(dict(origem='BRL',destino='USD',cotacao=.2,data_referencia='2026-11-05'))
        self.assertIn('consultado_em',legado['metadados_ausentes'])
        self.assertIsNone(legado['consultado_em'])

    def test_consulta_api_direcao_data_timeout_e_cobertura(self):
        resposta=Mock()
        resposta.json.return_value=dict(base='USD',quote='BRL',rate=5.123456,date='2026-11-05')
        with patch('consumo.cambio.requests.get',return_value=resposta) as get:
            q=consultar_cotacao('USD','BRL',data_referencia='2026-11-05')
            self.assertEqual(D(q['cotacao']),D('5.123456'))
            self.assertEqual(q['metodo'],'direta')
            self.assertIsNotNone(q['consultado_em'])
            self.assertEqual(get.call_args.kwargs['params'],{'date':'2026-11-05'})
        for dados in (dict(base='BRL',quote='USD',rate=5,date='2026-11-05'),dict(base='USD',quote='BRL',rate=True,date='2026-11-05'),dict(base='USD',quote='BRL',rate=5,date='inválida')):
            resposta.json.return_value=dados
            with patch('consumo.cambio.requests.get',return_value=resposta),self.assertRaises(ErroCambio):
                consultar_cotacao('USD','BRL')
        with patch('consumo.cambio.requests.get',side_effect=requests.exceptions.Timeout),self.assertRaises(ErroCambio):
            consultar_cotacao('USD','BRL')
        with patch('consumo.cambio.requests.get') as get,self.assertRaises(ErroCambio):
            consultar_cotacao('XXX','BRL')
        get.assert_not_called()
        self.assertEqual(set(MOEDAS_SUPORTADAS),{'BRL','USD','EUR','MXN','CLP','ZAR'})

    def test_consolidacao_exemplo_reconciliavel_brl_usd(self):
        itens=[despesa('frete_maritimo',10,categoria='maritimo',base='conteiner'),despesa('porto',20,'BRL')]
        log=self.entrada(itens)
        antes=deepcopy(log)
        r=consolidar_operacao(self.v,1,'BRL','USD',[taxa()],log)
        self.assertEqual(r['estado'],'completo')
        self.assertEqual(r['por_moeda']['BRL']['subtotal_mercadorias_logistica']['minimo'],170)
        self.assertEqual(r['por_moeda']['USD']['subtotal_mercadorias_logistica']['minimo'],34)
        self.assertEqual(r['itens'][0]['valor_original']['minimo'],100)
        for codigo in ('BRL','USD'):
            soma=sum(i['convertidos'][codigo]['minimo'] for i in r['itens'] if i['convertidos'][codigo])
            self.assertEqual(soma,r['por_moeda'][codigo]['subtotal_mercadorias_logistica']['minimo'])
        self.assertEqual(log,antes)
        # Nenhum custo de fabricação foi acrescentado ao preço comercial.
        self.assertEqual(len(r['itens']),3)

    def test_seguro_base_mista_mesmo_conjunto_sem_duplica(self):
        seguro=despesa('seguro',2,categoria='seguro',base='percentual')
        seguro['componentes_base']=['mercadoria','frete_maritimo']
        itens=[despesa('frete_maritimo',10,categoria='maritimo',base='conteiner'),seguro]
        log=self.entrada(itens)
        log['declaracao']=dict(valor=100,moeda='BRL',origem_escolha='Declarado explicitamente no teste')
        r=consolidar_operacao(self.v,1,'BRL','USD',[taxa()],log)
        self.assertEqual(r['resultado_logistica']['despesas'][1]['base_calculada']['minimo'],30)
        self.assertEqual(r['por_moeda']['USD']['grupos']['seguro']['minimo'],D('.60'))
        self.assertEqual(r['por_moeda']['BRL']['subtotal_mercadorias_logistica']['minimo'],153)
        self.assertEqual(r['por_moeda']['USD']['subtotal_mercadorias_logistica']['minimo'],D('30.60'))

    def test_parcial_faixa_aberta_inclusoes_e_arredondamento(self):
        self.v.update(minimo=100,maximo=None,referencia_superior=200)
        frete=despesa('frete_maritimo',10,categoria='maritimo',base='conteiner')
        doc=despesa('doc',50);doc.update(estado='incluido',incluido_em='frete_maritimo')
        r=consolidar_operacao(self.v,1,'BRL','USD',[taxa()],self.entrada([frete,doc]))
        total=r['por_moeda']['USD']['subtotal_mercadorias_logistica']
        self.assertEqual(total,dict(minimo=D(30),maximo=None,referencia_superior=D(50)))
        self.assertIsNone(r['itens'][2]['convertidos']['BRL'])
        parcial=consolidar_operacao(self.v,1,'BRL','USD',[],self.entrada([frete]))
        self.assertIsNone(parcial['por_moeda']['BRL']['subtotal_mercadorias_logistica'])
        self.assertIsNone(parcial['por_moeda']['BRL']['grupos']['frete_maritimo'])
        self.assertEqual(parcial['itens'][1]['valor_original']['minimo'],10)
        self.assertEqual(arredondar(faixa('1.005'),'BRL')['minimo'],D('1.01'))
        self.assertEqual(arredondar(faixa('1.5'),'CLP')['minimo'],2)

    def test_brl_sem_duplicacao_e_conjunto_atualizado_uma_vez_por_par(self):
        itens=[despesa('frete_maritimo',10,categoria='maritimo',base='conteiner')]
        def calcular(qs):
            return consolidar_operacao(self.v,1,'BRL','BRL',qs,self.entrada(itens))
        consultar=Mock(return_value=taxa())
        cache,r,erros=atualizar_cotacoes(calcular,consultar)
        self.assertFalse(erros)
        self.assertEqual(consultar.call_count,1)
        self.assertEqual(list(r['por_moeda']),['BRL'])
        self.assertEqual(len(cache),1)
        # Recalcular com o cache não faz nova consulta.
        calcular(list(cache.values()))
        self.assertEqual(consultar.call_count,1)
        falha=Mock(side_effect=ErroCambio('indisponível'))
        cache,r,erros=atualizar_cotacoes(calcular,falha)
        self.assertEqual(cache,{})
        self.assertTrue(erros)
        self.assertEqual(r['estado'],'parcial')

    def test_atualizacao_fixa_data_dos_pares_seguintes(self):
        def calcular(qs):
            c=ConjuntoCotacoes(qs)
            c.converter(1,'USD','BRL');c.converter(1,'EUR','BRL')
            return dict(pares_faltantes=[list(p) for p in c.faltantes])
        def consultar(de,para,**kwargs):
            return taxa(de,para,6 if de=='EUR' else 5)
        mock=Mock(side_effect=consultar)
        cache,r,erros=atualizar_cotacoes(calcular,mock)
        self.assertEqual(mock.call_count,2)
        self.assertEqual(mock.call_args_list[1].kwargs,{'data_referencia':'2026-11-05'})
        self.assertFalse(erros)

    def test_migracao_cache_legado_uma_vez_sem_ressuscitar_falha(self):
        antiga=taxa()
        estado={'cambio_simulador':antiga}
        antes=deepcopy(antiga)
        cache=obter_cache_sessao(estado)
        self.assertEqual(ConjuntoCotacoes(cache.values()).converter(2,'USD','BRL')['minimo'],10)
        self.assertEqual(antiga,antes)
        estado['cotacoes_sessao']={}
        self.assertEqual(obter_cache_sessao(estado),{})

    def test_subtotal_decimal_nao_altera_meio_centavo_do_seguro(self):
        from calculos.operacoes import calcular_subtotal_faixa
        self.v.update(minimo=1.005,maximo=1.005)
        declarado=calcular_subtotal_faixa(self.v,3)
        self.assertEqual(str(declarado['minimo']),'3.015')
        seguro=despesa('seguro',100,'BRL',categoria='seguro',base='percentual')
        seguro['componentes_base']=['mercadoria']
        log=self.entrada([seguro])
        log['declaracao']=dict(valor=declarado,moeda='BRL',origem_escolha='Declarado explicitamente no teste')
        r=consolidar_operacao(self.v,3,'BRL','BRL',[],log)
        self.assertEqual(r['resultado_logistica']['despesas'][0]['total_original']['minimo'],D('3.02'))
        self.assertEqual(r['por_moeda']['BRL']['subtotal_mercadorias_logistica']['minimo'],D('6.04'))

    def test_historico_preserva_taxas_e_metadados(self):
        r=consolidar_operacao(self.v,1,'BRL','USD',[taxa()],self.entrada([]))
        snapshot=serializar(r)
        with tempfile.TemporaryDirectory() as pasta,patch.object(historico,'BANCO',Path(pasta)/'teste.sqlite3'):
            historico.salvar('op',dict(produto='Teste',consolidacao=snapshot))
            snapshot['cotacoes_usadas'][0]['cotacao']='999'
            antigo=historico.listar()[0]['consolidacao']
            self.assertNotEqual(antigo['cotacoes_usadas'][0]['cotacao'],'999')
            self.assertEqual(next(q for q in antigo['cotacoes_usadas'] if q['origem']!=q['destino'])['consultado_em'],'2026-11-05T12:00:00+00:00')


if __name__=='__main__':
    unittest.main()
