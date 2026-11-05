"""Catálogo versionado de cenários; nenhuma consulta fiscal externa no painel."""
import json
from pathlib import Path
from consumo.catalogo import ErroCatalogo
from consumo.portos import carregar_portos
from calculos.tributos import validar_regras,data_iso

CAMINHO=Path(__file__).resolve().parents[1]/'dados'/'cenarios_tributarios.json'


def carregar_cenarios_tributarios():
    try:
        dados=json.loads(CAMINHO.read_text(encoding='utf-8'))
        base,_=carregar_portos()
        ids=set()
        for c in dados['cenarios']:
            if c['id'] in ids or not c.get('versao'):
                raise ValueError('Cenário duplicado ou sem versão.')
            ids.add(c['id'])
            for campo in ('pais_origem','pais_procedencia','pais_destino'):
                if c[campo] not in base['paises']:
                    raise ValueError('País de cenário fora do cadastro.')
            if c['estado'] not in ('exemplo_didatico','documentado','revisao_pendente'):
                raise ValueError('Estado documental desconhecido.')
            for campo in ('inicio_vigencia','fim_vigencia'):
                if c.get(campo): data_iso(c[campo],campo)
            validar_regras(c['regras'])
        return dados
    except (OSError,ValueError,TypeError,KeyError) as erro:
        raise ErroCatalogo('Falha nos cenários tributários: '+str(erro)) from erro
