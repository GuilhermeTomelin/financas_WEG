# Conversão monetária unificada

## O que mudou

A integração Frankfurter v2 foi preservada. A aritmética antes separada entre
`calculos/operacoes.py` e `calculos/fretes.py` agora usa `calculos/monetario.py`.
A organização e validação das taxas ficam em `calculos/cambio.py`; a consulta
externa e atualização explícita do conjunto ficam em `consumo/cambio.py`.
`calculos/consolidacao.py` produz uma fotografia em BRL e na moeda escolhida.
Os cálculos não importam Streamlit. `interface/conversao.py` apresenta o mesmo
resultado no simulador, nos fretes e no histórico, sem refazer consultas.

## API e direção

A [documentação oficial Frankfurter v2](https://frankfurter.dev/) foi conferida
em 05/11/2026. Mantido o endpoint `https://api.frankfurter.dev/v2/rate/{origem}/{destino}`.
O parâmetro opcional `date=AAAA-MM-DD` é usado para manter o lote na mesma data.
A resposta contém `base`, `quote`, `rate` e `date`; direção, taxa e data são validadas.
O JSON é lido com valores decimais para não passar por float antes da validação.

Contrato: **1 unidade da moeda de origem = taxa × unidades da moeda de destino**.
Uma taxa USD → BRL de 5 converte USD 10 em BRL 50. Ela não converte BRL 10 em USD 50.
Os campos registrados são `origem`, `destino`, `cotacao`, `data_referencia`,
`consultado_em` (ISO com fuso UTC), `provedor`, `fonte` e `metodo`.

- `direta`: taxa consultada na direção indicada.
- `inversa`: 1 / taxa do par oposto, com precisão decimal de 50 dígitos na
  inversão; guarda o registro original em `componentes`, com mesma data/fonte.
- `identidade`: mesma moeda, taxa 1 local, sem consulta externa.
- `manual`: comparação explicitamente informada pelo usuário. Não substitui
  automaticamente o conjunto de referências. Consulta/data podem estar ausentes
  porque não se trata de observação do provedor.

**Não há conversão cruzada ou triangulação nesta etapa.** USD → BRL e USD → EUR
não bastam para inferir BRL → EUR; esse par é consultado diretamente ou resolvido
por sua inversa explícita. Não se inventa taxa 1 para cobrir falha ou moeda diferente.
Taxa 1 entre moedas distintas só pode ser um valor fornecido/consultado com origem
identificada, nunca um substituto automático.

A Frankfurter usa referências agregadas por padrão; não foi adicionado outro
provedor nem atribuição a um banco específico. São referências, não ofertas
executáveis de banco/corretora. A data pode ser a última disponível, não a data
de hoje. Sem spread, tarifa bancária ou tributo automático novo.

## Cobertura, cache e coerência

A [lista de moedas da API](https://api.frankfurter.dev/v2/currencies) foi conferida;
a aplicação mantém sua cobertura explícita existente: **BRL, USD, EUR, MXN, CLP,
ZAR**. A API pode oferecer outras moedas, mas isso não expande automaticamente o
suporte do painel. O cadastro de países/portos não presume suporte cambial.
Moeda manual não suportada preserva o valor original e deixa conversão pendente.

A sessão compartilha `cotacoes_sessao` entre produtos e logística. A chave de
cache registra provedor, par e data de referência. Recalcular entradas ou navegar
usa as referências armazenadas, identificadas na seção expansível; não realiza
HTTP por item, card ou renderização. O cache é por sessão, sem TTL comercial
prometido ou serviço novo. Os caches anteriores de frete e da cotação do simulador são aceitos uma única vez como migração local, preservando metadados ausentes. Um conjunto vazio após falha não é repovoado com essas taxas antigas.

Um clique em **Calcular conversão** ou **Consultar / atualizar câmbio desta
simulação** inicia um conjunto novo, sem misturar taxas antigas em caso de falha.
O primeiro par ancora a data; os seguintes usam o parâmetro `date` com essa data.
Inversas disponíveis evitam consulta redundante. Pares descobertos por bases
percentuais são resolvidos no mesmo lote, uma tentativa por par/direção.
Se o provedor devolver outra data, essa taxa não entra no conjunto e o resultado
fica parcial. Conjuntos fornecidos com datas diferentes não são usados para
converter moedas distintas. A identidade permanece disponível.

Timeout, HTTP inválido, resposta malformada, direção divergente, taxa não positiva,
NaN/infinito e data inválida geram erros/pendências. Não há fallback fictício ou
reuso silencioso de taxa removida numa atualização malsucedida. Taxa legada sem
data não é usada para nova conversão automática. Metadados antigos ausentes são
identificados, não preenchidos com uma consulta inventada.

## Bases monetárias e consolidação

A base comercial do simulador permanece o **preço da variante do catálogo**.
Custo de fabricação/compra não é acrescentado como outra despesa. O valor declarado
do seguro continua dependendo da escolha explícita do usuário; não é substituído
silenciosamente pelo custo de fabricação ou pela base comercial.

Frete e despesas continuam sendo calculados primeiro em sua moeda/base original:
por operação, contêiner, produto ou percentual. A consolidação converte os **totais**
desses itens, sem multiplicar de novo pela quantidade. Inclusões, itens não
aplicáveis e exclusões não são cobrados novamente. Original, parâmetros de cobrança,
moeda, categoria, estado e natureza permanecem na fotografia.

Seguro percentual converte os componentes explicitamente escolhidos para a moeda
do seguro com o **mesmo conjunto**, antes de aplicar o percentual. Seu próprio
prêmio não compõe a base. O total original do prêmio então é convertido para BRL
e para a moeda de apresentação, tal como as outras despesas.

A apresentação separa mercadorias, frete marítimo, seguro e demais despesas,
e rotula a soma como **Subtotal de mercadorias + logística**, sem chamar de custo
completo ao cliente. Quando a apresentação é BRL, a visão e a tabela possuem apenas
uma coluna/destino BRL. Valores zero são exibidos como zero; ausência de dados,
inclusões e não aplicáveis não são convertidos em zeros artificiais.

## Faixas e arredondamento

Mínimos, máximos desconhecidos e `referencia_superior` são preservados. Taxas
positivas multiplicam os limites conhecidos. Não há ponto médio, e referência
superior não vira teto. A soma só conserva referência se todas as parcelas abertas
tiverem informação suficiente, conforme a regra já usada nas despesas.

A regra central é **Decimal + ROUND_HALF_UP**. Configuração de exibição/arredondamento
em `CASAS_MOEDAS`: CLP sem casas; BRL, USD, EUR, MXN e ZAR com duas. Valores originais
e taxas mantêm precisão na fotografia. Totais de despesas são arredondados na
moeda original após aplicar a cobrança; cada conversão de item é arredondada para
a moeda de destino; **o total soma exatamente os itens convertidos exibidos**.
Não se converte o total agregado com outra taxa nem se multiplica um total novamente.
A adaptação substitui a antiga regra uniforme de duas casas no cálculo logístico.
Registros históricos preservam sua regra e valores já salvos.

`converter_faixa(subtotal, taxa)` permanece como adaptador legado sem moeda:
mantém saída numérica sem novo arredondamento obrigatório. Com moeda explícita,
aplica a regra central. As telas atuais utilizam a consolidação com moeda definida.
`calcular_estimativa` também delega sua conversão ao mesmo adaptador. O subtotal por faixa calcula a multiplicação em Decimal e mantém os tipos numéricos legados, evitando artefatos como 1,005 × 3 virar 3,014999... antes de compor a base de seguro.

Cada destino possui estado e pendências próprios. Falta de valor ou taxa mantém
originais/subtotais conhecidos, mas deixa o subtotal completo indisponível. A soma
conhecida é identificada como **parcial**. Se a logística não está configurada,
não se afirma que mercadoria sozinha é mercadoria mais logística completa. Grupo
com despesa desconhecida é indisponível, não zero. Capacidade insuficiente e demais
pendências logísticas também impedem declarar o escopo completo.

## Estado e histórico

Produto, variante, lote, rota, equipamento e moeda identificam a simulação.
Mudanças recalculam resultados com as entradas atuais; moeda nova pode reutilizar
despesas do mesmo contexto físico e referências datadas compatíveis. A comparação
manual fica separada do conjunto automático e é registrada como informada pelo usuário.

Salvar no simulador inclui `consolidacao`: itens originais e convertidos,
conjunto completo de taxas, datas, métodos, componentes de inversão, política de
arredondamento e estado por moeda. Decimal é serializado como string, sem perder
centavos. Atualizar taxas gera nova fotografia/identificação; não reescreve um
registro anterior ao salvar novamente.

O histórico lê a fotografia gravada. **Não consulta nem recalcula taxas atuais.**
Registros antigos continuam legíveis com os valores salvos e aviso de metadados
não registrados; eles não são completados automaticamente com dados atuais.

## Exemplo reproduzível e verificações

Cenário controlado de teste, não cotação de mercado:

| Componente | Original | Em BRL | Em USD |
| --- | ---: | ---: | ---: |
| Mercadoria | BRL 100 | 100 | 20 |
| Frete de um contêiner | USD 10 | 50 | 10 |
| Outra despesa por operação | BRL 20 | 20 | 4 |
| Subtotal mercadorias + logística | — | **170** | **34** |

Taxa simulada: **1 USD = 5 BRL**; inversa **1 BRL = 0,2 USD**. Seguro não faz parte
do escopo deste exemplo. O cenário é verificado por
`test_consolidacao_exemplo_reconciliavel_brl_usd` em `tests/test_cambio_unificado.py`.

```powershell
python -B -m unittest discover -s tests -p test_cambio_unificado.py -v
python -B -m unittest discover -s tests -q
python -m streamlit run interface/app.py
```

Os testes não dependem de rede: usam respostas controladas para direta/inversa,
identidade, datas, erros, cobertura, faixas, reconciliação, seguro de base mista,
cache compartilhado, comparação manual e preservação histórica. A conferência
visual local não substitui uma matriz de navegadores ou revisão operacional.
