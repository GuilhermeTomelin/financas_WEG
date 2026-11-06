"""Exemplos aritméticos independentes. Não validam contratos ou legislação."""
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from calculos.consolidacao import consolidar_operacao,consolidar_custos
from calculos.fretes import serializar
from calculos.tributos import calcular_tributos
from consumo.catalogo import carregar_dados_simulador
from consumo.conteineres import carregar_conteineres
from consumo import historico


def despesa(id_,valor,categoria='outras'):
    return dict(id=id_,nome=id_,valor=valor,moeda='BRL',categoria=categoria,
        base='conteiner' if id_=='frete_maritimo' else 'operacao',estado='conhecido',
        natureza='simulado',participa_total=True,incluido_em=None,componentes_base=[])


def configuracao():
    return dict(perspectiva='comprador',base_vendedor=dict(tipo='fabricacao',valor_unitario=60,moeda='BRL',fonte='Hipótese independente',natureza='manual'),
        contrato=dict(incoterm=None,versao=None,local_nomeado=None,atribuicao='manual'),
        escopo=dict(local_origem='Fábrica A',porto_embarque='BRSSZ',porto_destino='ITGIT',local_final_entrega=None,
            ate='porto_destino',data_simulacao='2026-11-05',trechos={k:dict(estado='contemplado',premissa='Cobertura declarada explicitamente no teste') for k in ('origem','maritimo')}),
        itens={id_:dict(responsavel='comprador',pagador_inicial='vendedor',tratamento='herdar') for id_ in ('frete_maritimo','seguro')},
        tributos={p:dict(estado='sem_adicionais',premissa='Hipótese manual: sem adicionais tributários neste exercício') for p in ('comprador','vendedor')})


class ConsolidacaoCustosTests(unittest.TestCase):
    def setUp(self):
        cat,_=carregar_dados_simulador()
        self.v=deepcopy(cat['produtos'][0]['variantes'][0]);self.v.update(minimo=100,maximo=100,referencia_superior=None)
        self.cfg=configuracao()
        self.log=dict(origem='BRSSZ',destino='ITGIT',conteiner=carregar_conteineres()[0],
            despesas=[despesa('frete_maritimo',30,'maritimo'),despesa('seguro',10,'seguro')])

    def base(self,q=1,moeda='BRL',taxas=()):
        return consolidar_operacao(self.v,q,'BRL',moeda,taxas,logistica=self.log)

    def calcular(self,q=1,moeda='BRL',taxas=(),fiscal=None):
        return consolidar_custos(self.base(q,moeda,taxas),q,self.cfg,taxas,fiscal)

    def dados(self,r,lado='comprador',moeda='BRL'):
        return r['perspectivas'][lado]['por_moeda'][moeda]

    def test_base_100_adicionais_40_total_140_acrescimo_40(self):
        cfg=deepcopy(self.cfg)
        r=self.calcular();c=self.dados(r)
        self.assertEqual(c['base_inicial']['minimo'],100)
        self.assertEqual(c['total_estimado']['minimo'],140)
        self.assertEqual(c['acrescimo_absoluto']['minimo'],40)
        self.assertEqual(c['percentual_acrescimo']['minimo'],40)
        self.assertEqual(c['denominador_acrescimo']['minimo'],100)
        self.assertEqual(c['denominador_participacao']['minimo'],140)
        self.assertEqual(c['estado_dados'],'completo')
        self.assertEqual(self.cfg,cfg)
        self.assertIn('simulado',r['perspectivas']['comprador']['naturezas'])
        self.assertNotEqual(c['linhas'][0]['participacao_no_total']['minimo'],40)

    def test_divisor_produtos_nao_conteineres_ou_embalagens(self):
        self.v.update(minimo=25,maximo=25)
        r=self.calcular(q=4);c=self.dados(r)
        self.assertEqual(c['base_inicial']['minimo'],100)
        self.assertEqual(c['total_estimado']['minimo'],140)
        self.assertEqual(c['total_unitario']['minimo'],35)
        self.assertEqual(c['base_unitaria']['minimo'],25)
        self.assertEqual(r['quantidade_produtos'],4)

    def test_perspectivas_nao_somam_fabricacao_e_preco(self):
        self.cfg['itens']['frete_maritimo']['responsavel']='vendedor'
        r=self.calcular()
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],110)
        self.assertEqual(self.dados(r,'vendedor')['total_estimado']['minimo'],90)
        # Pagador do seguro é vendedor, mas seu custo foi atribuído ao comprador.
        self.assertEqual(next(i for i in r['componentes'] if i['id']=='seguro')['pagador_inicial'],'vendedor')
        self.assertNotIn('total_global',r)

    def test_custo_interno_ausente_nao_bloqueia_comprador(self):
        self.cfg['base_vendedor']={}
        r=self.calcular()
        self.assertEqual(self.dados(r)['estado_dados'],'completo')
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],140)
        self.assertEqual(self.dados(r,'vendedor')['estado_dados'],'parcial')
        self.assertIsNone(self.dados(r,'vendedor')['total_estimado'])

    def test_frete_no_preco_nao_duplica_comprador_mantem_custo_vendedor(self):
        self.cfg['itens']['frete_maritimo'].update(responsavel='vendedor',tratamento='incluido_preco',justificativa='Preço comercial já inclui o frete de 30')
        r=self.calcular()
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],110)
        self.assertEqual(self.dados(r,'vendedor')['total_estimado']['minimo'],90)
        linha=next(i for i in self.dados(r)['linhas'] if i['id']=='frete_maritimo')
        self.assertEqual(linha['estado'],'incluido_na_base')
        self.assertIsNone(linha['valor_considerado'])

    def test_despesa_incluida_em_outra_sem_duplicacao(self):
        self.cfg['itens']['seguro'].update(tratamento='incluido_outro',incluido_em='frete_maritimo',justificativa='Cobrança de 30 já inclui seguro')
        self.assertEqual(self.dados(self.calcular())['total_estimado']['minimo'],130)
        self.log['despesas'][1].update(estado='incluido',incluido_em='frete_maritimo')
        self.cfg['itens']['seguro']['tratamento']='herdar'
        r=self.calcular()
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],130)
        self.assertEqual(len(self.dados(r)['linhas']),4)
        self.cfg['itens']['frete_maritimo']['responsavel']='vendedor'
        self.assertEqual(self.dados(self.calcular())['estado_dados'],'parcial')

    def test_referencias_invalidas_ciclos_e_justificativas(self):
        for alvo in ('inexistente','seguro'):
            self.cfg['itens']['seguro'].update(tratamento='incluido_outro',incluido_em=alvo,justificativa='Hipótese')
            with self.subTest(alvo=alvo),self.assertRaises(ValueError):self.calcular()
        self.cfg=configuracao()
        self.cfg['itens']['seguro'].update(tratamento='incluido_outro',incluido_em='frete_maritimo',justificativa='Hipótese')
        self.cfg['itens']['frete_maritimo'].update(tratamento='incluido_outro',incluido_em='seguro',justificativa='Hipótese')
        with self.assertRaises(ValueError):self.calcular()
        self.cfg=configuracao();self.cfg['itens']['seguro']['tratamento']='incluido_preco'
        with self.assertRaises(ValueError):self.calcular()
        self.cfg=configuracao();self.cfg['itens']['fantasma']={}
        with self.assertRaises(ValueError):self.calcular()

    def test_responsabilidade_indefinida_terceiro_e_desconhecido(self):
        self.cfg['itens']['seguro']['responsavel']='nao_definido'
        r=self.calcular()
        self.assertEqual(self.dados(r)['subtotal_conhecido']['minimo'],130)
        self.assertIsNone(self.dados(r)['total_estimado'])
        self.assertTrue(any('responsável' in p for p in self.dados(r)['pendencias']))
        self.cfg['itens']['seguro']['responsavel']='terceiro'
        self.assertEqual(self.dados(self.calcular())['total_estimado']['minimo'],130)
        self.log['despesas'][0].update(estado='desconhecido',valor=None)
        self.cfg['itens']['frete_maritimo']['responsavel']='vendedor'
        r=self.calcular()
        self.assertEqual(self.dados(r)['estado_dados'],'completo')
        self.assertEqual(self.dados(r,'vendedor')['estado_dados'],'parcial')

    def test_cambio_ausente_afeta_so_moeda_e_perspectiva_necessarias(self):
        self.cfg['base_vendedor'].update(valor_unitario=20,moeda='USD')
        r=self.calcular(moeda='USD')
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],140)
        self.assertIsNone(self.dados(r,'comprador','USD')['total_estimado'])
        self.assertIsNone(self.dados(r,'vendedor')['total_estimado'])
        taxa=dict(origem='USD',destino='BRL',cotacao=5,data_referencia='2026-11-05',fonte='Teste',metodo='manual')
        r=self.calcular(moeda='USD',taxas=[taxa])
        self.assertEqual(self.dados(r,'comprador','USD')['total_estimado']['minimo'],28)
        self.assertEqual(self.dados(r,'vendedor')['total_estimado']['minimo'],100)
        self.assertEqual(self.dados(r,'vendedor','USD')['total_estimado']['minimo'],20)

    def test_escopo_porto_cliente_e_local_incompativel(self):
        self.assertEqual(self.calcular()['cobertura']['confirmada'],'porto_destino')
        self.cfg['escopo'].update(ate='cliente',local_final_entrega='Cliente A')
        r=self.calcular()
        self.assertEqual(r['cobertura']['confirmada'],'porto_destino')
        self.assertNotIn('até o cliente',r['cobertura']['rotulo'])
        self.assertIsNone(self.dados(r)['total_estimado'])
        self.cfg['escopo']['trechos']['destino']=dict(estado='contemplado',premissa='Último trecho incluído no preço, por declaração do exercício')
        r=self.calcular()
        self.assertEqual(r['cobertura']['confirmada'],'cliente')
        self.assertEqual(self.dados(r)['estado_dados'],'completo')
        self.log['locais']={'terrestre_destino':'Outro local'}
        self.assertEqual(self.dados(self.calcular())['estado_dados'],'parcial')

    def test_ultimo_trecho_fora_do_escopo_portuario_nao_e_somado(self):
        self.log['despesas'].append(despesa('ultima_milha',20,'terrestre_destino'))
        self.log['locais']={'terrestre_destino':'Cliente A'}
        self.cfg['itens']['ultima_milha']=dict(responsavel='comprador')
        r=self.calcular()
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],140)
        self.assertEqual(next(x for x in self.dados(r)['linhas'] if x['id']=='ultima_milha')['estado'],'fora_escopo')
        self.cfg['escopo'].update(ate='cliente',local_final_entrega='Cliente A')
        self.cfg['escopo']['trechos']['destino']=dict(estado='contemplado',premissa='Custo conhecido de 20')
        r=self.calcular()
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],160)
        self.assertEqual(r['cobertura']['confirmada'],'cliente')

    def test_base_zero_e_ausente_sem_divisao(self):
        self.v.update(minimo=0,maximo=0)
        r=self.dados(self.calcular())
        self.assertEqual(r['total_estimado']['minimo'],40)
        self.assertIsNone(r['percentual_acrescimo'])
        self.assertIn('zero',r['motivo_percentual'])
        self.cfg['base_vendedor']={}
        self.assertIsNone(self.dados(self.calcular(),'vendedor')['percentual_acrescimo'])

    def test_faixas_abertas_dependencia_fiscal_sem_razao_enganosa(self):
        self.v.update(minimo=100,maximo=None,referencia_superior=200)
        b=self.base()
        c=dict(pais_origem='BR',pais_procedencia='BR',pais_destino='IT',data_referencia='2026-11-05',quantidade=1,classificacao={})
        regra=dict(id='a',nome='Hipótese A',versao='manual-1',jurisdicao='IT',escopo='importacao_destino',tipo_calculo='percentual',
            aliquota=10,valor_fixo=None,moeda='BRL',componentes_base=['mercadoria'],situacao='aplicavel',participa_total=True,
            incluido_em=None,estado_regra='manual',cambio_base='referencia')
        f=calcular_tributos(c,[regra],b)
        self.cfg['itens']['tributo:a']=dict(responsavel='comprador')
        for lado in ('comprador','vendedor'):self.cfg['tributos'][lado]['estado']='usar_cenario'
        r=self.calcular(fiscal=f);d=self.dados(r)
        self.assertEqual(d['total_estimado'],dict(minimo=D(150),maximo=None,referencia_superior=D(260)))
        self.assertIsNone(d['percentual_acrescimo'])
        self.assertTrue(all(x['participacao_no_total'] is None for x in d['linhas']))
        self.assertIn('manual',r['perspectivas']['comprador']['naturezas'])
        self.assertEqual(r['fonte_tributaria']['regras'][0]['versao'],'manual-1')

    def test_arredondamento_reconcilia_linhas_e_categorias(self):
        self.v.update(minimo=100,maximo=100)
        self.log['despesas'][0]['valor']='.005';self.log['despesas'][1]['valor']='.005'
        d=self.dados(self.calcular())
        self.assertEqual(d['total_estimado']['minimo'],D('100.02'))
        self.assertEqual(sum(x['valor_considerado']['minimo'] for x in d['linhas'] if x['valor_considerado'] is not None),d['total_estimado']['minimo'])
        self.assertEqual(sum(f['minimo'] for f in d['por_categoria'].values()),d['total_estimado']['minimo'])

    def test_quantidade_inteira_positiva_e_consistente(self):
        for q in (0,-1,True,1.5):
            with self.subTest(q=q),self.assertRaises(ValueError):consolidar_custos(self.base(),q,self.cfg)
        with self.assertRaises(ValueError):consolidar_custos(self.base(),2,self.cfg)

    def test_incoterm_sem_matriz_e_ausencia_de_tributos_nao_e_zero(self):
        self.cfg['contrato']=dict(incoterm='CIF',versao='2020',local_nomeado='Porto X')
        r=self.calcular()
        self.assertEqual(self.dados(r)['total_estimado']['minimo'],140)
        self.assertEqual(self.dados(r,'vendedor')['total_estimado']['minimo'],60)
        self.cfg['contrato']['local_nomeado']=None
        self.assertEqual(self.dados(self.calcular())['estado_dados'],'parcial')
        self.cfg['contrato']={};self.cfg['tributos']['comprador']={'estado':'nao_informado'}
        self.assertEqual(self.dados(self.calcular())['subtotal_conhecido']['minimo'],140)
        self.assertIsNone(self.dados(self.calcular())['total_estimado'])

    def test_tributos_incluidos_reutilizados_sem_dupla_cobranca(self):
        b=self.base()
        c=dict(pais_origem='BR',pais_procedencia='BR',pais_destino='IT',data_referencia='2026-11-05',quantidade=1,classificacao={})
        a=dict(id='a',nome='Tributo manual',versao='manual-1',jurisdicao='IT',escopo='importacao_destino',tipo_calculo='percentual',aliquota=10,
            valor_fixo=None,moeda='BRL',componentes_base=['mercadoria'],situacao='aplicavel',participa_total=True,incluido_em=None,estado_regra='manual',cambio_base='referencia')
        incluido=dict(a,id='incluido',situacao='incluido',incluido_em='tributo:a')
        f=calcular_tributos(c,[a,incluido],b)
        self.cfg['itens'].update({'tributo:a':dict(responsavel='comprador'),'tributo:incluido':dict(responsavel='comprador')})
        for lado in ('comprador','vendedor'):self.cfg['tributos'][lado]['estado']='usar_cenario'
        r=self.calcular(fiscal=f);d=self.dados(r)
        self.assertEqual(d['total_estimado']['minimo'],150)
        self.assertEqual(d['tributos_conhecidos']['minimo'],10)
        self.assertEqual(d['percentual_acrescimo']['minimo'],50)
        self.assertEqual(next(x for x in d['linhas'] if x['id']=='tributo:incluido')['estado'],'incluido_em_outro')
        self.assertIn('manual',r['fonte_tributaria']['natureza_resultado'])

    def test_declaracao_sem_adicionais_aceita_zero_nao_aceita_positivo(self):
        b=self.base()
        c=dict(pais_origem='BR',pais_procedencia='BR',pais_destino='IT',data_referencia='2026-11-05',quantidade=1,classificacao={})
        a=dict(id='a',nome='Tributo zero',versao='manual-1',jurisdicao='IT',escopo='importacao_destino',tipo_calculo='fixo',aliquota=None,
            valor_fixo=0,moeda='BRL',componentes_base=[],situacao='aplicavel',participa_total=True,incluido_em=None,estado_regra='manual',cambio_base='referencia')
        self.cfg['itens']['tributo:a']=dict(responsavel='comprador')
        f=calcular_tributos(c,[a],b)
        self.assertEqual(self.dados(self.calcular(fiscal=f))['total_estimado']['minimo'],140)
        a['valor_fixo']=10;f=calcular_tributos(c,[a],b)
        self.assertIsNone(self.dados(self.calcular(fiscal=f))['total_estimado'])
        self.cfg['itens']['seguro'].update(responsavel='nao_definido',tratamento='incluido_preco',justificativa='Incluído, mas responsável ainda não definido')
        self.assertIsNone(self.dados(self.calcular(fiscal=f))['total_estimado'])

    def test_historico_preserva_responsabilidade_inclusao_taxas_e_resultados(self):
        r=serializar(self.calcular())
        with tempfile.TemporaryDirectory() as pasta,patch.object(historico,'BANCO',Path(pasta)/'teste.sqlite3'):
            historico.salvar('nova',dict(custos=r))
            historico.salvar('legada',dict(produto='Anterior'))
            r['configuracao']['itens']['seguro']['responsavel']='terceiro'
            with patch('calculos.consolidacao.consolidar_custos',side_effect=AssertionError('Não recalcular')):
                dados=historico.listar()
            salvo=next(x['custos'] for x in dados if 'custos' in x)
            self.assertEqual(salvo['configuracao']['itens']['seguro']['responsavel'],'comprador')
            self.assertEqual(salvo['perspectivas']['comprador']['por_moeda']['BRL']['total_estimado']['minimo'],'140.00')
            self.assertTrue(any('custos' not in x for x in dados))


if __name__=='__main__':unittest.main()
