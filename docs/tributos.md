# Simulação tributária

Entrega de 05/11/2026. **Modo manual funcional e dois exercícios didáticos. Zero cenários tributários legais documentados ativados.** Não há API tributária, precificação ou nova dependência. O cálculo funciona sem rede; somente o botão de câmbio de referência pode consultar a integração Frankfurter existente.

## Como conferir

1. Execute `python -m streamlit run interface/app.py` e abra **Operações → Impostos**.
2. Em **Cenário**, informe produto, variante, quantidade, origem da mercadoria, destino, portos, data e condições. A procedência/embarque permanece Brasil. Origem pode ser outro país: embarcar no Brasil não comprova origem brasileira.
3. Em **Classificação fiscal**, informe sistema, edição, código como texto e fonte. SH/HS exige seis dígitos; NCM, oito. Código nacional do destino exige tamanho declarado. Zeros iniciais permanecem. A checagem de formato não comprova existência do código nem classificação correta; nenhuma classificação é inferida pelo nome do produto ou convertida para o destino.
4. Em **Regras e bases**, adicione/edite/remova tributos. Escolha percentual com componentes explícitos ou valor fixo por operação. Informe moeda, situação, janela de aplicação e fonte/premissa. Se depender de outro tributo, selecione-o como componente. Remover um tributo referenciado exige corrigir as dependências; o sistema não muda fórmulas silenciosamente.
5. Em **Resultado e memória**, confira tributos, bases, fórmula, moedas, taxas, resultados conhecidos e pendências. A falta de classificação revisada não bloqueia hipóteses manuais; o aviso permanece.
6. Opcionalmente configure **Fretes e rotas**, leve a logística ao simulador e use **Reaproveitar operação do simulador** na página fiscal. Produto, lote, portos e equipamento precisam coincidir para reaproveitar despesas. Sem logística compatível, tributos sobre mercadoria podem ser calculados, mas a soma mercadoria + logística + tributos permanece indisponível.
7. Use **Levar cenário tributário ao simulador para salvar**. No simulador, revise o resumo fiscal e salve. Moeda BRL permite conferir o fluxo sem rede; outras moedas precisam de referência disponível. Abra **Histórico e relatórios → Consultar registro completo** para ver a cópia salva.

Para um exercício pré-carregado, selecione **Exemplo didático** e clique em **Carregar explicitamente o cenário**. Os parâmetros só são aplicados quando países, classificação, edição, condições e data coincidem exatamente. O modo **Cenário documentado** informa a indisponibilidade nesta versão.

## Cenários entregues

| Uso | Origem / embarque / destino | Parâmetros matemáticos em BRL | Natureza |
| --- | --- | --- | --- |
| Manual | Origem informada / BR / exterior | Percentuais, fixos e bases informados explicitamente | Simulação manual — regras não validadas |
| `exercicio_dependencias` v1.0 | BR / BR / US | A: 5% da mercadoria; B: 10% de mercadoria + A; fixo: R$ 2,50 por operação | Exemplo didático, sem validade legal |
| `exercicio_aduaneiro` v1.0 | BR / BR / MX | 12% de valor aduaneiro explicitamente informado; outro tributo com alíquota zero | Exemplo didático, sem validade legal |

Nos exercícios, `HS_SH`, edição `2022`, código **`000001`** são identificadores sintéticos: não representam código real ou classificação de produto. O regime `EXERCICIO_SEM_PREFERENCIA` e a condição mercadoria nova são premissas do exercício, sem benefícios comerciais. A janela 01/01/2026–31/12/2026 serve para testar compatibilidade temporal; **não é vigência de lei**. BRL é a moeda dos cálculos didáticos, sem afirmar ser moeda de recolhimento de US/MX. O valor aduaneiro inicial de R$ 100 do segundo exemplo é uma hipótese editável, sem relação automática com catálogo ou legislação.

Nenhum tributo de importação brasileira é aplicado ao fluxo BR → exterior. `importacao_destino` exige jurisdição do destino; `exportacao_origem` refere-se ao país de embarque BR, que continua separado da origem da mercadoria. Importação para o Brasil e embarque em outro país são rejeitados pelo motor e não expostos pela tela.

## Fontes e pendências

Consultadas em **05/11/2026**:

- [Siscomex — SH e NCM](https://www.gov.br/siscomex/pt-br/servicos/aprendendo-a-exportar/1-classificacao-fiscal-da-mercadoria/sh-e-ncm/sh-e-ncm): distinção estrutural entre SH de seis dígitos e NCM de oito.
- [Organização Mundial das Aduanas — FAQ do Sistema Harmonizado](https://www.wcoomd.org/en/faq/harmonized_system_faq): estrutura de seis dígitos, detalhamento nacional e edição HS 2022.

Essas fontes fundamentam somente a distinção dos sistemas de classificação. **Não fundamentam os tributos dos exercícios, suas alíquotas, bases, exceções ou vigências.** As fontes legais dos exercícios são `null`, explicitamente sem consulta legal. Não foram confirmados código real dos produtos, enquadramento nacional do destino, alíquotas oficiais aplicáveis, bases, exceções e vigências para os cenários comerciais do catálogo. Por isso nenhum cenário legal foi ativado.

Para adicionar um cenário documentado, falta registrar classificação confirmada externamente, documentação oficial da jurisdição pertinente à data, fórmula/base/exceções conferidas, condições e premissas explícitas, fonte e data real de consulta, versão e responsável pela conferência. O estado de revisão por especialista é separado. URL e testes de aritmética não validam juridicamente a regra. Acordos e preferências exigem comprovação de origem e demais requisitos; não são inferidos do embarque nem aplicados nesta entrega.

## Arquitetura e regras

- `dados/cenarios_tributarios.json`: esquema v1; cenários e regras v1.0, naturezas, classificação, condições, janela, fontes e premissas. Não é alterado pela interface.
- `consumo/tributos.py`: leitura e verificação da configuração local.
- `calculos/tributos.py`: validação de entradas, compatibilidade exata, grafo de dependências, cálculo e reaproveitamento compatível de cenário ativo. Sem Streamlit, rede ou `eval`.
- `interface/impostos.py`: entradas e editores; `interface/resumo_tributario.py`: mesmo apresentador para página fiscal, simulador e histórico.

Regras registram `id`, `versao`, `jurisdicao`, `escopo`, `tipo_calculo`, `componentes_base`, `aliquota` ou `valor_fixo`, `moeda`, `situacao`, participação, inclusão, início/fim, natureza, fonte/data e revisão. Classificação e condições aplicáveis são herdadas do cenário versionado, salvo junto às regras. Fontes manuais são entradas do usuário, sem promoção automática a documento oficial. Alterar parâmetros de uma regra didática/documentada gera estado `manual`, versão `manual-1` e `substitui_regra` com identificador, versão e natureza anteriores.

O motor só aplica regras compatíveis com jurisdição, período inclusivo e contexto do cenário. Configuração `documentado` exige fonte, data, premissas/exceções, conferência documental registrada e classificação confirmada; regra documentada exige também sua própria fundamentação/fonte/data. Estado `revisao_pendente` não é calculado como regra válida. Os exercícios não recebem selo de validação jurídica.

### Fórmulas e memória

Percentual: `soma(componentes explícitos convertidos para a moeda do tributo) × alíquota / 100`. Valor fixo: montante na moeda informada **por operação**, sem multiplicar novamente por produtos ou contêineres. Dependências `tributo:<id>` usam o valor original já arredondado do tributo anterior. Ordenação da lista não altera o resultado; ciclos e dependências tributárias inexistentes são rejeitados. Componente monetário indisponível gera pendência, sem zero artificial.

Bases possíveis: mercadoria comercial, despesas existentes, tributos anteriores e `valor_aduaneiro`. Valor aduaneiro exige montante, moeda e fonte/premissa próprios; não se presume CIF. Preço comercial não é custo de fabricação e este não é somado ao preço. Fórmulas por dentro, créditos e arredondamentos especiais não implementados ficam `nao_suportado`, sem aproximação genérica ou abatimento automático.

A memória preserva componentes e valores originais, montantes convertidos na base, alíquota/fixo, fórmula explicativa, resultado, moeda, fonte, natureza, revisão e pendências. A fórmula exibida é texto explicativo, nunca código executável.

### Moedas, faixas e precisão

`calculos/monetario.py`, `ConjuntoCotacoes` e a consolidação existente continuam centrais: `Decimal`, `ROUND_HALF_UP` por item/moeda; CLP com zero casas e demais moedas habilitadas com duas. Totais somam as linhas arredondadas. Original, moedas e datas são preservados; não há soma direta entre moedas nem cruzamento cambial implícito. A referência da sessão pode ser reaproveitada; consulta só por ação explícita, em lote de data coerente.

`cambio_base=referencia` usa as referências da simulação. `cambio_base=aduaneiro` usa conjunto separado: taxa explicitamente marcada `aduaneiro`, com fonte e a data requerida, informada pelo usuário. A tela não a valida como taxa legal. Sem a taxa exigida, a base fica pendente mesmo que exista taxa Frankfurter do mesmo par. Conversão de apresentação continua sendo de referência. Moedas iguais usam identidade local sem taxa externa. A tela permite um par aduaneiro por cenário; o motor aceita lista. Pares aduaneiros ausentes não são enviados à Frankfurter.

Faixas lineares crescentes e dependências com alíquotas não negativas propagam mínimo, máximo e referência superior; limite aberto permanece aberto. O percentual conhecido sobre a base comercial só é calculado quando o denominador comercial do lote é **um valor definido positivo**. Com denominador variável/zero/ausente, fica indisponível; não se usa ponto médio nem se apresenta razão de intervalos correlacionados como exata.

### Estados e consolidação

| Estado | Tratamento |
| --- | --- |
| Aplicável e alíquota/valor zero explícito | Resultado numérico zero, separado de isenção |
| Não informado | Pendente, nunca tratado como zero |
| Não aplicável | Sem cobrança no escopo; não inventa alíquota |
| Isento | Só sem cobrança se cenário documentado compatível e fundamentação presentes; declaração manual insuficiente fica pendente |
| Incluído | Referência explícita a `despesa:<id>` ou `tributo:<id>` com cobertura conhecida e no escopo; não somado novamente |
| Fora do escopo | Exclusão explícita mantida na memória |
| Fora da vigência | Sem aplicação; resultado parcial |
| Não suportado / revisão pendente | Sem fórmula improvisada; resultado parcial |

Ausência de regras não significa ausência de imposto. A cobertura de item incluído precisa ser conhecida; se a despesa/tributo que o inclui estiver indisponível ou excluído, gera pendência. Se o montante tributário não está individualizado na despesa que o inclui, não é inventado para uma base de outro tributo.

Por moeda, exibe total tributário conhecido, conhecido por produto, percentual conhecido e denominador, subtotal de mercadorias + logística e subtotal acrescido dos tributos calculados. Este último só aparece quando os dois blocos estão completos no escopo. Conhecidos parciais permanecem identificados; a ausência de conversão ou logística pode impedir total completo. Mesmo completo, o resultado continua manual/didático conforme origem das regras e não representa cobertura tributária completa do país ou custo final garantido ao cliente.

### Estado ativo e histórico

A página fiscal recalcula ao editar origem, destino, produto, classificação, data, condições ou valores; falha de validação remove o resultado ativo. No simulador, uma assinatura considera produto/variante/preços, lote, portos, equipamento e despesas/premissas originais. Mudanças incompatíveis impedem o reaproveitamento do cenário fiscal. Mudar só moeda/taxa de referência reconverte e recalcula pelas mesmas entradas/regras; pares adicionais de tributos participam do atualizador central.

Salvar grava uma cópia serializada do cenário, classificação, regras/versões/fontes, parâmetros comerciais/logísticos, bases, taxas de referência/aduaneiras, resultados e premissas no SQLite já existente. O histórico lê a cópia, sem nova consulta ou recálculo com regras atuais. Registros anteriores sem tributos continuam legíveis, com aviso de informação não registrada; não recebem zero nem preenchimento retroativo.

## Exemplos aritméticos independentes

Com mercadoria R$ 100, frete R$ 10 e seguro R$ 2:

- Subtotal antes dos tributos = R$ 112.
- Tributo manual A = 10% de R$ 100 = R$ 10.
- Tributo manual B = 5% de (mercadoria + frete + A) = 5% de R$ 120 = R$ 6.
- Encargo fixo por operação = R$ 4.
- Tributos conhecidos = R$ 20; por produto, em lote de uma unidade = R$ 20; percentual sobre preço comercial R$ 100 = 20%; subtotal acrescido = **R$ 132**.

O exercício pré-carregado US usa outras hipóteses: A=R$ 5; B=R$ 10,50; fixo=R$ 2,50; tributos=R$ 18; subtotal acrescido=R$ 130, com a mesma logística acima. No exercício MX, valor aduaneiro hipotético R$ 100 × 12% = R$ 12 e o tributo de alíquota zero resulta R$ 0. Esses números não descrevem leis de US/MX.

Com mercadoria R$ 100,00–limite aberto e referência superior R$ 200, um percentual manual de 10% gera R$ 10,00–limite aberto e referência R$ 20. Com base aduaneira hipotética USD 100 e taxa aduaneira informada de 4 BRL/USD, 10% resulta BRL 40, independentemente de uma referência Frankfurter hipotética de 5 BRL/USD. Referência Frankfurter sozinha não supre a taxa aduaneira requerida.

## Verificação

```powershell
python -B -m unittest discover -s tests -p '*tributos.py' -v
python -B -m unittest discover -s tests -v
```

Os testes verificam valores independentes, dependências fora de ordem, ciclos, vigência inclusiva e exterior, incompatibilidades, origem separada de embarque, código com zeros, natureza manual/didática, desconhecido/zero/isenção, moedas/taxas ausentes, câmbio aduaneiro separado, faixas abertas, arredondamento, inclusões, histórico/legado e adição/edição/remoção/transferência na interface. Fórmulas testadas **não comprovam validade jurídica**.

Capturas de cenário e resultado fiscal em `docs/capturas/impostos-*.png`; relatório `docs/capturas/verificacao.json`, viewports 1440×1050 e 390×844. Revisão local Chrome, sem matriz completa de navegadores ou auditoria de acessibilidade.
