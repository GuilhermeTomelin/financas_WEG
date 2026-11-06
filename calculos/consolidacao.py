"""Consolidação da mesma operação em BRL e na moeda selecionada, sem rede."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from calculos.cambio import ConjuntoCotacoes
from calculos.monetario import faixa, somar, arredondar, multiplicar, moeda
from calculos.operacoes import calcular_subtotal_faixa
from calculos.fretes import calcular_logistica


def consolidar_operacao(variante,quantidade,moeda_catalogo,moeda_apresentacao,cotacoes=(),logistica=None):
    conjunto=ConjuntoCotacoes(cotacoes)
    destinos=list(dict.fromkeys(['BRL',moeda_apresentacao]))
    original=faixa(calcular_subtotal_faixa(variante,quantidade))
    mercadoria=dict(id='mercadoria',nome='Mercadorias · preço comercial do catálogo',categoria='mercadorias',
                    natureza='simulado',moeda=moeda_catalogo,valor_original=original,estado='conhecido',participa_total=True,
                    base_comercial='Preço comercial da variante; custo de fabricação/compra não é somado.')
    itens=[mercadoria]
    resultado_logistica=None
    pendencias_comuns=[]
    if logistica is not None:
        args=deepcopy(logistica)
        for chave in ('produto_id','moeda','cotacoes'):
            args.pop(chave,None)
        args.update(variante=variante,quantidade=quantidade,moeda_apresentacao=moeda_apresentacao,
                    cotacoes=cotacoes,conjunto=conjunto)
        resultado_logistica=calcular_logistica(**args)
        # Pendências de câmbio são avaliadas por destino abaixo; as demais são comuns.
        pendencias_comuns=[p for p in resultado_logistica['pendencias'] if 'falta cotação' not in p or 'para sua base' in p]
        for d in resultado_logistica['despesas']:
            itens.append(dict(id=d['id'],nome=d['nome'],categoria=d['categoria'],natureza=d['natureza'],
                              moeda=d['moeda'],valor_original=deepcopy(d['total_original']),estado=d['estado'],
                              participa_total=d['participa_total'],incluido_em=d.get('incluido_em'),
                              parametro_original=deepcopy(d.get('valor')),base_cobranca=d['base']))
    else:
        pendencias_comuns.append('Logística não configurada para estas entradas; subtotal de mercadorias + logística indisponível.')
    por_moeda={}
    for item in itens:
        item['convertidos']={}
        item['taxas']={}
        for destino in destinos:
            f=item['valor_original']
            convertido=conjunto.converter(f,item['moeda'],destino) if f is not None else None
            item['convertidos'][destino]=arredondar(convertido,destino) if convertido is not None else None
            item['taxas'][destino]=deepcopy(conjunto.usadas.get((item['moeda'],destino))) if f is not None else None
    for destino in destinos:
        pendencias=list(pendencias_comuns)
        grupos={k:[] for k in ('mercadorias','frete_maritimo','seguro','demais_despesas')}
        conhecidos=[]
        grupos_pendentes=set()
        subtotais_originais={}
        for item in itens:
            ativo=item['participa_total'] and item['estado'] not in ('incluido','nao_aplicavel','excluido')
            if not ativo:
                continue
            grupo='mercadorias' if item['id']=='mercadoria' else 'frete_maritimo' if item['id']=='frete_maritimo' else 'seguro' if item['categoria']=='seguro' else 'demais_despesas'
            f=item['convertidos'][destino]
            if item['valor_original'] is not None:
                subtotais_originais.setdefault(item['moeda'],[]).append(item['valor_original'])
            if f is None:
                grupos_pendentes.add(grupo)
                pendencias.append(f"{item['nome']}: valor ou conversão {item['moeda']} → {destino} pendente.")
            else:
                grupos[grupo].append(f)
                conhecidos.append(f)
        pendencias.extend(conjunto.problemas)
        pendencias=list(dict.fromkeys(pendencias))
        totais={g:(None if g in grupos_pendentes else arredondar(somar(fs),destino) if fs else (None if g=='mercadorias' or logistica is None else faixa(0))) for g,fs in grupos.items()}
        conhecido=arredondar(somar(conhecidos),destino) if conhecidos else None
        por_moeda[destino]=dict(estado='parcial' if pendencias else 'completo',pendencias=pendencias,
                               grupos=totais,subtotal_conhecido=conhecido,
                               subtotal_mercadorias_logistica=conhecido if not pendencias else None,
                               subtotais_originais={m:arredondar(somar(fs),m) for m,fs in subtotais_originais.items()})
    return dict(versao=1,quantidade=quantidade,moeda_apresentacao=moeda_apresentacao,base_comercial=mercadoria['base_comercial'],itens=itens,
                por_moeda=por_moeda,estado='completo' if all(r['estado']=='completo' for r in por_moeda.values()) else 'parcial',
                cotacoes_usadas=list(conjunto.usadas.values()),pares_faltantes=[list(p) for p in sorted(conjunto.faltantes)],
                data_referencia=conjunto.data_referencia,resultado_logistica=resultado_logistica,
                politica='ROUND_HALF_UP por item e moeda (CLP: 0 casas; demais: 2). Total = soma dos itens exibidos. Sem impostos, spreads ou tarifas bancárias automáticas.')


RESPONSAVEIS=('vendedor','comprador','terceiro','nao_definido')
TRATAMENTOS=('herdar','separado','incluido_preco','incluido_outro','incluido_base_vendedor')


def componentes_custo(consolidacao,tributacao=None):
    """Adapta resultados existentes; não recalcula frete, seguro ou tributos."""
    log=consolidacao.get('resultado_logistica') or {}
    fontes={d['id']:d for d in log.get('despesas',[])}
    itens=[]
    for original in consolidacao['itens']:
        i=deepcopy(original)
        origem=fontes.get(i['id'],{})
        i.update(fonte=origem.get('fonte') or origem.get('observacoes') or i.get('fonte') or
                 ('Catálogo de preços simulados' if i['id']=='mercadoria' else 'Configuração logística da simulação'),
                 pendencias_origem=deepcopy(origem.get('pendencias',[])),tipo_componente='comercial' if i['id']=='mercadoria' else 'despesa')
        itens.append(i)
    fiscal=(tributacao or {}).get('resultado',tributacao or {})
    for r in fiscal.get('regras',[]):
        alvo=r.get('incluido_em')
        if alvo and alvo.startswith('despesa:'):alvo=alvo.split(':',1)[1]
        itens.append(dict(id='tributo:'+r['id'],nome=r['nome'],categoria='tributos',tipo_componente='tributo',
            valor_original=deepcopy(r['valor_original']),moeda=r['moeda'],convertidos=deepcopy(r['convertidos']),
            natureza=r['estado_regra'],fonte=r.get('fonte') or 'Regra '+r['estado_regra']+' sem fonte legal',
            estado=r['estado_calculo'],participa_total=r['participa_total'],incluido_em=alvo,
            pendencias_origem=deepcopy(r['pendencias']),regra_original=deepcopy(r)))
    return itens


def consolidar_custos(consolidacao,quantidade,configuracao,cotacoes=(),tributacao=None):
    """Duas perspectivas independentes, sobre os componentes monetários já calculados.

    A atribuição econômica e a cobertura são declarações manuais. Não interpreta
    Incoterms, não forma preço de venda e não combina totais das perspectivas.
    """
    if type(quantidade) is not int or quantidade<1:
        raise ValueError('Quantidade de produtos deve ser inteira e positiva.')
    if consolidacao.get('quantidade',quantidade)!=quantidade:
        raise ValueError('Quantidade incompatível com a consolidação monetária.')
    cfg=deepcopy(configuracao)
    if cfg.get('perspectiva') not in ('comprador','vendedor'):
        raise ValueError('Selecione comprador ou vendedor.')
    escopo=cfg.get('escopo') or {}
    try:date.fromisoformat(escopo.get('data_simulacao'))
    except (ValueError,TypeError) as erro:raise ValueError('Informe data ISO da simulação.') from erro
    if escopo.get('ate') not in ('porto_destino','cliente'):
        raise ValueError('Destino do escopo deve ser porto ou cliente.')
    conjunto=ConjuntoCotacoes(cotacoes)
    itens=componentes_custo(consolidacao,tributacao)
    inicial=cfg.get('base_vendedor') or {}
    if inicial.get('tipo') not in ('fabricacao','compra',None):
        raise ValueError('Base do vendedor deve ser fabricação ou compra.')
    valor=inicial.get('valor_unitario')
    base_vendedor=None
    if valor is not None:
        moeda(inicial.get('moeda'))
        if not inicial.get('tipo') or not inicial.get('fonte'):
            raise ValueError('Custo interno preenchido exige tipo e fonte próprios, separados do preço comercial.')
        base_vendedor=arredondar(multiplicar(faixa(valor),Decimal(quantidade)),inicial['moeda'])
    itens.insert(1,dict(id='base_vendedor',nome='Custo de '+str(inicial.get('tipo') or 'origem não informado'),
        categoria='base_inicial',tipo_componente='interno',valor_original=base_vendedor,moeda=inicial.get('moeda'),
        natureza=inicial.get('natureza') or 'nao_informado',fonte=inicial.get('fonte'),estado='conhecido' if base_vendedor else 'desconhecido',
        participa_total=True,incluido_em=None,pendencias_origem=[],convertidos={}))
    por_id={i['id']:i for i in itens}
    if len(por_id)!=len(itens):raise ValueError('Identificador reservado ou duplicado entre bases, despesas e tributos.')
    atribuicoes=cfg.get('itens') or {}
    sobras=set(atribuicoes)-set(por_id)
    if sobras:raise ValueError('Atribuição referencia componente inexistente: '+', '.join(sorted(sobras)))
    for i in itens:
        id_=i['id']
        a=atribuicoes.get(id_,{})
        responsavel='comprador' if id_=='mercadoria' else 'vendedor' if id_=='base_vendedor' else a.get('responsavel','nao_definido')
        if responsavel not in RESPONSAVEIS or a.get('pagador_inicial','nao_definido') not in RESPONSAVEIS:
            raise ValueError('Responsável/pagador desconhecido: '+id_)
        modo=a.get('tratamento','herdar')
        if modo not in TRATAMENTOS:raise ValueError('Tratamento de inclusão desconhecido: '+id_)
        incluido=i.get('incluido_em') if i['estado']=='incluido' else None
        if modo=='incluido_preco':incluido='mercadoria'
        elif modo=='incluido_base_vendedor':incluido='base_vendedor'
        elif modo=='incluido_outro':incluido=a.get('incluido_em')
        elif modo=='separado':
            # Não desmembra montantes indisponíveis dentro de outra cobrança.
            incluido=None
        if id_ in ('mercadoria','base_vendedor') and modo!='herdar':
            raise ValueError('A base inicial não pode ser incluída em outro componente.')
        if modo!='herdar' and not (a.get('justificativa') or '').strip():
            raise ValueError('Ajuste particular exige justificativa: '+id_)
        i.update(responsavel=responsavel,pagador_inicial=a.get('pagador_inicial','nao_definido'),
            tratamento=modo,incluido_em_efetivo=incluido,condicao_particular=a.get('justificativa'),atribuicao='manual')
        if incluido is not None and incluido not in por_id:
            raise ValueError('Inclusão em componente inexistente: '+id_+' → '+str(incluido))
        if modo=='incluido_outro' and not incluido:
            raise ValueError('Informe o componente que inclui '+id_)
    visitados=set()
    def validar_inclusao(id_,pilha):
        if id_ in pilha:raise ValueError('Ciclo de inclusões entre componentes de custo.')
        if id_ in visitados:return
        alvo=por_id[id_]['incluido_em_efetivo']
        if alvo:validar_inclusao(alvo,pilha|{id_})
        visitados.add(id_)
    for id_ in por_id:validar_inclusao(id_,set())
    destinos=list(consolidacao['por_moeda'])
    for i in itens:
        for destino in destinos:
            if destino not in i['convertidos']:
                f=conjunto.converter(i['valor_original'],i['moeda'],destino) if i['valor_original'] is not None else None
                i['convertidos'][destino]=arredondar(f,destino) if f is not None else None
            elif i['convertidos'][destino] is not None:
                i['convertidos'][destino]=faixa(i['convertidos'][destino])
    fiscal=(tributacao or {}).get('resultado',tributacao or {})
    contrato=cfg.get('contrato') or {}
    pendencias_escopo=[]
    for campo in ('local_origem','porto_embarque','porto_destino'):
        if not (escopo.get(campo) or '').strip():pendencias_escopo.append('Local do escopo não informado: '+campo)
    if contrato.get('incoterm') and (not contrato.get('versao') or not contrato.get('local_nomeado')):
        pendencias_escopo.append('Incoterm informado exige versão e local/porto nomeado; atribuição permanece manual.')
    trechos=escopo.get('trechos') or {}
    necessarios=['origem','maritimo']+(['destino'] if escopo['ate']=='cliente' else [])
    for trecho in necessarios:
        t=trechos.get(trecho,{})
        if t.get('estado') not in ('contemplado','nao_aplicavel') or not (t.get('premissa') or '').strip():
            pendencias_escopo.append('Cobertura do trecho '+trecho+' não confirmada com premissa explícita.')
    if escopo['ate']=='cliente' and not (escopo.get('local_final_entrega') or '').strip():
        pendencias_escopo.append('Local final de entrega não informado.')
    log=consolidacao.get('resultado_logistica')
    if log:
        capacidade=log.get('capacidade') or {}
        if not capacidade.get('compativel') or not capacidade.get('atende'):
            pendencias_escopo.append('Logística não confirma capacidade de transporte do lote completo.')
        locais=(log.get('premissas') or {}).get('locais') or {}
        for campo,trecho in (('terrestre_origem','local_origem'),('terrestre_destino','local_final_entrega')):
            if campo=='terrestre_destino' and escopo['ate']!='cliente':continue
            if locais.get(campo) and locais[campo].strip()!=(escopo.get(trecho) or '').strip():
                pendencias_escopo.append('Local do escopo difere da logística utilizada: '+trecho)
    perspectivas={}
    neutros=('nao_aplicavel','isento','fora_escopo','excluido')
    for perspectiva,base_id in (('comprador','mercadoria'),('vendedor','base_vendedor')):
        por_moeda={}
        for destino in destinos:
            ps=list(pendencias_escopo)+list(conjunto.problemas)
            linhas={}
            def avaliar(id_):
                if id_ in linhas:return linhas[id_]
                i=por_id[id_]
                r=dict(id=id_,valor_considerado=None,participacao_no_total=None,estado='nao_somado',motivo='')
                linhas[id_]=r
                if id_==base_id:
                    r.update(estado='base_inicial',valor_considerado=i['convertidos'][destino],motivo='Base exclusiva desta perspectiva.')
                    if r['valor_considerado'] is None:
                        ps.append('Base inicial da perspectiva '+perspectiva+' não informada ou sem conversão para '+destino)
                    return r
                if id_ in ('mercadoria','base_vendedor'):
                    r['motivo']='Base da outra perspectiva; não é somada.'
                    return r
                if not i['participa_total'] or i['estado'] in neutros:
                    r.update(estado='fora_escopo' if not i['participa_total'] else i['estado'],motivo='Sem cobrança adicional conforme estado registrado na origem.')
                    return r
                if i['categoria']=='terrestre_destino' and escopo['ate']=='porto_destino':
                    r.update(estado='fora_escopo',motivo='Trecho posterior ao porto de destino, fora do alcance escolhido; permanece registrado.')
                    return r
                alvo=i['incluido_em_efetivo']
                if i['responsavel']=='nao_definido':
                    r.update(estado='responsabilidade_nao_definida',motivo='Responsável econômico não definido; pode afetar esta perspectiva.')
                    ps.append(i['nome']+': responsável econômico não definido.')
                    return r
                if alvo==base_id:
                    pai=avaliar(base_id)
                    r.update(estado='incluido_na_base',motivo='Incluído na base desta perspectiva; não somado novamente.')
                    if pai['valor_considerado'] is None:
                        ps.append(i['nome']+': base que inclui o item indisponível.')
                    return r
                # Uma inclusão no preço não elimina um custo econômico do vendedor;
                # o preço não é sua base. Exige montante separado e atribuição própria.
                if i['responsavel']!=perspectiva:
                    r['motivo']='Custo atribuído a '+i['responsavel']+'; pagador inicial não muda essa atribuição.'
                    return r
                if alvo and alvo not in ('mercadoria','base_vendedor'):
                    pai=avaliar(alvo)
                    r.update(estado='incluido_em_outro',motivo='Incluído em '+alvo+'; não somado novamente.')
                    if pai['valor_considerado'] is None and pai['estado'] not in ('incluido_em_outro','incluido_na_base'):
                        ps.append(i['nome']+': cobrança que o inclui não está disponível nesta perspectiva.')
                    return r
                f=i['convertidos'][destino]
                if f is None:
                    r.update(estado='pendente',motivo='Montante ou câmbio indisponível; não se inventa desmembramento de valor incluído.')
                    ps.append(i['nome']+': valor ou câmbio pendente para '+destino)
                else:r.update(estado='adicionado',valor_considerado=f,motivo='Custo adicional atribuído economicamente a esta perspectiva.')
                if i.get('pendencias_origem'):
                    ps.extend(i['nome']+': '+p for p in i['pendencias_origem'] if 'falta cotação' not in p)
                return r
            for id_ in por_id:avaliar(id_)
            tratamento=(cfg.get('tributos') or {}).get(perspectiva,{})
            if tratamento.get('estado')=='sem_adicionais' and (tratamento.get('premissa') or '').strip():
                if any(i['tipo_componente']=='tributo' and (linhas[i['id']]['estado'] in ('pendente','responsabilidade_nao_definida') or (linhas[i['id']]['estado']=='adicionado' and linhas[i['id']]['valor_considerado']['maximo']!=0)) for i in itens):
                    ps.append('Declaração de ausência de tributos adicionais contradiz os componentes tributários desta perspectiva.')
            elif tratamento.get('estado')!='usar_cenario' or not fiscal.get('regras'):
                ps.append('Tributos adicionais não definidos para a perspectiva '+perspectiva+'. Ausência de regra não significa zero.')
            valores=[r['valor_considerado'] for r in linhas.values() if r['valor_considerado'] is not None]
            conhecido=arredondar(somar(valores),destino) if valores else None
            base=linhas[base_id]['valor_considerado']
            adicionais=[r['valor_considerado'] for id_,r in linhas.items() if id_!=base_id and r['valor_considerado'] is not None]
            adicional=arredondar(somar(adicionais),destino)
            valores_tributos=[linhas[i['id']]['valor_considerado'] for i in itens if i['tipo_componente']=='tributo' and linhas[i['id']]['valor_considerado'] is not None]
            impostos=arredondar(somar(valores_tributos),destino) if valores_tributos or (fiscal.get('regras') and tratamento.get('estado')=='usar_cenario') or (tratamento.get('estado')=='sem_adicionais' and tratamento.get('premissa')) else None
            categorias={}
            for i in itens:
                f=linhas[i['id']]['valor_considerado']
                if f is not None:
                    cat='base_inicial' if i['id']==base_id else i['categoria']
                    categorias.setdefault(cat,[]).append(f)
            categorias={k:arredondar(somar(v),destino) for k,v in categorias.items()}
            ps=list(dict.fromkeys(ps))
            completo=not ps
            percentual=None
            motivo=None
            if not completo:motivo='Percentual indisponível: dados incompletos para esta perspectiva e moeda.'
            elif base is None or base['minimo']==0:motivo='Percentual indisponível: base inicial ausente ou zero.'
            elif base['maximo']!=base['minimo']:motivo='Percentual indisponível: base variável; não se divide extremos nem se usa ponto médio. Informe base definida.'
            else:percentual=multiplicar(adicional,Decimal(100)/base['minimo'])
            if completo and conhecido and conhecido['minimo']>0 and conhecido['maximo']==conhecido['minimo']:
                for r in linhas.values():
                    if r['valor_considerado'] is not None:r['participacao_no_total']=multiplicar(r['valor_considerado'],Decimal(100)/conhecido['minimo'])
            div=lambda f:arredondar(multiplicar(f,Decimal(1)/quantidade),destino) if f is not None else None
            por_moeda[destino]=dict(estado_dados='completo' if completo else 'parcial',pendencias=ps,
                tipo_base='valor_comercial' if perspectiva=='comprador' else inicial.get('tipo'),base_inicial=base,base_unitaria=div(base),
                adicionais_conhecidos=adicional,tributos_conhecidos=impostos,
                despesas_adicionais_conhecidas=arredondar(somar([linhas[i['id']]['valor_considerado'] for i in itens if i['id']!=base_id and i['tipo_componente']!='tributo' and linhas[i['id']]['valor_considerado'] is not None]),destino),por_categoria=categorias,
                subtotal_conhecido=conhecido,unitario_conhecido=div(conhecido),total_estimado=conhecido if completo else None,
                total_unitario=div(conhecido) if completo else None,acrescimo_absoluto=adicional if base is not None else None,
                percentual_acrescimo=percentual,motivo_percentual=motivo,denominador_acrescimo=deepcopy(base),
                denominador_participacao=deepcopy(conhecido) if completo else None,linhas=list(linhas.values()))
        perspectivas[perspectiva]=dict(por_moeda=por_moeda,naturezas=sorted({i['natureza'] for i in itens if i['id']!=('base_vendedor' if perspectiva=='comprador' else 'mercadoria')}),
            atribuicao='Manual — condições particulares, sem interpretação automática de Incoterm')
    cobertura_porto=all((trechos.get(k) or {}).get('estado') in ('contemplado','nao_aplicavel') and (trechos.get(k) or {}).get('premissa') for k in ('origem','maritimo'))
    locais=((log or {}).get('premissas') or {}).get('locais') or {}
    cap=(log or {}).get('capacidade') or {}
    cobertura_porto=cobertura_porto and all((escopo.get(k) or '').strip() for k in ('local_origem','porto_embarque','porto_destino')) and (not log or (cap.get('compativel') and cap.get('atende'))) and (not locais.get('terrestre_origem') or locais['terrestre_origem'].strip()==escopo['local_origem'].strip())
    cobertura_cliente=cobertura_porto and escopo['ate']=='cliente' and bool(escopo.get('local_final_entrega')) and (trechos.get('destino') or {}).get('estado') in ('contemplado','nao_aplicavel') and bool((trechos.get('destino') or {}).get('premissa'))
    cobertura_cliente=cobertura_cliente and (not locais.get('terrestre_destino') or locais['terrestre_destino'].strip()==(escopo.get('local_final_entrega') or '').strip())
    alcance='cliente' if cobertura_cliente else 'porto_destino' if cobertura_porto else None
    rotulo='Custo estimado até o cliente em '+escopo['local_final_entrega'] if alcance=='cliente' else 'Custo estimado até o porto de destino' if alcance=='porto_destino' else 'Custo parcial — cobertura de transporte pendente'
    return dict(versao=1,quantidade_produtos=quantidade,perspectiva_selecionada=cfg['perspectiva'],configuracao=cfg,
        componentes=itens,perspectivas=perspectivas,cobertura=dict(confirmada=alcance,solicitada=escopo['ate'],rotulo=rotulo),
        cotacoes_usadas=list(conjunto.usadas.values()),cotacoes_monetarias=deepcopy(consolidacao['cotacoes_usadas']),
        fonte_tributaria=deepcopy(tributacao),premissas_logisticas=deepcopy((log or {}).get('premissas')),pares_faltantes=[list(p) for p in sorted(conjunto.faltantes)],
        politica=consolidacao['politica'],premissas='Perspectivas independentes, sem soma entre vendedor e comprador, sem preço sugerido, lucro, margem ou créditos automáticos. Completude refere-se apenas ao escopo declarado.')
