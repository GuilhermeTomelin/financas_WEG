"""Resultados aritméticos independentes; não atestam validade jurídica."""
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from calculos.tributos import (calcular_tributos,validar_classificacao,verificar_cenario,
    ErroTributario,assinatura_base_tributaria,aplicar_snapshot_tributario)
from calculos.consolidacao import consolidar_operacao
from calculos.fretes import serializar
from consumo.catalogo import carregar_dados_simulador
from consumo.conteineres import carregar_conteineres
from consumo.tributos import carregar_cenarios_tributarios
from consumo import historico


def regra(id_='a',**kw):
    r=dict(id=id_,nome=id_,versao='manual-1',jurisdicao='US',escopo='importacao_destino',
        tipo_calculo='percentual',aliquota=10,valor_fixo=None,moeda='BRL',componentes_base=['mercadoria'],
        situacao='aplicavel',participa_total=True,incluido_em=None,inicio_vigencia=None,fim_vigencia=None,
        estado_regra='manual',revisao_especialista='nao_revisada',fonte=None,consultado_em=None,
        fundamentacao=None,cambio_base='referencia',arredondamento='politica_monetaria')
    r.update(kw)
    return r


def taxa(valor=5,**kw):
    r=dict(origem='USD',destino='BRL',cotacao=valor,data_referencia='2026-11-05',
        fonte='Hipótese independente do teste',provedor='Teste',metodo='manual',consultado_em=None)
    r.update(kw)
    return r


def despesa(id_,valor,categoria='outras'):
    return dict(id=id_,nome=id_,valor=valor,moeda='BRL',categoria=categoria,base='conteiner' if id_=='frete_maritimo' else 'operacao',
        estado='conhecido',natureza='simulado',participa_total=True,incluido_em=None,componentes_base=[])


class TributosTests(unittest.TestCase):
    def setUp(self):
        cat,_=carregar_dados_simulador()
        self.v=deepcopy(cat['produtos'][0]['variantes'][0])
        self.v.update(minimo=100,maximo=100,referencia_superior=None)
        self.log=dict(origem='BRSSZ',destino='USNYC',conteiner=carregar_conteineres()[0],
            despesas=[despesa('frete_maritimo',10,'maritimo'),despesa('seguro',2,'seguro')])
        self.c=dict(pais_origem='BR',pais_procedencia='BR',pais_destino='US',data_referencia='2026-11-05',
            quantidade=1,produto_id=cat['produtos'][0]['id'],variante=self.v['nome'],
            classificacao=dict(codigo='000001',sistema='HS_SH',versao='2022',pais=None,codigo_sintetico=True),
            condicoes=dict(regime='EXERCICIO_SEM_PREFERENCIA',mercadoria_nova=True))
        self.contexto=dict(produto_id=self.c['produto_id'],variante=self.v,quantidade=1,
            origem_unlocode='BRSSZ',destino_unlocode='USNYC',conteiner_id=self.log['conteiner']['id'])

    def base(self,moeda='BRL',taxas=(),q=1):
        return consolidar_operacao(self.v,q,'BRL',moeda,taxas,logistica=self.log)

    def calcular(self,regras,**kw):
        return calcular_tributos(self.c,regras,self.base(),**kw)

    def test_exemplo_independente_base_dependente_e_fixo(self):
        # 100 + 10 + 2 = 112; A=10; B=(100+10+10)*5%=6; F=4.
        regras=[regra('b',aliquota=5,componentes_base=['mercadoria','frete_maritimo','tributo:a']),
                regra('f',tipo_calculo='fixo',valor_fixo=4),regra('a')]
        antes=deepcopy(regras)
        r=self.calcular(regras)
        brl=r['por_moeda']['BRL']
        self.assertEqual(brl['total_tributario']['minimo'],20)
        self.assertEqual(brl['subtotal_mercadorias_logistica']['minimo'],112)
        self.assertEqual(brl['subtotal_acrescido_tributos']['minimo'],132)
        self.assertEqual(brl['por_produto']['minimo'],20)
        self.assertEqual(brl['percentual_base_comercial']['minimo'],20)
        self.assertEqual(r['regras'][0]['base_calculada']['minimo'],120)
        self.assertEqual(r['estado'],'completo')
        self.assertIn('manual',r['natureza_resultado'])
        self.assertEqual(regras,antes)

    def test_fixo_uma_operacao_divisao_unidade(self):
        self.c['quantidade']=4
        r=calcular_tributos(self.c,[regra(tipo_calculo='fixo',valor_fixo=10)],self.base(q=4))
        self.assertEqual(r['por_moeda']['BRL']['total_tributario']['minimo'],10)
        self.assertEqual(r['por_moeda']['BRL']['por_produto']['minimo'],D('2.50'))

    def test_ciclos_dependencia_ausente_e_duplicidade(self):
        casos=[[regra(componentes_base=['tributo:a'])],
               [regra(componentes_base=['tributo:b']),regra('b',componentes_base=['tributo:a'])],
               [regra(componentes_base=['tributo:inexistente'])],[regra(),regra()],
               [regra(situacao='incluido',incluido_em='tributo:a')]]
        for rs in casos:
            with self.subTest(rs=rs),self.assertRaises(ErroTributario):self.calcular(rs)

    def test_validade_inclusive_e_fora(self):
        regra_=regra(inicio_vigencia='2026-01-01',fim_vigencia='2026-12-31')
        for dia in ('2026-01-01','2026-12-31'):
            self.c['data_referencia']=dia
            self.assertEqual(self.calcular([regra_])['regras'][0]['estado_calculo'],'calculado')
        for dia in ('2025-12-31','2027-01-01'):
            self.c['data_referencia']=dia
            r=self.calcular([regra_])
            self.assertEqual(r['regras'][0]['estado_calculo'],'fora_vigencia')
            self.assertIsNone(r['por_moeda']['BRL']['total_tributario'])

    def test_config_exata_pais_classificacao_versao_condicoes(self):
        config=carregar_cenarios_tributarios()['cenarios'][0]
        self.assertTrue(verificar_cenario(self.c,config)['compativel'])
        for campo,valor in [('pais_origem','CN'),('pais_procedencia','AR'),('pais_destino','MX')]:
            c=deepcopy(self.c);c[campo]=valor
            self.assertFalse(verificar_cenario(c,config)['compativel'])
        for campo,valor in [('codigo','000002'),('sistema','NCM'),('versao','2017')]:
            c=deepcopy(self.c);c['classificacao'][campo]=valor
            self.assertFalse(verificar_cenario(c,config)['compativel'])
        c=deepcopy(self.c);c['condicoes']['regime']='OUTRO'
        self.assertFalse(verificar_cenario(c,config)['compativel'])
        self.c['data_referencia']='2027-01-01'
        self.assertEqual(verificar_cenario(self.c,config)['estado'],'fora_vigencia')

    def test_dois_exercicios_completos_sem_validade_legal(self):
        configs=carregar_cenarios_tributarios()['cenarios']
        self.assertEqual([x['estado'] for x in configs],['exemplo_didatico']*2)
        r=self.calcular(configs[0]['regras'],config=configs[0])
        # A=5, B=10.5, fixo=2.5 => 18; subtotal 112+18=130.
        self.assertEqual(r['por_moeda']['BRL']['subtotal_acrescido_tributos']['minimo'],130)
        c=deepcopy(self.c);c['pais_destino']='MX';c['valor_aduaneiro']=configs[1]['valor_aduaneiro_exemplo']
        r=calcular_tributos(c,configs[1]['regras'],self.base(),config=configs[1])
        self.assertEqual(r['por_moeda']['BRL']['total_tributario']['minimo'],12)
        self.assertIn('didático',r['natureza_resultado'])

    def test_formato_nao_e_confirmacao_preserva_zeros(self):
        c=validar_classificacao(self.c['classificacao'])
        self.assertTrue(c['formato_valido']);self.assertEqual(c['codigo'],'000001')
        self.assertTrue(c['avisos'])
        with self.assertRaises(ErroTributario):validar_classificacao(dict(codigo=100001,sistema='HS_SH'))
        self.assertFalse(validar_classificacao(dict(codigo='12345678',sistema='HS_SH'))['formato_valido'])
        self.assertTrue(validar_classificacao(dict(codigo='00000001',sistema='NCM'))['formato_valido'])
        self.assertFalse(validar_classificacao(dict(codigo='00000001',sistema='nacional_destino'))['formato_valido'])
        self.assertTrue(validar_classificacao(dict(codigo='00000001',sistema='nacional_destino',tamanho_declarado=8))['formato_valido'])

    def test_origem_nao_e_embarque_e_tributo_brasileiro_nao_e_importacao_destino(self):
        self.c['pais_origem']='CN'
        r=self.calcular([regra(jurisdicao='BR',escopo='exportacao_origem')])
        self.assertEqual(r['regras'][0]['estado_calculo'],'calculado')
        self.assertEqual(self.calcular([regra(jurisdicao='BR')])['regras'][0]['estado_calculo'],'nao_suportado')
        self.c['pais_destino']='BR'
        with self.assertRaises(ErroTributario):self.calcular([regra()])

    def test_zero_nao_informado_nao_aplicavel_isencao(self):
        r=self.calcular([regra('zero',aliquota=0),regra('pendente',aliquota=None),
                        regra('na',situacao='nao_aplicavel'),regra('isen',situacao='isento')])
        self.assertEqual([x['estado_calculo'] for x in r['regras']],['calculado_zero','nao_informado','nao_aplicavel','nao_informado'])
        self.assertEqual(r['por_moeda']['BRL']['total_tributario_conhecido']['minimo'],0)
        self.assertIsNone(r['por_moeda']['BRL']['total_tributario'])
        vazio=self.calcular([])
        self.assertIsNone(vazio['por_moeda']['BRL']['total_tributario_conhecido'])

    def test_url_nao_valida_regra_ou_isencao(self):
        config=deepcopy(carregar_cenarios_tributarios()['cenarios'][0])
        config.update(estado='documentado',fonte='https://example.invalid',consultado_em='2026-11-05')
        r=self.calcular([regra(estado_regra='documentado',fonte=config['fonte'])],config=config)
        self.assertFalse(r['compatibilidade']['compativel'])
        self.assertIsNone(r['regras'][0]['valor_original'])
        r=self.calcular([regra(estado_regra='documentado',fonte=config['fonte'])])
        self.assertEqual(r['regras'][0]['estado_calculo'],'nao_suportado')

    def test_isencao_exige_metadados_completos_sem_revisao_inferida(self):
        # Fixture estrutural inventada para testar o gate; não é cenário legal.
        config=deepcopy(carregar_cenarios_tributarios()['cenarios'][0])
        self.c['classificacao'].update(codigo='123456',codigo_sintetico=False,
            fonte='Fixture de confirmação externa do teste',validacao_conteudo='confirmada_externamente')
        config['classificacao']=deepcopy(self.c['classificacao'])
        config.update(estado='documentado',fonte='Fixture documental do teste',consultado_em='2026-11-05',
            verificacao_documental=dict(formula_base_excecoes_conferidas=True,responsavel='Fixture do teste'))
        rs=[regra(situacao='isento',estado_regra='documentado',fonte=config['fonte'],
            consultado_em='2026-11-05',fundamentacao='Fundamentação sintética do teste')]
        r=self.calcular(rs,config=config)
        self.assertEqual(r['regras'][0]['estado_calculo'],'isento')
        self.assertEqual(r['por_moeda']['BRL']['total_tributario']['minimo'],0)
        self.assertEqual(r['regras'][0]['revisao_especialista'],'nao_revisada')
        rs[0]['fundamentacao']=None
        self.assertEqual(self.calcular(rs,config=config)['regras'][0]['estado_calculo'],'nao_suportado')

    def test_cambio_referencia_original_e_ausencia(self):
        base=self.base('USD',[taxa()])
        r=calcular_tributos(self.c,[regra(moeda='USD')],base,[taxa()])
        self.assertEqual(r['regras'][0]['base_calculada']['minimo'],20)
        self.assertEqual(r['regras'][0]['valor_original']['minimo'],2)
        self.assertEqual(r['por_moeda']['BRL']['total_tributario']['minimo'],10)
        self.assertEqual(r['por_moeda']['USD']['total_tributario']['minimo'],2)
        self.assertTrue(any(q['metodo']=='inversa' for q in r['cotacoes_usadas']))
        r=calcular_tributos(self.c,[regra(moeda='USD')],self.base('USD'))
        self.assertIsNone(r['regras'][0]['valor_original'])
        self.assertIn(['BRL','USD'],r['pares_faltantes'])

    def test_aduaneiro_exige_taxa_propria_fonte_tipo_e_data(self):
        self.c['valor_aduaneiro']=dict(valor=100,moeda='USD',fonte='Hipótese explícita')
        rs=[regra(cambio_base='aduaneiro',componentes_base=['valor_aduaneiro'])]
        r=self.calcular(rs,cotacoes=[taxa()])
        self.assertIsNone(r['regras'][0]['valor_original'])
        self.assertIn(['USD','BRL'],r['pares_aduaneiros_faltantes'])
        adu=taxa(4,tipo_cambio='aduaneiro')
        r=self.calcular(rs,cotacoes=[taxa()],cotacoes_aduaneiras=[adu])
        self.assertEqual(r['regras'][0]['base_calculada']['minimo'],400)
        self.assertEqual(r['regras'][0]['valor_original']['minimo'],40)
        self.assertEqual(r['cotacoes_aduaneiras_usadas'][0]['cotacao'],4)
        for kw in (dict(tipo_cambio='referencia'),dict(data_referencia='2026-11-04'),dict(fonte=None)):
            errado=dict(adu,**kw)
            self.assertIsNone(self.calcular(rs,cotacoes=[taxa()],cotacoes_aduaneiras=[errado])['regras'][0]['valor_original'])

    def test_faixa_aberta_sem_ponto_medio_e_dependencias_monotonicas(self):
        self.v.update(minimo=100,maximo=None,referencia_superior=200)
        r=self.calcular([regra(),regra('b',componentes_base=['mercadoria','tributo:a'])])
        self.assertEqual(r['por_moeda']['BRL']['total_tributario'],dict(minimo=D(21),maximo=None,referencia_superior=D(42)))
        self.assertIsNone(r['por_moeda']['BRL']['percentual_base_comercial'])
        self.assertIsNone(r['por_moeda']['BRL']['subtotal_acrescido_tributos']['maximo'])

    def test_half_up_por_item_e_moeda(self):
        r=self.calcular([regra('a',tipo_calculo='fixo',valor_fixo='.005'),regra('b',tipo_calculo='fixo',valor_fixo='.005')])
        self.assertEqual(r['por_moeda']['BRL']['total_tributario']['minimo'],D('.02'))
        base=self.base('CLP',[taxa(1,origem='CLP',destino='BRL')])
        r=calcular_tributos(self.c,[regra(tipo_calculo='fixo',valor_fixo='2.5',moeda='CLP')],base,[taxa(1,origem='CLP',destino='BRL')])
        self.assertEqual(r['regras'][0]['valor_original']['minimo'],3)

    def test_incluido_sem_dupla_cobranca_e_cobertura_pendente(self):
        rs=[regra('a'),regra('incl',situacao='incluido',incluido_em='tributo:a'),
            regra('porto',situacao='incluido',incluido_em='despesa:seguro')]
        r=self.calcular(rs)
        self.assertEqual(r['por_moeda']['BRL']['total_tributario']['minimo'],10)
        self.assertEqual(r['por_moeda']['BRL']['subtotal_acrescido_tributos']['minimo'],122)
        self.assertEqual([x['estado_calculo'] for x in r['regras']],['calculado','incluido','incluido'])
        self.log['despesas'][1]['valor']=None
        self.log['despesas'][1]['estado']='desconhecido'
        self.assertEqual(self.calcular(rs)['regras'][2]['estado_calculo'],'nao_informado')

    def test_formula_especial_credito_e_arredondamento_nao_improvisados(self):
        for kw in (dict(tipo_calculo='por_dentro'),dict(creditos={'percentual':10}),dict(arredondamento='especial')):
            r=self.calcular([regra(**kw)])
            self.assertEqual(r['regras'][0]['estado_calculo'],'nao_suportado')
            self.assertIsNone(r['por_moeda']['BRL']['total_tributario'])

    def snapshot(self):
        return dict(assinatura_base=assinatura_base_tributaria(self.contexto,self.base()),
            entradas=dict(cenario=deepcopy(self.c),regras=[regra()],cotacoes_aduaneiras=[],config=None),
            resultado=serializar(self.calcular([regra()])))

    def test_snapshot_invalida_entradas_e_preserva_regras_ao_atualizar_cambio(self):
        snap=self.snapshot()
        aplicado=aplicar_snapshot_tributario(snap,self.contexto,self.base('USD',[taxa()]),[taxa()])
        self.assertIsNotNone(aplicado)
        self.assertEqual(aplicado['resultado']['por_moeda']['USD']['total_tributario']['minimo'],'2.00')
        self.assertNotIn('USD',snap['resultado']['por_moeda'])
        for campo,valor in [('quantidade',2),('produto_id','outro'),('destino_unlocode','MXVER'),('conteiner_id','outro')]:
            ctx=dict(self.contexto,**{campo:valor})
            self.assertIsNone(aplicar_snapshot_tributario(snap,ctx,self.base(),[]))
        self.log['despesas'][0]['valor']=20
        self.assertIsNone(aplicar_snapshot_tributario(snap,self.contexto,self.base(),[]))

    def test_historico_copia_integral_sem_recalculo_e_legado(self):
        foto=serializar(dict(tributacao=self.snapshot(),consolidacao=self.base()))
        with tempfile.TemporaryDirectory() as pasta,patch.object(historico,'BANCO',Path(pasta)/'simulacoes.sqlite3'):
            historico.salvar('nova',foto)
            historico.salvar('antiga',dict(produto='Registro anterior'))
            foto['tributacao']['entradas']['regras'][0]['aliquota']=99
            with patch('calculos.tributos.calcular_tributos',side_effect=AssertionError('Histórico não recalcula')):
                registros=historico.listar()
            nova=next(r for r in registros if 'tributacao' in r)
            self.assertEqual(nova['tributacao']['entradas']['regras'][0]['aliquota'],10)
            self.assertEqual(nova['tributacao']['resultado']['por_moeda']['BRL']['total_tributario']['minimo'],'10.00')
            self.assertEqual(next(r for r in registros if r.get('produto'))['produto'],'Registro anterior')

    def test_numeros_invalidos_nao_sao_zero(self):
        for valor in (-1,True,float('nan'),float('inf')):
            with self.subTest(valor=valor),self.assertRaises(ValueError):self.calcular([regra(aliquota=valor)])


if __name__=='__main__':
    unittest.main()
