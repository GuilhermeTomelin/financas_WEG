# Frete e despesas logísticas selecionadas

A página **Fretes e rotas → Simulação logística** reúne mercadoria, trajeto,
equipamento, quantidade, tarifa, despesas e seguro. A consulta UN/LOCODE anterior
permanece na aba **Consulta de portos**. O tema e a navegação foram preservados.
Não há cotação real de frete, tributos, Incoterms completos ou recomendação de preço.

## Arquivos e configuração

- `dados/fretes_simulados.json`: nove tarifas e sete despesas-base.
- `consumo/fretes.py`: carregamento, validação dos relacionamentos e cópias dos modelos.
- `calculos/fretes.py`: valores/faixas, validação, capacidade, despesas, câmbio e totais.
- `interface/fretes.py`: edição somente na sessão, importação e transferência de seleções.
- `interface/resumo_logistico.py`: resumo compartilhado entre páginas e histórico.

Cada tarifa contém `id`, `origem_unlocode`, `destino_unlocode`, `conteiner_id`,
`valor_unitario`, `moeda`, `natureza`, `referencia`, `validade`, `observacoes` e
`despesas_incluidas`. O identificador do equipamento é o mesmo da calculadora.
A busca exige correspondência exata de origem, destino e equipamento. Não
inverte o sentido, não amplia a tarifa por país e não confirma serviço regular.
Não havia tarifas comerciais no cadastro anterior; ele permanece intacto.

### Rotas de demonstração

Valores em USD **por contêiner**, sem proporção pela ocupação:

| Trajeto direcional | dry20 | dry40 | hc40 |
| --- | ---: | ---: | ---: |
| BRSSZ → ITGIT (Santos → Gioia Tauro) | 2.000 | 3.300 | 3.500 |
| BRSSZ → USLAX (Santos → Los Angeles) | 3.200 | 4.800 | 5.100 |
| BRSSZ → MXZLO (Santos → Manzanillo) | 1.800 | 2.800 | 3.000 |

São hipóteses educacionais do projeto, não preços oficiais ou cotações de
transportador. `validade=null` significa sem validade comercial aplicável ao
exemplo, não uma cotação com prazo indefinido garantido. A referência explica a
natureza didática, sem inventar consulta comercial. A documentação é declarada
incluída no frete destes exemplos. Não há prazos de viagem nem taxas reais novas.

Os modelos contêm portuárias de origem de BRL 450 por contêiner, portuárias de
destino de USD 250 por contêiner e percentual didático de seguro de 0,5%.
Esses parâmetros também são **simulados**; não são tarifas portuárias verificadas.
O seguro começa pendente por falta de escolha dos componentes da base.
Transporte terrestre começa com valor desconhecido. Local de coleta/entrega e
valor devem ser informados; país e porto não determinam sozinhos esse custo.
Para rota sem tarifa, o frete fica desconhecido e admite preenchimento manual.

## Modelo e estados de uma despesa

Campos: `id`, `nome`, `categoria`, `valor`, `moeda`, `base`, `natureza`, `estado`,
`participa_total`, `incluido_em`, `componentes_base` e `observacoes`.
`natureza` distingue `simulado`, `informado_manualmente` e `nao_informado`.
Alterações de valor, moeda, cobrança, participação, inclusão ou base percentual
ficam identificadas como informadas manualmente até restaurar o modelo.

Bases suportadas:

- `operacao`: valor cobrado uma vez, independentemente da quantidade de contêineres.
- `conteiner`: valor × quantidade de contêineres avaliada.
- `produto`: valor × quantidade de produtos do lote.
- `percentual`: percentual / 100 × soma dos componentes monetários escolhidos,
  convertidos para a moeda da despesa antes do cálculo percentual.

O frete marítimo FCL exige `conteiner`. Não recebe desconto proporcional por
baixa ocupação. A quantidade estimada é recalculada pelo mesmo módulo
`calculos/conteineres.py`; não se confia em um resultado antigo de outro lote.
Quantidade manual deve ser inteira e positiva. Falta de capacidade deixa o
cenário parcial, com aviso e sem custo por produto; incompatibilidade do
equipamento impede calcular os itens dependentes de quantidade de contêineres.

Estados diferentes não são substituídos por zero:

| Estado | Comportamento |
| --- | --- |
| `conhecido` | Zero é válido e calculado; outros valores precisam ser não negativos e finitos |
| `desconhecido` | Despesa aplicável pendente, sem valor calculado |
| `nao_aplicavel` | Identificada como não aplicável, sem somar valor artificial |
| `incluido` | Não é cobrada novamente; exige item referenciado no escopo com valor disponível |
| `excluido` | Fora do escopo escolhido pelo usuário |

`participa_total=false` exclui explicitamente o item do escopo, preservando seu
valor/estado na fotografia. Não representa definição automática de responsabilidade
contratual. No item incluído, o valor próprio não é somado nem usado como componente
percentual autônomo: não há preço separado conhecido para essa parcela.
Inclusões circulares e bases percentuais circulares são rejeitadas.

Não é permitido cobrar separadamente um item que permanece declarado incluído
na tarifa original. Para rever essa premissa, desmarque **Manter as inclusões
declaradas na tarifa original** e altere explicitamente o estado da despesa.
A origem dessa alteração fica manual e os arquivos não são modificados.

## Seguro e valor declarado

Prêmio fixo: escolha **Por operação** no item Seguro e informe o prêmio.
Percentual: escolha **Percentual**, informe o parâmetro e selecione os componentes
na lista. O seguro não pode incluir a si próprio; não existem componentes tributários.
Bases podem usar o valor declarado da mercadoria e/ou outras despesas calculadas.
Um componente fora do escopo ou desconhecido gera pendência, não zero.

O valor declarado começa **Não informado**. O usuário pode escolher explicitamente
**Faixa de preço do catálogo** ou informar um valor/faixa manual e moeda. Não há
conversão automática de custo de fabricação/compra em valor declarado. A escolha
e os valores efetivamente usados ficam salvos nas premissas.

Faixas abertas permanecem abertas, inclusive no prêmio e nos totais. Não é usado
ponto médio. `referencia_superior` permanece referência, nunca teto. Na soma,
usam-se máximos fechados e referências disponíveis apenas para construir outra
referência superior; se alguma parcela aberta não tiver referência, a referência
da soma também fica ausente. Multiplicação por zero produz zero conhecido.
A fórmula percentual é didática, não regra universal de contratação de seguro.

## Câmbio e arredondamento

Valores e totais originais de cada item são preservados. Não há soma direta de
moedas distintas. **Consultar / atualizar câmbio desta simulação** chama somente
a integração Frankfurter existente, apenas para os pares necessários. A consulta
pode descobrir novos pares ao resolver bases percentuais; cada par é tentado uma
vez por clique. Navegação e edição não disparam chamadas externas.

Cada cotação usada registra origem, destino, taxa, fonte e data de referência.
Não se presume taxa inversa nem conversão por triangulação. Fator 1 é usado
apenas para a mesma moeda, identificado como identidade local. Moeda manual fora
da lista do provedor/app mantém o valor original, mas a conversão fica pendente.
Falha na atualização remove a taxa anterior daquele par para não ocultar a falha.
Cotações da sessão podem ser reutilizadas, com suas datas apresentadas, sem
prometer disponibilidade ou atualidade comercial.

Regra desta simulação: `Decimal`, **ROUND_HALF_UP**, duas casas decimais por
**total de despesa na moeda original**, novamente por conversão, e por valor
unitário do lote. Não se arredonda a tarifa unitária antes de multiplicá-la.
As linhas já arredondadas são somadas; a base percentual usa esses valores na
origem e a conversão sem arredondamento intermediário adicional. A regra de duas
casas é uniforme nesta etapa didática, inclusive em moedas que possam ter outra
prática comercial. Os cálculos financeiros antigos não foram alterados.

## Totais, escopo e histórico

O resumo mostra frete marítimo, despesas por categoria/moeda, totais conhecidos,
valor conhecido por produto e estado. `total_consolidado` só está disponível
quando não existem pendências e a capacidade atende ao lote.

Se uma despesa aplicável não foi preenchida, o resultado fica parcial e os valores
conhecidos podem ser mostrados como subtotal **parcial**, nunca total completo.
Se faltar conversão de algum valor conhecido, o total conhecido consolidado fica
indisponível; exibem-se os subtotais originais por moeda. Sem nenhum valor conhecido
em cenário pendente, não se apresenta um zero artificial. Escopo vazio ou itens
explicitamente não aplicáveis/excluídos podem resultar em zero, com suas escolhas
preservadas. Valor por produto divide o total conhecido pela quantidade do lote e
fica indisponível se a capacidade não atender à carga.

As abas **Origem**, **Frete marítimo**, **Seguro**, **Destino** e **Extras** organizam
a edição. Adicione/remova extras pelo nome. **Restaurar valores originais da rota**
recarrega os modelos e remove edições/extras. Alterar portos ou equipamento também
reinicia os itens com os valores da combinação correta: não leva uma tarifa
editada de um porto para outro. Produto, lote e moeda preservam despesas úteis,
mas recalculam todos os resultados. O catálogo e os arquivos de tarifa são somente leitura.

**Reaproveitar seleção do simulador** copia mercadoria, lote, rota, equipamento e
moeda quando disponíveis. Também é possível copiar os dados da calculadora de
contêineres. A capacidade sempre é recalculada, mantendo validação centralizada.

**Levar cenário ao simulador para salvar** transfere as seleções para o simulador.
Mercadorias e logística são mostradas separadamente; não é apresentada uma soma
como custo completo ao cliente. A assinatura de compatibilidade inclui produto,
variante completa, lote, portos, equipamento e moeda. Cenário incompatível não é
exibido junto a novas entradas. Mudanças de tarifa/despesas atualizam a fotografia;
entrada inválida remove o resultado ativo, evitando reaproveitamento de custo antigo.

Ao usar **Salvar simulação** no simulador, a chave opcional `logistica` inclui
entradas, tarifa original e premissas modificadas, despesas, bases, cotações,
capacidade e resultado. Os valores monetários Decimal são serializados como
strings decimais para preservar centavos. O histórico não é recalculado ao ler,
e tarifas futuras não modificam operações salvas. Registros antigos sem essa
chave continuam legíveis, sem migração ou alteração retroativa.

## Verificações e limites

```powershell
python -B -m unittest discover -s tests -v
python -m streamlit run interface/app.py
```

Os testes cobrem cobrança por operação/contêiner/produto, seguro fixo/percentual,
inclusão, falta de tarifa, zero/desconhecido, capacidade, moeda e falta de cotação,
faixas abertas, arredondamento, restauração/extra/transferência e histórico legado.
As taxas desses testes são explicitamente simuladas; eles não dependem de rede.

Limites: valores didáticos não são orçamento real; coleta/entrega dependem de
locais e condições informadas. Não há impostos, Incoterms completos, escolha de
responsabilidades, API comercial de frete, prazos novos ou preço sugerido. A
calculadora de capacidade mantém suas limitações de grade e não certifica estufagem.

As capturas de entrada e resumo logístico em desktop/celular estão em `docs/capturas/fretes-*.png`. A conferência no Chrome não substitui uma auditoria em todos os navegadores.
