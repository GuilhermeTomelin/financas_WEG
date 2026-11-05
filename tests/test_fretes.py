import copy
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calculos.fretes import (calcular_logistica, validar_despesas, ErroDespesas, serializar,
                            assinatura_contexto, cenario_compativel)
from consumo.catalogo import carregar_dados_simulador
from consumo.conteineres import carregar_conteineres
from consumo.fretes import carregar_fretes, buscar_tarifa, despesas_da_rota
from consumo import historico


def item(id_='frete_maritimo',valor=100,base='conteiner',moeda='USD',categoria='maritimo',**extra):
    d=dict(id=id_,nome=id_,valor=valor,base=base,moeda=moeda,categoria=categoria,
           natureza='simulado',estado='conhecido',participa_total=True,incluido_em=None,componentes_base=[])
    d.update(extra)
    return d


def cambio(de='USD',para='BRL',taxa=5):
    return dict(origem=de,destino=para,cotacao=taxa,fonte='Cotação simulada de teste',data_referencia='2026-11-05')


class FretesTests(unittest.TestCase):
    def setUp(self):
        c,_=carregar_dados_simulador()
        self.v=copy.deepcopy(c['produtos'][0]['variantes'][0])
        self.c=carregar_conteineres()[0]

    def calcular(self,itens=None,**opcoes):
        args=dict(variante=self.v,quantidade=5,conteiner=self.c,origem='BRSSZ',destino='ITGIT',
                  moeda_apresentacao='USD',despesas=itens if itens is not None else [item()])
        args.update(opcoes)
        return calcular_logistica(**args)

    def test_fcl_e_bases_sem_multiplicacao_indevida(self):
        despesas=[item(),item('doc',10,'operacao',categoria='documentacao'),
                  item('taxa_cont',3,'conteiner',categoria='origem'),item('taxa_prod',2,'produto',categoria='outras')]
        r=self.calcular(despesas,quantidade_manual=3)
        self.assertEqual(r['frete_maritimo']['total_original']['minimo'],300)
        self.assertEqual(r['total_consolidado']['minimo'],329) # 300 + 10 + 9 + 10
        self.assertEqual(r['total_por_produto']['minimo'],D('65.80'))
        self.assertEqual(r['estado'],'completo')
        self.assertEqual(self.calcular(quantidade=1)['frete_maritimo']['total_original']['minimo'],100)

    def test_seguro_fixo_e_percentual_componentes_explicitos(self):
        fixo=item('seguro',20,'operacao',categoria='seguro')
        self.assertEqual(self.calcular([item(),fixo],quantidade_manual=3)['total_consolidado']['minimo'],320)
        seguro=item('seguro',2,'percentual',categoria='seguro',componentes_base=['mercadoria','frete_maritimo'])
        declaracao=dict(valor=1000,moeda='USD',origem_escolha='Escolha explícita do teste')
        r=self.calcular([item(),seguro],declaracao=declaracao)
        self.assertEqual(r['despesas'][1]['base_calculada']['minimo'],1100)
        self.assertEqual(r['despesas'][1]['total_original']['minimo'],22)
        self.assertEqual(r['total_consolidado']['minimo'],122)
        r=self.calcular([item(),seguro])
        self.assertEqual(r['estado'],'parcial')
        self.assertIsNone(r['total_consolidado'])
        self.assertEqual(r['total_logistico_conhecido']['minimo'],100)
        self.assertTrue(any('valor declarado' in p for p in r['pendencias']))

    def test_seguro_nao_inclui_proprio_valor_e_ciclos(self):
        with self.assertRaises(ErroDespesas):
            self.calcular([item('seguro',1,'percentual',categoria='seguro',componentes_base=['seguro'])])
        a=item('a',1,'percentual',categoria='outras',componentes_base=['b'])
        b=item('b',1,'percentual',categoria='outras',componentes_base=['a'])
        with self.assertRaises(ErroDespesas):
            self.calcular([a,b])

    def test_inclusao_nao_duplica_e_exige_item_coberto(self):
        doc=item('documentacao',99,'operacao',categoria='documentacao',estado='incluido',incluido_em='frete_maritimo')
        r=self.calcular([item(),doc])
        self.assertEqual(r['total_consolidado']['minimo'],100)
        self.assertIsNone(r['despesas'][1]['total_original'])
        r=self.calcular([item(estado='desconhecido',valor=None),doc])
        self.assertEqual(r['estado'],'parcial')
        self.assertIsNone(r['total_logistico_conhecido'])
        with self.assertRaises(ErroDespesas):
            self.calcular([item(),dict(doc,incluido_em='mercadoria')])

    def test_zero_desconhecido_nao_aplicavel_e_excluido(self):
        zero=self.calcular([item(valor=0)])
        self.assertEqual(zero['total_consolidado']['minimo'],0)
        desconhecido=self.calcular([item(valor=None,estado='desconhecido')])
        self.assertIsNone(desconhecido['total_consolidado'])
        self.assertIsNone(desconhecido['total_logistico_conhecido'])
        for estado in ('nao_aplicavel','excluido'):
            r=self.calcular([item(valor=None,estado=estado)])
            self.assertEqual(r['estado'],'completo')
            self.assertEqual(r['total_consolidado']['minimo'],0)
        r=self.calcular([item(estado='desconhecido',participa_total=False,valor=None)])
        self.assertEqual(r['estado'],'completo')

    def test_rota_direcional_tipo_exato_e_arquivo_inalterado(self):
        config=carregar_fretes()
        antes=copy.deepcopy(config)
        self.assertEqual(len(config['tarifas']),9)
        tarifa=buscar_tarifa(config,'BRSSZ','ITGIT','dry20')
        self.assertEqual(tarifa['valor_unitario'],2000)
        self.assertIsNone(buscar_tarifa(config,'ITGIT','BRSSZ','dry20'))
        self.assertIsNone(buscar_tarifa(config,'BRRIO','ITGIT','dry20'))
        self.assertIsNone(buscar_tarifa(config,'BRSSZ','ZADUR','dry20'))
        itens=despesas_da_rota(config,None)
        self.assertEqual(next(d for d in itens if d['id']=='frete_maritimo')['estado'],'desconhecido')
        itens[0]['valor']=999
        tarifa['valor_unitario']=1
        self.assertEqual(config,antes)
        with self.assertRaises(ErroDespesas):
            self.calcular(tarifa=buscar_tarifa(config,'BRSSZ','USLAX','dry20'))

    def test_inclusao_da_tarifa_nao_pode_ser_cobrada_em_duplicidade(self):
        config=carregar_fretes()
        tarifa=buscar_tarifa(config,'BRSSZ','ITGIT','dry20')
        with self.assertRaisesRegex(ErroDespesas,'incluída na tarifa'):
            self.calcular([item(),item('documentacao',10,'operacao',categoria='documentacao')],tarifa=tarifa)

    def test_cambio_e_ausencia_sem_somar_moedas(self):
        despesas=[item(),item('doc',10,'operacao','BRL','documentacao')]
        r=self.calcular(despesas,moeda_apresentacao='BRL')
        self.assertEqual(r['subtotais_por_moeda']['USD']['minimo'],100)
        self.assertEqual(r['subtotais_por_moeda']['BRL']['minimo'],10)
        self.assertIsNone(r['total_logistico_conhecido'])
        self.assertIn(['USD','BRL'],r['pares_faltantes'])
        r=self.calcular(despesas,moeda_apresentacao='BRL',cotacoes=[cambio()])
        self.assertEqual(r['total_consolidado']['minimo'],510)
        self.assertEqual(r['cotacoes_usadas'][0]['fonte'],'Cotação simulada de teste')
        self.assertIsNone(self.calcular(despesas,cotacoes=[cambio()])['total_consolidado']) # não inverte BRL/USD
        for taxa in (0,-1,float('nan'),True):
            with self.assertRaises(ErroDespesas):
                self.calcular(cotacoes=[cambio(taxa=taxa)])

    def test_faixa_aberta_seguro_e_referencia(self):
        seguro=item('seguro',10,'percentual',categoria='seguro',componentes_base=['mercadoria','frete_maritimo'])
        declaracao=dict(valor=dict(minimo=100,maximo=None,referencia_superior=200),moeda='BRL',origem_escolha='Declarado no teste')
        r=self.calcular([item(valor=10),seguro],declaracao=declaracao,cotacoes=[cambio('BRL','USD',.2)])
        premio=r['despesas'][1]['total_original']
        self.assertEqual(premio,dict(minimo=D(3),maximo=None,referencia_superior=D(5)))
        self.assertEqual(r['total_consolidado'],dict(minimo=D(13),maximo=None,referencia_superior=D(15)))
        declaracao['valor']['referencia_superior']=None
        self.assertIsNone(self.calcular([item(valor=10),seguro],declaracao=declaracao,cotacoes=[cambio('BRL','USD',.2)])['total_consolidado']['referencia_superior'])

    def test_arredondamento_por_linha_meio_para_cima(self):
        a=item('a',.005,'operacao',categoria='outras')
        b=item('b',.015,'operacao',categoria='outras')
        r=self.calcular([a,b])
        self.assertEqual(r['total_consolidado']['minimo'],D('.03'))
        self.assertEqual(r['despesas'][0]['total_original']['minimo'],D('.01'))
        self.assertEqual(r['despesas'][1]['total_original']['minimo'],D('.02'))

    def test_capacidade_manual_e_incompatibilidade(self):
        r=self.calcular(quantidade=100000,quantidade_manual=1)
        self.assertEqual(r['estado'],'parcial')
        self.assertFalse(r['capacidade']['atende'])
        self.assertIsNone(r['total_por_produto'])
        self.assertEqual(r['frete_maritimo']['total_original']['minimo'],100)
        v=copy.deepcopy(self.v)
        v['dados_fisicos']['unidade_embarque']['dimensoes_externas']['altura_cm']=10000
        r=self.calcular(variante=v)
        self.assertFalse(r['capacidade']['compativel'])
        self.assertIsNone(r['quantidade_conteineres'])
        self.assertIsNone(r['frete_maritimo']['total_original'])
        self.assertIsNone(r['total_consolidado'])

    def test_transporte_terrestre_exige_local(self):
        d=item('terrestre_origem',200,'operacao','BRL','terrestre_origem')
        r=self.calcular([d],moeda_apresentacao='BRL')
        self.assertEqual(r['estado'],'parcial')
        r=self.calcular([d],moeda_apresentacao='BRL',locais={'terrestre_origem':'Fábrica didática informada pelo usuário'})
        self.assertEqual(r['total_consolidado']['minimo'],200)

    def test_validacao_ids_bases_e_valores(self):
        for d in (item(valor=-1),item(valor=True),item(base='produto',id_='frete_maritimo'),
                  item(valor=dict(minimo=10,maximo=5)),item(moeda='XX')):
            with self.assertRaises(ErroDespesas):
                self.calcular([d])
        with self.assertRaises(ErroDespesas):
            self.calcular([item(),item()])

    def test_fotografia_compativel_e_historico_imutavel(self):
        r=self.calcular()
        assinatura=assinatura_contexto('w22',self.v,5,'BRSSZ','ITGIT','dry20','USD')
        snapshot=dict(assinatura=assinatura,entradas={'despesas':[item()]},resultado=serializar(r))
        self.assertIsNotNone(cenario_compativel(snapshot,'w22',self.v,5,'BRSSZ','ITGIT','dry20','USD'))
        for campo,valor in ((2,6),(3,'BRRIO'),(4,'USLAX'),(5,'hc40'),(6,'BRL')):
            args=['w22',self.v,5,'BRSSZ','ITGIT','dry20','USD']
            args[campo]=valor
            self.assertIsNone(cenario_compativel(snapshot,*args))
        with tempfile.TemporaryDirectory() as pasta,patch.object(historico,'BANCO',Path(pasta)/'teste.sqlite3'):
            legado=dict(produto='Motor W22',pais='Itália',moeda='USD')
            historico.salvar('legado',legado)
            historico.salvar('novo',dict(legado,logistica=snapshot))
            snapshot['entradas']['despesas'][0]['valor']=999
            registros=historico.listar()
            salvo=next(r for r in registros if r.get('logistica'))
            self.assertEqual(salvo['logistica']['entradas']['despesas'][0]['valor'],100)
            self.assertEqual(salvo['logistica']['resultado']['total_consolidado']['minimo'],'100.00')
            antigo=next(r for r in registros if not r.get('logistica'))
            self.assertEqual({k:v for k,v in antigo.items() if k not in ('id','salvo')},legado)


if __name__=='__main__':
    unittest.main()
