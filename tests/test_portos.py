import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from consumo.cambio import consultar_cotacao, ErroCambio
from consumo.portos import (carregar_portos, validar_base, buscar_portos, garantir_selecao,
                            invalidar_resultado, consultar_rota, dados_localidade)
from consumo import historico
from scripts.importar_unlocode import processar_zip, elegivel

ROOT = Path(__file__).resolve().parents[1]


class PortosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.config = carregar_portos()

    def test_base_completa_e_relacoes(self):
        validar_base(self.base)
        self.assertEqual(len(self.base["portos"]), self.base["metadados"]["total_localidades"])
        self.assertEqual(len(self.base["paises"]), self.base["metadados"]["total_paises"])
        self.assertGreater(len(buscar_portos(self.base, "BR")), 1)
        for campo, valor in (("pais_iso", "XX"), ("funcao", "--3-----"), ("status", "RQ")):
            base = dict(self.base, portos={"BRSSZ": dict(self.base["portos"]["BRSSZ"], **{campo: valor})})
            with self.assertRaises(ValueError):
                validar_base(base)

    def test_destinos_legados(self):
        legado = json.loads((ROOT / "dados/rotas.json").read_text(encoding="utf-8"))
        self.assertEqual(self.config["origem_padrao"], "BRSSZ")
        for iso in ("IT", "US", "DE", "MX", "CL", "ZA"):
            config = self.config["paises"][iso]
            self.assertEqual(config["moeda"], legado["destinos"][config["nome"]]["moeda"])
            self.assertEqual(self.base["portos"][config["porto_padrao"]]["pais_iso"], iso)
        self.assertEqual(self.base["portos"]["DEHAM"]["nome"], "Hamburg")

    def test_busca_codigo_acentos_favoritos(self):
        self.assertEqual(buscar_portos(self.base, "BR", "brssz")[0]["unlocode"], "BRSSZ")
        self.assertEqual(buscar_portos(self.base, "MX", "BRSSZ"), [])
        nome = next(p["nome"] for p in buscar_portos(self.base, "BR") if "São" in p["nome"])
        self.assertTrue(buscar_portos(self.base, "BR", nome.replace("São", "sao")))
        self.assertEqual(buscar_portos(self.base, "BR", favoritos=["BRSSZ"])[0]["unlocode"], "BRSSZ")

    def test_estado_e_rota_sem_frete(self):
        estado = dict(porto="BRSSZ", cambio_simulador={"cotacao": 1}, registro_salvo=123)
        garantir_selecao(estado, "porto", ["ITGIT"], "ITGIT")
        self.assertEqual(estado["porto"], "ITGIT")
        invalidar_resultado(estado, ("BRSSZ", "ITGIT", "EUR"))
        self.assertNotIn("cambio_simulador", estado)
        self.assertNotIn("registro_salvo", estado)
        self.assertIsNone(consultar_rota(self.config, "BRSSZ", "ITGIT"))
        comercial = dict(rotas=[dict(origem_unlocode="BRSSZ", destino_unlocode="ITGIT", frete=100, prazo=20)])
        self.assertEqual(consultar_rota(comercial, "BRSSZ", "ITGIT")["frete"], 100)
        self.assertIsNone(consultar_rota(comercial, "BRRIO", "ITGIT"))

    def test_moeda_nao_suportada_sem_rede(self):
        with patch("consumo.cambio.requests.get") as get:
            with self.assertRaisesRegex(ErroCambio, "Moeda não suportada"):
                consultar_cotacao("BRL", "XXX")
            get.assert_not_called()
            self.assertEqual(consultar_cotacao("BRL", "BRL")["cotacao"], 1)

    def test_historico_antigo_e_novo_sem_migrar(self):
        antigo = dict(produto="Motor W22", pais="Itália", origem={"pais": "Brasil", "porto": "Santos", "moeda": "BRL"},
                      destino={"porto": "Gioia Tauro", "moeda": "EUR"}, moeda="EUR")
        novo = dict(antigo, origem=dados_localidade(self.base, self.config, "BRSSZ"),
                    destino=dados_localidade(self.base, self.config, "ITGIT"), pais_iso="IT")
        with tempfile.TemporaryDirectory() as pasta, patch.object(historico, "BANCO", Path(pasta) / "teste.sqlite3"):
            historico.salvar("antigo", antigo)
            historico.salvar("novo", novo)
            registros = historico.listar()
            registro_antigo = next(r for r in registros if "pais_iso" not in r)
            self.assertEqual({k:v for k,v in registro_antigo.items() if k not in ("id", "salvo")}, antigo)
            self.assertEqual(next(r for r in registros if "pais_iso" in r)["origem"]["unlocode"], "BRSSZ")


class ImportadorTests(unittest.TestCase):
    def linha(self, **campos):
        r = ["", "BR", "SSZ", "Santos", "Santos", "SP", "1-------", "AA", "2501", "", "", ""]
        indices = dict(alteracao=0, local=2, nome=3, subdivisao=5, funcao=6, status=7, data=8)
        for k,v in campos.items():
            r[indices[k]] = v
        return r

    def zip(self, linhas):
        arquivo = io.BytesIO()
        with zipfile.ZipFile(arquivo, "w") as z:
            z.writestr("release/csv/SubdivisionCodes.csv", "BR,SP,São Paulo,Estado\n")
            for parte in (1, 2, 3):
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["", "BR", "", ".BRAZIL", "", "", "", "", "", "", "", ""])
                if parte == 1:
                    writer.writerows(linhas)
                z.writestr(f"release/csv/UNLOCODE CodeListPart{parte}.csv", buf.getvalue().encode("utf-8"))
        return arquivo.getvalue()

    def importar(self, linhas):
        return processar_zip(self.zip(linhas), "teste", "fonte de teste", "2026-11-05T00:00:00+00:00")

    def test_filtro_funcao_status_alteracao(self):
        self.assertTrue(elegivel(self.linha()))
        for k, v in (("funcao", "--3--6--"), ("funcao", "-------8"), ("status", "RQ"),
                     ("status", "XX"), ("status", "AQ"), ("status", "QQ"), ("status", "RN"),
                     ("alteracao", "X"), ("alteracao", "=")):
            with self.subTest(k=k, v=v):
                self.assertFalse(elegivel(self.linha(**{k:v})))
        base = self.importar([self.linha(), self.linha(local="ABC", funcao="---4----")])
        self.assertEqual(list(base["portos"]), ["BRSSZ"])
        self.assertEqual(base["portos"]["BRSSZ"]["nome_subdivisao"], "São Paulo")

    def test_duplicatas_e_conflitos(self):
        base = self.importar([self.linha(), self.linha(nome="Santos alternativo", data="2401")])
        self.assertEqual(len(base["portos"]), 1)
        self.assertIn("Santos alternativo", base["portos"]["BRSSZ"]["nomes_alternativos"])
        base = self.importar([self.linha(), self.linha(status="AI"), self.linha(local="RIO")])
        self.assertNotIn("BRSSZ", base["portos"])
        self.assertEqual(base["metadados"]["duplicatas_conflitantes_excluidas"], ["BRSSZ"])

    def test_codigo_invalido(self):
        with self.assertRaisesRegex(ValueError, "malformado"):
            self.importar([self.linha(local="S0Z")])

    def test_reprodutivel(self):
        zip_ = self.zip([self.linha()])
        args = (zip_, "teste", "fonte de teste", "2026-11-05T00:00:00+00:00")
        self.assertEqual(processar_zip(*args), processar_zip(*args))


if __name__ == "__main__":
    unittest.main()
