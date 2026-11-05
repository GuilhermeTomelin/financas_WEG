"""Tributos manuais/didáticos, sem interpretação automática de legislação."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
import re

from calculos.cambio import ConjuntoCotacoes
from calculos.monetario import faixa, decimal, moeda, somar, multiplicar, arredondar
from calculos.fretes import serializar


class ErroTributario(ValueError):
    pass


def data_iso(valor,campo):
    try:
        return date.fromisoformat(valor)
    except (TypeError,ValueError) as erro:
        raise ErroTributario(f'{campo}: informe data ISO válida.') from erro


def validar_classificacao(c):
    if not isinstance(c,dict):
        raise ErroTributario('Classificação deve ser um objeto.')
    codigo=c.get('codigo')
    if codigo is not None and not isinstance(codigo,str):
        raise ErroTributario('Código fiscal deve ser texto para preservar zeros iniciais.')
    sistema=c.get('sistema')
    tamanho={'HS_SH':6,'NCM':8}.get(sistema)
    if sistema=='nacional_destino':
        tamanho=c.get('tamanho_declarado')
        if tamanho is not None and (type(tamanho) is not int or not 1<=tamanho<=16):
            raise ErroTributario('Tamanho nacional declarado deve ser inteiro entre 1 e 16; não confirma padrão oficial.')
    elif sistema not in ('HS_SH','NCM',None):
        raise ErroTributario('Sistema de classificação desconhecido.')
    valido=bool(codigo and tamanho and re.fullmatch('[0-9]{'+str(tamanho)+'}',codigo))
    avisos=[]
    if not valido:
        avisos.append('Classificação não informada ou formato não confirmado. Simulação manual não valida classificação fiscal.')
    if c.get('validacao_conteudo')!='confirmada_externamente' or not c.get('fonte'):
        avisos.append('Classificação informada pelo usuário, sem confirmação externa registrada. Formato não comprova existência ou enquadramento correto.')
    if c.get('codigo_sintetico'):
        avisos.append('Código sintético de exercício; não é uma classificação real e não fundamenta regra oficial.')
    if sistema=='NCM':
        avisos.append('NCM brasileira não é classificação nacional universal do destino; não foi feita equivalência automática.')
    return dict(deepcopy(c),formato_valido=valido,avisos=avisos)


def verificar_cenario(cenario,config):
    """Compatibilidade exata, nunca por nome, prefixo ou semelhança."""
    if config is None:
        return dict(compativel=True,estado='manual',motivos=[])
    motivos=[]
    for campo in ('pais_origem','pais_procedencia','pais_destino'):
        if cenario.get(campo)!=config.get(campo):
            motivos.append('País incompatível: '+campo)
    classificacao=cenario.get('classificacao') or {}
    for campo,esperado in config.get('classificacao',{}).items():
        if classificacao.get(campo)!=esperado:
            motivos.append('Classificação incompatível: '+campo)
    for campo,esperado in config.get('condicoes',{}).items():
        if (cenario.get('condicoes') or {}).get(campo)!=esperado:
            motivos.append('Condição necessária ausente/incompatível: '+campo)
    dia=data_iso(cenario.get('data_referencia'),'Data da operação')
    fora=False
    for chave,teste in (('inicio_vigencia',lambda v:dia<v),('fim_vigencia',lambda v:dia>v)):
        if config.get(chave) and teste(data_iso(config[chave],chave)):
            fora=True
            motivos.append('Cenário fora da vigência/janela de aplicação configurada.')
    if config.get('estado')=='documentado':
        doc=config.get('verificacao_documental') or {}
        if not config.get('fonte') or not config.get('consultado_em') or not config.get('premissas') or not config.get('excecoes') or not doc.get('formula_base_excecoes_conferidas') or not doc.get('responsavel'):
            motivos.append('Documentação oficial e verificação da fórmula/base/exceções não foram registradas; uma URL isolada não valida a regra.')
        if not validar_classificacao(classificacao)['formato_valido'] or not classificacao.get('versao') or classificacao.get('codigo_sintetico') or classificacao.get('validacao_conteudo')!='confirmada_externamente' or not classificacao.get('fonte'):
            motivos.append('Classificação sem confirmação externa; não pode fundamentar cenário oficial.')
    elif config.get('estado')!='exemplo_didatico':
        motivos.append('Cenário em revisão ou não suportado.')
    return dict(compativel=not motivos,estado='fora_vigencia' if fora else 'nao_suportado' if motivos else 'compativel',motivos=list(dict.fromkeys(motivos)))


def validar_regras(regras):
    if not isinstance(regras,list):
        raise ErroTributario('Informe uma lista de tributos.')
    por_id={}
    for r in regras:
        if not isinstance(r,dict) or not isinstance(r.get('id'),str) or not r['id'] or r['id'] in por_id or ':' in r['id']:
            raise ErroTributario('Identificador de tributo ausente, duplicado ou inválido.')
        if not r.get('nome') or not r.get('versao'):
            raise ErroTributario('Nome e versão da regra são obrigatórios.')
        if r.get('situacao') not in ('aplicavel','nao_informado','nao_aplicavel','isento','incluido') or type(r.get('participa_total')) is not bool:
            raise ErroTributario('Situação/participação de tributo inválida.')
        if r.get('escopo') not in ('importacao_destino','exportacao_origem'):
            raise ErroTributario('Escopo tributário não suportado.')
        if r.get('estado_regra') not in ('manual','exemplo_didatico','documentado','revisao_pendente'):
            raise ErroTributario('Estado documental da regra inválido.')
        moeda(r.get('moeda'))
        if r.get('cambio_base') not in ('referencia','aduaneiro'):
            raise ErroTributario('Indique se a base usa câmbio de referência ou aduaneiro.')
        componentes=r.get('componentes_base',[])
        if not isinstance(componentes,list) or any(not isinstance(x,str) for x in componentes) or len(set(componentes))!=len(componentes):
            raise ErroTributario('Componentes da base inválidos ou duplicados.')
        for campo in ('aliquota','valor_fixo'):
            if r.get(campo) is not None:
                decimal(r[campo],campo)
        inicio=data_iso(r['inicio_vigencia'],'Início da vigência') if r.get('inicio_vigencia') else None
        fim=data_iso(r['fim_vigencia'],'Fim da vigência') if r.get('fim_vigencia') else None
        if inicio and fim and inicio>fim:
            raise ErroTributario('Intervalo de vigência invertido.')
        por_id[r['id']]=r
    def dependencias(r):
        componentes=[r.get('incluido_em')] if r['situacao']=='incluido' else r.get('componentes_base',[])
        return [x.split(':',1)[1] for x in componentes if isinstance(x,str) and x.startswith('tributo:')]
    visitados=set()
    def visitar(id_,pilha):
        if id_ in pilha:
            raise ErroTributario('Dependência circular entre tributos.')
        if id_ not in por_id:
            raise ErroTributario('Tributo dependente não cadastrado: '+id_)
        if id_ in visitados:
            return
        for dep in dependencias(por_id[id_]):
            visitar(dep,pilha|{id_})
        visitados.add(id_)
    for id_ in por_id:
        visitar(id_,set())
    return por_id


def calcular_tributos(cenario,regras,consolidacao,cotacoes=(),cotacoes_aduaneiras=(),config=None):
    cenario=deepcopy(cenario)
    regras=deepcopy(regras)
    for campo in ('pais_origem','pais_procedencia','pais_destino'):
        if not isinstance(cenario.get(campo),str) or not re.fullmatch('[A-Z]{2}',cenario[campo]):
            raise ErroTributario('Informe países ISO válidos: '+campo)
    if cenario['pais_procedencia']!='BR' or cenario['pais_destino']=='BR':
        raise ErroTributario('Fluxo suportado: embarque no Brasil e destino exterior. Importação para o Brasil não implementada.')
    dia=data_iso(cenario.get('data_referencia'),'Data da operação')
    quantidade=cenario.get('quantidade')
    if type(quantidade) is not int or quantidade<1:
        raise ErroTributario('Quantidade deve ser inteira e positiva.')
    classificacao=validar_classificacao(cenario.get('classificacao') or {})
    compat=verificar_cenario(cenario,config)
    por_id=validar_regras(regras)
    conjunto=ConjuntoCotacoes(cotacoes)
    data_adu=cenario.get('data_cambio_aduaneiro') or cenario['data_referencia']
    adu_validas=[]
    avisos=list(classificacao['avisos'])
    for q in cotacoes_aduaneiras:
        if q.get('tipo_cambio')!='aduaneiro' or q.get('data_referencia')!=data_adu or not q.get('fonte'):
            avisos.append('Taxa aduaneira informada sem tipo, fonte ou data requerida: não utilizada.')
        else:
            adu_validas.append(q)
    aduaneiro=ConjuntoCotacoes(adu_validas)
    itens_base={i['id']:i for i in consolidacao['itens']}
    resultados={}
    pendencias=[]
    if not regras:
        pendencias.append('Nenhum tributo configurado. Ausência de regra não significa ausência de imposto.')
    def pendente(r,estado,motivo):
        r['estado_calculo']=estado
        r['pendencias'].append(motivo)
        return r
    def avaliar(id_):
        if id_ in resultados:
            return resultados[id_]
        regra=por_id[id_]
        r=dict(deepcopy(regra),base_calculada=None,valor_original=None,formula=None,pendencias=[],estado_calculo='nao_informado',componentes_utilizados=[])
        resultados[id_]=r
        if not regra['participa_total']:
            r['estado_calculo']='fora_escopo'
            return r
        if not compat['compativel']:
            return pendente(r,compat['estado'],'; '.join(compat['motivos']))
        jurisdicao=cenario['pais_destino'] if regra['escopo']=='importacao_destino' else cenario['pais_procedencia']
        if regra.get('jurisdicao')!=jurisdicao:
            return pendente(r,'nao_suportado','Jurisdição da regra incompatível com o escopo e país da operação.')
        for chave,teste in (('inicio_vigencia',lambda v:dia<v),('fim_vigencia',lambda v:dia>v)):
            if regra.get(chave) and teste(data_iso(regra[chave],chave)):
                return pendente(r,'fora_vigencia','Regra fora da vigência/janela configurada; não aplicada.')
        if regra['estado_regra']=='documentado' and (not config or config.get('estado')!='documentado' or not regra.get('fonte') or not regra.get('consultado_em') or not regra.get('fundamentacao')):
            return pendente(r,'nao_suportado','Regra documentada sem fonte, fundamentação e cenário documental compatível; não aplicada.')
        if regra['estado_regra']=='revisao_pendente':
            return pendente(r,'nao_suportado','Regra em revisão pendente; não aplicada como regra válida.')
        if regra['situacao']=='nao_aplicavel':
            r['estado_calculo']='nao_aplicavel'
            return r
        if regra['situacao']=='isento':
            if regra['estado_regra']!='documentado' or not regra.get('fundamentacao') or not regra.get('fonte') or not config or config.get('estado')!='documentado':
                return pendente(r,'nao_informado','Isenção não fundamentada em cenário documentado compatível. Não foi atribuída alíquota zero.')
            r.update(estado_calculo='isento',formula='Isenção fundamentada, sem cobrança no escopo.')
            return r
        if regra['situacao']=='incluido':
            alvo=regra.get('incluido_em')
            if isinstance(alvo,str) and alvo.startswith('tributo:'):
                pai=avaliar(alvo.split(':',1)[1])
                coberto=pai['valor_original'] is not None or pai.get('cobertura_confirmada',False)
            else:
                chave=alvo.split(':',1)[1] if isinstance(alvo,str) and alvo.startswith('despesa:') else alvo
                pai=itens_base.get(chave,{})
                coberto=bool(pai.get('participa_total') and pai.get('valor_original') is not None and pai.get('estado') not in ('incluido','excluido','nao_aplicavel'))
            if not coberto:
                return pendente(r,'nao_informado','Item que inclui o tributo indisponível ou fora do escopo; não há cobertura confirmada.')
            r.update(estado_calculo='incluido',cobertura_confirmada=True,formula='Já incluído em '+str(alvo)+'; não somado novamente.')
            return r
        if regra['situacao']=='nao_informado':
            return pendente(r,'nao_informado','Tributo aplicável com informação pendente.')
        if regra.get('creditos') or regra.get('arredondamento') not in ('politica_monetaria',None):
            return pendente(r,'nao_suportado','Créditos ou arredondamento especial não implementados; nenhum abatimento foi aplicado.')
        if regra['tipo_calculo']=='fixo':
            if regra.get('valor_fixo') is None:
                return pendente(r,'nao_informado','Valor fixo não informado.')
            valor=faixa(regra['valor_fixo'])
            r['formula']='Valor fixo por operação; sem multiplicação adicional por produto ou contêiner.'
        elif regra['tipo_calculo']=='percentual':
            if regra.get('aliquota') is None or not regra.get('componentes_base'):
                return pendente(r,'nao_informado','Informe alíquota e componentes explícitos da base.')
            partes=[]
            ctx=aduaneiro if regra['cambio_base']=='aduaneiro' else conjunto
            for componente in regra['componentes_base']:
                if componente.startswith('tributo:'):
                    dep=avaliar(componente.split(':',1)[1])
                    f,de=dep['valor_original'],dep['moeda']
                    descricao=dep['nome']
                elif componente=='valor_aduaneiro':
                    dado=cenario.get('valor_aduaneiro') or {}
                    f=faixa(dado['valor']) if dado.get('valor') is not None and dado.get('fonte') else None
                    de=dado.get('moeda')
                    descricao='Valor aduaneiro informado explicitamente; não inferido do preço/custo.'
                else:
                    dep=itens_base.get(componente,{})
                    f=dep.get('valor_original') if dep.get('participa_total') and dep.get('estado') not in ('incluido','excluido','nao_aplicavel') else None
                    de=dep.get('moeda')
                    descricao=dep.get('nome',componente)
                if f is None:
                    r['pendencias'].append('Componente da base indisponível: '+componente)
                    continue
                convertido=ctx.converter(f,de,regra['moeda'])
                if convertido is None:
                    r['pendencias'].append(f"Base {componente}: câmbio {'aduaneiro requerido, não substituído pela Frankfurter' if regra['cambio_base']=='aduaneiro' else 'de referência'} {de} → {regra['moeda']} indisponível.")
                else:
                    partes.append(convertido)
                    r['componentes_utilizados'].append(dict(id=componente,nome=descricao,valor_original=deepcopy(f),moeda_original=de,valor_na_base=convertido,moeda_base=regra['moeda'],tipo_cambio=regra['cambio_base']))
            if r['pendencias']:
                return r
            r['base_calculada']=somar(partes)
            valor=multiplicar(r['base_calculada'],decimal(regra['aliquota'],'Alíquota')/100)
            r['formula']='('+' + '.join(regra['componentes_base'])+') × '+str(regra['aliquota'])+' / 100'
        else:
            return pendente(r,'nao_suportado','Fórmula não suportada: '+str(regra['tipo_calculo'])+'. Não foi usada fórmula genérica ou por dentro.')
        r.update(valor_original=arredondar(valor,regra['moeda']),estado_calculo='calculado_zero' if valor['minimo']==0 and valor['maximo']==0 else 'calculado')
        return r
    for id_ in por_id:
        avaliar(id_)
    linhas=[resultados[r['id']] for r in regras]
    for r in linhas:
        pendencias.extend(r['pendencias'])
        r['convertidos']={}
        for destino in consolidacao['por_moeda']:
            f=conjunto.converter(r['valor_original'],r['moeda'],destino) if r['valor_original'] is not None else None
            r['convertidos'][destino]=arredondar(f,destino) if f is not None else None
    por_moeda={}
    for destino,antes in consolidacao['por_moeda'].items():
        ps=list(pendencias)+list(conjunto.problemas)+list(aduaneiro.problemas)
        valores=[]
        for r in linhas:
            if r['valor_original'] is not None:
                f=r['convertidos'][destino]
                if f is None:
                    ps.append(r['nome']+': conversão de apresentação pendente para '+destino)
                else:
                    valores.append(f)
        conhecido=arredondar(somar(valores),destino) if valores else (None if ps else faixa(0))
        completo=not ps
        subtotal=antes['subtotal_mercadorias_logistica']
        acrescido=arredondar(somar([subtotal,conhecido]),destino) if subtotal is not None and conhecido is not None and completo else None
        mercadoria=antes['grupos']['mercadorias']
        percentual=None
        motivo_percentual=None
        if conhecido is not None and mercadoria is not None and mercadoria['maximo']==mercadoria['minimo'] and mercadoria['minimo']>0:
            percentual=multiplicar(conhecido,Decimal(100)/mercadoria['minimo'])
        else:
            motivo_percentual='Percentual equivalente indisponível: denominador comercial é faixa, zero ou indisponível; não se usa ponto médio.'
        if subtotal is None:
            ps.append('Subtotal de mercadorias + logística indisponível; não é possível apresentar soma acrescida dos tributos.')
        por_moeda[destino]=dict(total_tributario_conhecido=conhecido,total_tributario=conhecido if completo else None,
             por_produto=arredondar(multiplicar(conhecido,Decimal(1)/quantidade),destino) if conhecido is not None else None,
             percentual_base_comercial=percentual,denominador=deepcopy(mercadoria),motivo_percentual=motivo_percentual,
             subtotal_mercadorias_logistica=subtotal,subtotal_acrescido_tributos=acrescido,
             estado='parcial' if ps else 'completo',estado_tributos='completo' if completo else 'parcial',pendencias=list(dict.fromkeys(ps)))
    natureza='Simulação manual — regras não validadas' if config is None or any(r['estado_regra']=='manual' for r in regras) else 'Exemplo didático — sem validade legal' if config['estado']=='exemplo_didatico' else 'Cenário documentado — não equivale a revisão por especialista'
    return dict(versao=1,cenario=cenario,classificacao=classificacao,regras=linhas,compatibilidade=compat,
      natureza_resultado=natureza,avisos=avisos,por_moeda=por_moeda,estado='completo' if all(v['estado']=='completo' for v in por_moeda.values()) else 'parcial',
      cotacoes_usadas=list(conjunto.usadas.values()),cotacoes_aduaneiras_usadas=list(aduaneiro.usadas.values()),
      pares_faltantes=[list(p) for p in sorted(conjunto.faltantes)],pares_aduaneiros_faltantes=[list(p) for p in sorted(aduaneiro.faltantes)],
      premissas='Tributos do escopo configurado, sem créditos automáticos ou garantia de custo final. Faixas lineares propagadas; razão com base comercial variável indisponível.')


def assinatura_base_tributaria(contexto,consolidacao):
    log=consolidacao.get('resultado_logistica')
    dados=dict(contexto=contexto,itens=[{k:v for k,v in r.items() if k not in ('convertidos','taxas')} for r in consolidacao['itens']],
               premissas_logisticas=log['premissas'] if log else None)
    return hashlib.sha256(json.dumps(dados,sort_keys=True,ensure_ascii=False,default=str).encode('utf-8')).hexdigest()


def aplicar_snapshot_tributario(snapshot,contexto,consolidacao,cotacoes):
    if not snapshot or snapshot.get('assinatura_base')!=assinatura_base_tributaria(contexto,consolidacao):
        return None
    entradas=deepcopy(snapshot['entradas'])
    c=entradas['cenario']
    if (c['pais_procedencia'],c['pais_destino'])!=(contexto['origem_unlocode'][:2],contexto['destino_unlocode'][:2]):
        return None
    resultado=calcular_tributos(c,entradas['regras'],consolidacao,cotacoes,entradas.get('cotacoes_aduaneiras',[]),entradas.get('config'))
    return dict(assinatura_base=snapshot['assinatura_base'],entradas=entradas,base_monetaria=serializar(consolidacao),resultado=serializar(resultado))
