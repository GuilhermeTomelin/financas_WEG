import copy
from decimal import Decimal as D
import unittest

from calculos.conteineres import (calcular_conteineres, preparar_carga, volume_m3,
                                  DadosLogisticosInvalidos)
from consumo.catalogo import carregar_dados_simulador
from consumo.conteineres import carregar_conteineres


class ConteineresTests(unittest.TestCase):
    def setUp(self):
        catalogo,_=carregar_dados_simulador()
        self.v=copy.deepcopy(catalogo["produtos"][0]["variantes"][0])
        e=self.v["dados_fisicos"]["unidade_embarque"]
        e.update(quantidade_produtos=1,peso_bruto_kg=10,usa_palete=False,palete_incluido=False)
        self.v["dados_fisicos"]["produto"]["peso_liquido_kg"]=1
        self.dims(50,50,50)
        self.pilha=self.v["dados_fisicos"]["empilhamento"]
        self.pilha.update(permitido=True,maximo_camadas=2,carga_sobreposta_maxima_kg=10,orientacoes_permitidas=["vertical"],restricoes="Manter na vertical; não tombar.")
        self.c=dict(id="teste",dimensoes_internas_cm=dict(comprimento=100,largura=100,altura=100),
                    porta_cm=dict(largura=100,altura=100),tara_kg=100,peso_bruto_maximo_kg=1100,carga_util_kg=1000)

    def dims(self,c,l,a):
        self.v["dados_fisicos"]["unidade_embarque"]["dimensoes_externas"]=dict(comprimento_cm=c,largura_cm=l,altura_cm=a)

    def calcular(self,qtd=1,manual=None):
        return calcular_conteineres(self.v,qtd,self.c,manual)

    def test_lote_pequeno_e_ultimo_parcial(self):
        r=self.calcular()
        self.assertEqual(r["capacidade_final"],8)
        self.assertEqual(r["quantidade_necessaria"],1)
        self.assertEqual(r["ocupacao_volumetrica_pct"],D('12.5'))
        r=self.calcular(9)
        self.assertEqual(r["quantidade_necessaria"],2)
        self.assertEqual([f["unidades_embarque"] for f in r["distribuicao"]],[8,1])
        self.assertEqual(r["distribuicao"][-1]["ocupacao_volumetrica_pct"],D('12.5'))

    def test_embalagem_parcial_conservadora(self):
        self.v["dados_fisicos"]["unidade_embarque"]["quantidade_produtos"]=4
        r=self.calcular(5)
        self.assertEqual(r["carga"]["unidades_embarque"],2)
        self.assertTrue(r["carga"]["embalagem_parcial"])
        self.assertEqual(r["carga"]["produtos_ultima_embalagem"],1)
        self.assertEqual(r["carga"]["peso_total_kg"],20)
        self.assertEqual(r["carga"]["volume_total_m3"],D('.25'))
        self.assertTrue(any("sem redução" in a for a in r["carga"]["avisos"]))

    def test_encaixe_exato_decimal(self):
        self.dims(.1,.1,.1)
        self.c["dimensoes_internas_cm"]=dict(comprimento=.3,largura=.3,altura=.3)
        self.c["porta_cm"]=dict(largura=.3,altura=.3)
        self.pilha.update(maximo_camadas=3,carga_sobreposta_maxima_kg=20)
        r=self.calcular()
        self.assertEqual(r["capacidade_geometrica"],27)
        self.assertEqual(volume_m3((100,100,100)),1)

    def test_limite_peso_sem_descontar_tara_novamente(self):
        self.c.update(carga_util_kg=25,peso_bruto_maximo_kg=125)
        r=self.calcular(9)
        self.assertEqual(r["capacidade_peso"],2)
        self.assertEqual(r["capacidade_final"],2)
        self.assertEqual(r["quantidade_necessaria"],5)
        self.assertEqual(r["limites"],["peso"])

    def test_empate_peso_geometria(self):
        self.c.update(carga_util_kg=80,peso_bruto_maximo_kg=180)
        self.assertEqual(self.calcular()["limites"],["peso","geometria"])

    def test_porta_menor_que_interior(self):
        self.dims(90,90,90)
        self.c["porta_cm"]["altura"]=80
        r=self.calcular()
        self.assertFalse(r["compativel"])
        self.assertIsNone(r["quantidade_necessaria"])
        self.assertTrue(any("porta" in m for m in r["motivos"]))

    def test_embalagem_maior_que_conteiner(self):
        self.dims(101,101,101)
        r=self.calcular()
        self.assertFalse(r["compativel"])
        self.assertIsNone(r["quantidade_necessaria"])
        self.assertEqual(r["distribuicao"],[])

    def test_uma_unidade_excede_peso(self):
        self.c.update(carga_util_kg=5,peso_bruto_maximo_kg=105)
        r=self.calcular()
        self.assertFalse(r["compativel"])
        self.assertIsNone(r["quantidade_necessaria"])
        self.assertTrue(any("carga útil" in m for m in r["motivos"]))

    def test_nao_empilhavel(self):
        self.pilha.update(permitido=False,maximo_camadas=1,carga_sobreposta_maxima_kg=0)
        r=self.calcular()
        self.assertEqual(r["disposicao"]["camadas"],1)
        self.assertEqual(r["capacidade_final"],4)
        self.assertIn("empilhamento",r["limites"])

    def test_limites_camadas_e_carga_sobreposta(self):
        self.dims(50,50,25)
        self.pilha.update(maximo_camadas=2,carga_sobreposta_maxima_kg=100)
        self.assertEqual(self.calcular()["disposicao"]["camadas"],2)
        self.pilha.update(maximo_camadas=4,carga_sobreposta_maxima_kg=10)
        r=self.calcular()
        self.assertEqual(r["disposicao"]["camadas"],2)
        self.assertEqual(r["capacidade_final"],8)

    def test_empilhamento_desconhecido_conservador(self):
        for campo in ("permitido","maximo_camadas","carga_sobreposta_maxima_kg"):
            with self.subTest(campo=campo):
                v=copy.deepcopy(self.v)
                v["dados_fisicos"]["empilhamento"][campo]=None
                r=calcular_conteineres(v,1,self.c)
                self.assertEqual(r["disposicao"]["camadas"],1)
                self.assertTrue(r["carga"]["avisos"])

    def test_orientacao_proibida_e_lateral_explicita(self):
        self.dims(150,50,50)
        self.c["dimensoes_internas_cm"]["altura"]=200
        self.c["porta_cm"]["altura"]=200
        self.assertFalse(self.calcular()["compativel"])
        self.pilha.update(orientacoes_permitidas=["lateral"],restricoes="Sem restrição adicional.")
        self.assertTrue(self.calcular()["compativel"])
        self.pilha["restricoes"]="Manter na vertical; não tombar."
        with self.assertRaisesRegex(DadosLogisticosInvalidos,"contradizem"):
            self.calcular()

    def test_giro_no_plano_horizontal(self):
        self.dims(90,50,50)
        self.c["dimensoes_internas_cm"].update(comprimento=100,largura=180)
        r=self.calcular()
        self.assertEqual(r["disposicao"]["dimensoes_cm"],(50,90,50))
        self.assertEqual(r["capacidade_final"],8)

    def test_dados_ausentes_invalidos_e_contraditorios(self):
        for valor in (None,0,-1,True,"50",float('nan'),float('inf')):
            with self.subTest(valor=valor):
                self.dims(50,50,valor)
                with self.assertRaises(DadosLogisticosInvalidos):
                    self.calcular()
        self.dims(50,50,50)
        for campo,valor in (("orientacoes_permitidas",None),("permitido","sim"),("maximo_camadas",0),("carga_sobreposta_maxima_kg",-1)):
            v=copy.deepcopy(self.v)
            v["dados_fisicos"]["empilhamento"][campo]=valor
            with self.assertRaises(DadosLogisticosInvalidos):
                calcular_conteineres(v,1,self.c)
        for qtd in (None,0,-1,True,1.5):
            with self.assertRaises(DadosLogisticosInvalidos):
                self.calcular(qtd)
            with self.assertRaises(DadosLogisticosInvalidos):
                self.calcular(1,qtd if qtd is not None else 0)
        self.pilha.update(permitido=False,maximo_camadas=2)
        with self.assertRaises(DadosLogisticosInvalidos):
            self.calcular()

    def test_estruturas_incompletas(self):
        for variante in ({}, None, {"dados_fisicos":None}, {"dados_fisicos":[]}):
            with self.subTest(variante=variante):
                with self.assertRaises(DadosLogisticosInvalidos):
                    calcular_conteineres(variante,1,self.c)
        self.v["dados_fisicos"]["unidade_embarque"]["tipo"]="outra"
        with self.assertRaisesRegex(DadosLogisticosInvalidos,"retangular"):
            self.calcular()

    def test_palete_contado_uma_vez(self):
        embarque=self.v["dados_fisicos"]["unidade_embarque"]
        embarque.update(usa_palete=True,palete_incluido=True)
        self.assertEqual(self.calcular(2)["carga"]["peso_total_kg"],20)
        embarque["palete_incluido"]=False
        with self.assertRaises(DadosLogisticosInvalidos):
            self.calcular()

    def test_manual_insuficiente_sem_ocupacao_ficticia(self):
        r=self.calcular(10,1)
        self.assertFalse(r["atende"])
        self.assertEqual(r["unidades_carregadas"],8)
        self.assertEqual(r["unidades_nao_atendidas"],2)
        self.assertEqual(r["ocupacao_volumetrica_pct"],100)
        self.assertEqual(r["posicoes_utilizadas_pct"],100)
        self.assertEqual(r["carga"]["volume_total_m3"],D('1.25'))

    def test_manual_excedente_com_conteiner_vazio(self):
        r=self.calcular(1,3)
        self.assertTrue(r["atende"])
        self.assertEqual(r["distribuicao"][-1]["unidades_embarque"],0)
        self.assertEqual(r["distribuicao"][-1]["quantidade_conteineres"],2)

    def test_distribuicao_e_totais_muitos_lotes(self):
        for qtd in (1,7,8,9,16,17,10000):
            for manual in (None,1,2,1000):
                with self.subTest(qtd=qtd,manual=manual):
                    r=self.calcular(qtd,manual)
                    dist=r["distribuicao"]
                    self.assertEqual(sum(f["quantidade_conteineres"] for f in dist),r["quantidade_avaliada"])
                    self.assertEqual(sum(f["quantidade_conteineres"]*f["unidades_embarque"] for f in dist),r["unidades_carregadas"])
                    self.assertEqual(r["unidades_carregadas"]+r["unidades_nao_atendidas"],qtd)
                    self.assertEqual(sum(f["quantidade_conteineres"]*f["peso_kg"] for f in dist),r["unidades_carregadas"]*10)
                    self.assertEqual(sum(f["quantidade_conteineres"]*f["volume_m3"] for f in dist),r["unidades_carregadas"]*D('.125'))
                    self.assertEqual(dist[0]["primeiro"],1)
                    self.assertEqual(dist[-1]["ultimo"],r["quantidade_avaliada"])
                    for faixa in dist:
                        self.assertLessEqual(faixa["unidades_embarque"],r["capacidade_final"])
                        self.assertLessEqual(faixa["peso_kg"],r["carga_util_kg"])
                        self.assertLessEqual(faixa["volume_m3"],r["volume_interno_m3"])

    def test_catalogo_inteiro_e_especificacoes(self):
        catalogo,_=carregar_dados_simulador()
        conteineres=carregar_conteineres()
        self.assertEqual(len(conteineres),3)
        antes=copy.deepcopy(catalogo)
        for produto in catalogo["produtos"]:
            for v in produto["variantes"]:
                for c in conteineres:
                    r=calcular_conteineres(v,123,c)
                    self.assertTrue(r["compativel"])
                    self.assertTrue(r["atende"])
                    self.assertGreater(r["capacidade_final"],0)
        self.assertEqual(catalogo,antes)
        self.c["carga_util_kg"]=1001
        with self.assertRaises(DadosLogisticosInvalidos):
            self.calcular()


if __name__=="__main__":
    unittest.main()
