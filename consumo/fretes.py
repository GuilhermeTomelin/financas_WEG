"""Tarifas didáticas direcionais e modelos de despesas, sem atualização pelo painel."""
from copy import deepcopy
import json
from pathlib import Path
from datetime import date
from consumo.catalogo import ErroCatalogo
from consumo.portos import carregar_portos
from consumo.conteineres import carregar_conteineres
from calculos.fretes import validar_despesas, decimal, moeda

CAMINHO=Path(__file__).resolve().parents[1]/"dados"/"fretes_simulados.json"


def carregar_fretes():
    try:
        dados=json.loads(CAMINHO.read_text(encoding='utf-8'))
        modelos=validar_despesas(dados['despesas_modelo'])
        base,_=carregar_portos()
        ids={c['id'] for c in carregar_conteineres()}
        chaves=set()
        identidades=set()
        for t in dados['tarifas']:
            chave=(t['origem_unlocode'],t['destino_unlocode'],t['conteiner_id'])
            if chave in chaves or t['id'] in identidades or chave[0] not in base['portos'] or chave[1] not in base['portos'] or chave[2] not in ids:
                raise ValueError('Tarifa duplicada ou relação porto/equipamento inválida.')
            decimal(t['valor_unitario'],'Tarifa')
            moeda(t['moeda'])
            if not t.get('natureza') or not t.get('referencia'):
                raise ValueError('Natureza ou referência da tarifa ausente.')
            if t.get('validade') is not None:
                date.fromisoformat(t['validade'])
            for item in t['despesas_incluidas']:
                if item not in modelos or item=='frete_maritimo':
                    raise ValueError('Despesa incluída inválida.')
            chaves.add(chave)
            identidades.add(t['id'])
        return dados
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as erro:
        raise ErroCatalogo(f'Falha na configuração de fretes: {erro}') from erro


def buscar_tarifa(config,origem,destino,conteiner_id):
    tarifa=next((t for t in config['tarifas'] if (t['origem_unlocode'],t['destino_unlocode'],t['conteiner_id'])==(origem,destino,conteiner_id)),None)
    return deepcopy(tarifa)


def despesas_da_rota(config,tarifa):
    itens=deepcopy(config['despesas_modelo'])
    for d in itens:
        if d['id']=='frete_maritimo' and tarifa:
            d.update(valor=tarifa['valor_unitario'],moeda=tarifa['moeda'],natureza=tarifa['natureza'],estado='conhecido',observacoes=tarifa['observacoes'])
        elif tarifa and d['id'] in tarifa['despesas_incluidas']:
            d.update(estado='incluido',incluido_em='frete_maritimo',natureza=tarifa['natureza'])
    return itens
