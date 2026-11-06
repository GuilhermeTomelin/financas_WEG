# Consolidação de custos por perspectiva

Entrega de 05/11/2026. O simulador reúne os **resultados já calculados** de mercadoria, logística e tributos. A função `consolidar_custos` amplia `calculos/consolidacao.py`, reutiliza Decimal, `ROUND_HALF_UP`, `ConjuntoCotacoes` e as conversões dos componentes existentes. Não há novo motor de frete, seguro, tributos, precificação ou integração externa.

## Como conferir na interface

1. Execute `python -m streamlit run interface/app.py` e abra **Operações → Simulador**.
2. Selecione produto, variante, quantidade, portos, equipamento e moeda. BRL permite conferir identidade monetária sem rede.
3. Para usar despesas, configure **Fretes e rotas** e leve o cenário ao simulador. Para tributos, configure **Impostos** e transfira o cenário compatível. A compatibilidade física/fiscal já existente continua obrigatória.
4. Expanda **Configurar perspectivas, responsabilidades e cobertura**. Escolha comprador ou vendedor; registre Incoterm, edição e local nomeado se usados, origem/coleta, local final, data e alcance até porto ou cliente.
5. Declare os trechos de origem, marítimo e, quando necessário, destino, com premissas explícitas. Não há inferência automática de transporte até o cliente a partir do porto.
6. Para vendedor, use custo de origem do catálogo ou uma entrada manual independente. Selecione fabricação/compra, informe custo **por produto**, moeda e fonte. Uma faixa aberta é permitida; marque **Custo unitário definido** para um valor único. Os custos internos atuais do catálogo estão não informados; não são inventados.
7. Por perspectiva, escolha usar o cenário tributário compatível ou mantenha a pendência. A declaração manual de ausência de tributos adicionais exige premissa e não significa isenção legal. Ela não pode contradizer tributos adicionais registrados para aquela perspectiva.
8. Em cada cobrança, selecione responsável econômico, eventual pagador inicial e tratamento da inclusão. Ajustar inclusão exige premissa. Custos extras são cadastrados no editor já existente de fretes; não há editor concorrente na consolidação.
9. Confira as abas **Resumo**, **Composição dos custos** e **Responsabilidades e premissas**. Consulte/atualize câmbio pelo botão existente. Pares adicionais do custo interno participam do mesmo atualizador central; navegar não consulta a rede.
10. Use **Salvar simulação** e consulte **Histórico e relatórios → Consultar registro completo**. A cópia salva não é recalculada ao abrir.

## Perspectivas independentes

| Perspectiva | Base inicial | Adicionais |
| --- | --- | --- |
| Vendedor/exportador | Custo de fabricação **ou** compra por produto × quantidade | Despesas e tributos atribuídos economicamente ao vendedor, sem cobrança duplicada |
| Aquisição do comprador | Valor comercial do lote do catálogo | Despesas e tributos atribuídos ao comprador e ainda não incluídos no preço ou em outra cobrança |

Custo interno e preço comercial não são somados. **Não existe total global formado pela soma das duas perspectivas**: o preço comercial pode conter custos e margem do vendedor. Os indicadores não são preço recomendado, lucro ou margem. A ausência do custo interno não impede um comprador completo, pois essa base não participa da aquisição do comprador.

São calculadas ambas as perspectivas; o resumo mostra a selecionada, salva junto à operação. O custo interno informado na interface é uma hipótese da sessão: não altera o catálogo.

## Responsabilidade e Incoterms

A atribuição é **manual**, por componente: vendedor, comprador, terceiro ou não definido. Pagador inicial é um campo independente, sem efeito na soma. Responsabilidade não definida mantém o componente visível e gera pendência nas perspectivas que ele pode afetar. Custo atribuído a terceiro fica detalhado, sem ser somado ao comprador ou ao vendedor.

Incoterm, versão e local/porto nomeado são registros do cenário. Se houver termo sem edição ou local nomeado, o cálculo fica parcial. **Nenhum Incoterm possui sugestão automática documentada nesta entrega.** Não foi criada matriz jurídica nem atribuída uma despesa com base na transferência de risco. As regras da ICC não foram verificadas para automatização nesta etapa; essa verificação e a adequação ao modal/local são pendências para qualquer sugestão futura.

O usuário pode registrar condições particulares com justificativa. Elas permanecem manuais; não ganham selo de regra oficial ou revisão por especialista.

## Inclusões e estados

Os componentes originais permanecem no resultado com identificador, categoria, estado, participação, valor/moeda, conversões, natureza/fonte e referências de inclusão. Regras tributárias e suas versões também são preservadas. Atribuições e inclusões efetivas da consolidação ficam em campos próprios, sem alterar a origem.

| Tratamento | Efeito |
| --- | --- |
| Herdar | Mantém a inclusão/estado calculado no módulo de origem |
| Separado | Soma somente se houver valor independente disponível e responsabilidade da perspectiva; não inventa desmembramento de uma cobrança incluída |
| Incluído no preço comercial | Não soma novamente no comprador; no vendedor, só considera valor independente quando a responsabilidade econômica for do vendedor |
| Incluído no custo interno | Não soma novamente no vendedor; não usa preço comercial como base interna |
| Incluído em outra cobrança | Não soma novamente; a cobrança que inclui o item precisa estar disponível na mesma perspectiva |
| Não aplicável, isento fundamentado, excluído ou fora de escopo na origem | Sem adicional; motivo permanece na linha |
| Aplicável desconhecido, fórmula indisponível ou responsabilidade indefinida | Conhecidos permanecem, total completo fica indisponível na perspectiva afetada |

Referências inexistentes, autorreferências e ciclos de inclusão são rejeitados. Cadeias válidas são aceitas; uma cadeia sem cobertura conhecida mantém pendência. Uma despesa incluída no preço pode ter valor interno desconhecido: isso não impede usar o preço do comprador, mas impede inventar o custo do vendedor.

Ajustes de inclusão na consolidação não modificam a base de cálculo de um tributo já configurado. Revise a fórmula explícita na página fiscal quando preço/contrato passarem a incluir frete ou outros componentes. A consolidação não interpreta legislação nem decide como alterar a base fiscal por causa do Incoterm.

## Alcance e completude

O escopo registra origem, portos, entrega final, quantidade de produtos, moeda e data. O alcance padrão é o **porto de destino**. Despesas de categoria `terrestre_destino` são mantidas no detalhamento, mas ficam fora da soma quando o alcance escolhido termina no porto.

Para rotular até o cliente, são necessários local final e cobertura do último trecho declarada com premissa, além dos trechos anteriores. Uma indicação de não aplicabilidade também exige premissa explícita (por exemplo, entrega no próprio porto). Quando falta o último trecho, o rótulo mantém porto ou cobertura pendente; o escopo solicitado até o cliente fica parcial. Locais divergentes da logística utilizada ou capacidade insuficiente para o lote geram pendências. Essas declarações não comprovam contratação de transporte ou entrega real.

Completude e natureza das fontes são eixos separados. Dados completos podem continuar simulados, manuais ou didáticos. O resultado mantém a natureza dos tributos de origem: cenário manual continua manual após a soma. Não há cobertura jurídica integral de país nem garantia de custo real até o cliente.

Cada moeda/perspectiva tem suas pendências. Valor ou taxa ausente, responsabilidade não definida, base necessária desconhecida e cobertura pendente impedem o total completo. O subtotal conhecido continua visível. Uma despesa desconhecida atribuída somente ao vendedor não bloqueia o comprador. Câmbio exclusivo do custo interno ausente também não bloqueia BRL do comprador.

Ausência de regra tributária não é zero. Sem cenário compatível, a perspectiva permanece pendente até ser configurada ou haver declaração manual explícita de ausência de adicionais no escopo. Essa declaração não cria tributo, benefício, crédito ou isenção legal. Possíveis créditos não são abatidos do desembolso.

## Fórmulas, denominadores e faixas

Para cada perspectiva, lote e moeda:

```text
base inicial do vendedor = custo interno unitário × quantidade de produtos
base inicial do comprador = preço comercial do lote
total = base inicial + despesas adicionais + tributos adicionais
custo unitário = total / quantidade de produtos
acréscimo absoluto = soma dos adicionais efetivamente considerados
acréscimo percentual = acréscimo absoluto / base inicial × 100
participação de um componente = componente considerado / total × 100
```

A soma dos adicionais equivale a `total − base` sem subtrair extremos de faixas correlacionadas. O acréscimo conhecido pode ser mostrado em resultado parcial, sempre rotulado conhecido; não se torna total completo. Base e total são da mesma perspectiva, quantidade e moeda. O divisor unitário é o número de **produtos**, nunca caixas, paletes ou contêineres. Quantidade deve ser inteira positiva; quantidade vazia na interface remove a fotografia anterior.

O denominador do acréscimo é a base inicial. O denominador da participação é o total da perspectiva. Percentual de acréscimo só é exibido com dados completos e base definida positiva; participação só com total definido positivo e completo. Base zero, ausente ou variável e total variável/parcial deixam o indicador correspondente indisponível, com explicação. Não se escolhe ponto médio, não se divide extremos e não se apresenta limite percentual aproximado como comprovado. As faixas monetárias e limites abertos continuam disponíveis; para percentuais com base variável, esta entrega pede base definida em vez de implementar avaliação correlacionada de cenários.

As faixas e dependências já calculadas pelos módulos de frete e tributos são reutilizadas. Original e conversões por componente são preservados. Somente o custo interno novo precisa de conversão adicional pelo mecanismo central. As duas moedas são BRL e a escolhida, sem coluna duplicada em BRL. Sem cotação, a moeda afetada permanece parcial.

A política é `Decimal` e `ROUND_HALF_UP`: CLP sem casas; demais moedas habilitadas com duas. A soma usa os componentes monetários arredondados; o detalhamento e as categorias reconciliam com o subtotal conhecido/total. Base interna é arredondada por lote na moeda original e convertida; o valor unitário informado permanece nas entradas. Percentuais são derivados dos montantes exibidos. Não há divisão adicional por contêiner na consolidação.

### Exemplos independentes

- Base comercial total 100, frete separado 30 e seguro separado 10, ambos do comprador: total **140**, acréscimo **40**, percentual **40% sobre 100**. A participação do frete é `30/140 × 100`, diferente do acréscimo.
- Com quatro produtos de 25 cada, a mesma base total é 100; adicionais 40; total 140 e custo **35 por produto**.
- Custo interno 60, preço comercial 100, frete 30 do vendedor e seguro 10 do comprador: vendedor **90**, comprador **110**. Não se somam esses totais.
- Se os 30 de frete já estiverem no preço 100, comprador paga base 100 mais seguro 10 = **110**. O vendedor continua com 60 + frete 30 = **90**, se esse valor e responsabilidade forem conhecidos.
- Se frete 30 já inclui seguro 10, ambos do comprador: base 100 + cobrança 30 = **130**, sem acrescentar seguro novamente.
- Base comercial 100–limite aberto, referência superior 200, adicionais fixos 40 e tributo manual de 10% da mercadoria: total **150–limite aberto**, referência superior 260. O percentual de acréscimo fica indisponível para essa base variável.

## Arquivos, estado e histórico

- `calculos/consolidacao.py`: adaptação de componentes e consolidação das perspectivas, inclusões, cobertura e indicadores; não chama rede ou interface.
- `interface/custos.py`: configuração e apresentador compartilhado de resumo/composição/premissas.
- `interface/simulador.py`: composição do resultado, atualização cambial central e salvamento.
- `interface/relatorios.py`: apresentação da cópia salva, sem novo cálculo.
- `interface/app.py`: preservação das chaves `custo_` ao navegar.

Toda entrada relevante provoca novo resultado, inclusive responsabilidade, inclusão, base, quantidade, escopo, local, data e Incoterm. Erros de inclusão/base eliminam o resultado de custos da fotografia atual e preservam as entradas e a mensagem de erro; não reutilizam o total anterior. Contextos de produto/variante/rota/equipamento distintos têm chaves próprias de premissas, para evitar transportar um contrato para outra operação. Atualizar referência cambial recalcula as conversões pelas mesmas entradas.

Salvar copia entradas, perspectivas, componentes, responsabilidades econômicas/pagador, inclusões, Incoterm/local, cobertura, fontes, taxas, resultados e regras tributárias. O SQLite existente é reutilizado sem mudança de esquema; registros antigos continuam legíveis, identificados como sem consolidação por perspectiva, sem preenchimento retroativo. A leitura histórica não consulta rede nem recalcula com configuração atual.

## Verificações

```powershell
python -B -m unittest discover -s tests -p '*custos.py' -v
python -B -m unittest discover -s tests -v
```

Testes aritméticos independentes cobrem 100+40=140/40%, quantidade de produtos, perspectivas, inclusões, ciclos, desconhecidos, câmbio, alcance porto/cliente, base zero/ausente, faixas/dependências, arredondamento/reconciliação e histórico. AppTest cobre entrada manual, edição/invalidação, atribuição e inclusão, taxas extras no atualizador central, navegação, quantidade/data vazias e salvamento. Testes matemáticos não validam contratos, fontes ou leis.

`scripts/capturar_interface.py` inclui capturas do custo em 1440×1050 e 390×844 e registra exceções/rolagem horizontal em `docs/capturas/verificacao.json`. A revisão é local em Chrome; não constitui matriz completa de navegadores nem auditoria de acessibilidade.
