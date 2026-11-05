[README (2).md](https://github.com/user-attachments/files/34200500/README.2.md)
# Finanças WEG

![Python](https://img.shields.io/badge/Python-243447) ![Streamlit](https://img.shields.io/badge/Streamlit-18745E)

Quanto custariam cinco motores brasileiros na moeda de um cliente no México? O **Finanças WEG** ajuda a responder essa pergunta. Você escolhe um produto, a quantidade e o país. O painel mostra a rota a partir do porto de Santos, calcula a faixa de preço em reais e consulta o câmbio para apresentar o mesmo pedido na moeda do destino.

Por exemplo, **5 motores W22 de 2 CV** têm um subtotal simulado de **R$ 9.000 a R$ 13.000**. Ao selecionar o México, a rota exibida é **Santos → Manzanillo**. Um clique em **Calcular conversão** mostra quanto essa faixa representa em pesos mexicanos, junto com a taxa utilizada e sua data de referência.

> **Como ler o resultado**  
> Os preços do catálogo são estimativas educacionais. O câmbio vem da API [Frankfurter](https://frankfurter.dev/). O subtotal cobre a mercadoria. Frete, seguro, impostos e despesas portuárias ficam fora da conta.

## Como rodar no seu PC

Você vai precisar de **Python** instalado. Os comandos abaixo usam o **PowerShell do Windows** e podem ser executados no terminal do VS Code.

### 1. Abra a pasta do projeto

Se você já baixou o ZIP, extraia os arquivos e abra no VS Code a pasta que contém `requirements.txt`. Abra **Terminal → Novo Terminal** e siga para a etapa 2.

Se preferir baixar com Git, execute:

```powershell
git clone https://github.com/GuilhermeTomelin/financas_WEG.git
cd financas_WEG
```

### 2. Prepare o ambiente

Na pasta do projeto, crie um ambiente virtual e instale as dependências:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Inicie o painel

```powershell
.\.venv\Scripts\python.exe -m streamlit run interface/app.py
```

O painel abrirá no navegador. Se a aba não abrir automaticamente, copie o endereço indicado como **Local URL** no terminal. Mantenha o terminal aberto enquanto usa o simulador. Para encerrar, pressione **Ctrl+C**. Nas próximas vezes, basta abrir a pasta do projeto e repetir o comando da etapa 3.

**No Linux ou macOS**, a partir da pasta do projeto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run interface/app.py
```

## Faça a primeira simulação

1. Escolha **Motor W22**, selecione a variante **2 CV** e informe **5** unidades.
2. Selecione **México** e confira o subtotal em reais.
3. Com conexão à internet, clique em **Calcular conversão**. Confira o resultado em **MXN** e a data do câmbio.

---

Projeto educacional independente, sem vínculo oficial com a WEG.


## Dados de custo e logística por variante

As 20 variantes de `dados/produtos_simulados.json` possuem dados adicionais.
Os campos antigos de preço (`minimo`, `maximo`, `referencia_superior`) continuam
com o mesmo significado: máximo null é limite aberto; referência não é teto.
O catálogo legado `dados/produtos.json` e os cálculos existentes foram preservados.

- `custo_origem`: `tipo` (`fabricacao` ou `compra`), `minimo`, `maximo`,
  `moeda`, `natureza` (`real`, `simulado`, `nao_informado`), `fonte` e
  `data_referencia` (AAAA-MM-DD ou null). Valores são por produto, na moeda
  indicada. Mínimo igual ao máximo representa valor único; máximo null com
  mínimo informado é faixa aberta. O custo ficou **não informado** em todas
  as variantes: não há base para deduzi-lo do preço de venda.
- `dados_fisicos`: tem sua própria `natureza`, `fonte` e `data_referencia`.
  Todos os dados físicos preenchidos são **simulados pelo projeto**, sem
  fontes oficiais, certificações ou datas de consulta inventadas. Cada variante
  representa uma hipótese ilustrativa, inclusive quando o nome abrange vários modelos.
- `produto.peso_liquido_kg`: massa de um produto sem embalagem, em kg.
  `produto.dimensoes` contém `comprimento_cm`, `largura_cm`, `altura_cm`.
  `tipo_dimensoes=caixa_envolvente_aproximada` indica o envelope aproximado de
  um produto irregular, não uma medição oficial.
- `unidade_embarque`: `tipo` (`caixa`, `engradado`, `palete`, `outra`),
  `quantidade_produtos` (inteiro positivo), `dimensoes_externas` (mesmos eixos,
  em cm) e `peso_bruto_kg` (massa **da unidade completa**, incluindo todos os
  produtos, embalagem, proteções e palete quando presente).
  `usa_palete` indica seu uso; `palete_incluido` confirma que massa e dimensões
  externas já o incluem. Sem palete, ambos são false. O engradado da variante
  maior W22 já inclui o palete: não somar outro. `nivel_calculo=unidade_embarque`
  define o único nível para a futura acomodação; não há caixas aninhadas ou
  paletização adicional nesta etapa.
- `empilhamento.permitido`: true permite, false proíbe, null é desconhecido.
  `maximo_camadas` é inteiro positivo e conta o piso (1 = somente piso).
  `orientacoes_permitidas` usa `vertical`, `lateral`, `invertida`; os exemplos
  permitem apenas vertical (altura indicada para cima). `restricoes` descreve
  cuidados. `carga_sobreposta_maxima_kg` é a massa máxima apoiada **sobre** a
  unidade inferior, excluindo sua própria massa. Zero significa nenhuma carga;
  null significa limite desconhecido. Não tratar desconhecido como permissão.

`consumo/logistica.py::validar_variante` retorna mensagens legíveis de
incompletude ou inconsistência sem modificar dados ou bloquear os cálculos
antigos. A interface chama essa validação no expansor **Custo de origem e dados
logísticos da variante**. Pesos/dimensões devem ser finitos e positivos;
quantidades/camadas, inteiros positivos; custos e carga sobreposta podem ser zero.
A massa bruta deve cobrir a massa líquida de todos os produtos. A validação
confere coerência de faixas de custo, palete, camadas e carga sobreposta.
Fonte de preço não comprova características físicas.

Abra o painel como descrito acima e selecione diferentes variantes para conferir
o expansor, inclusive W22 de 50 CV (palete e empilhamento proibido).
Para executar as verificações locais, sem rede ou dependências novas:

```powershell
python -B -m unittest discover -s tests -v
```

A estrutura prepara uma futura calculadora de contêineres para demonstração.
Ainda não calcula capacidade, arranjo, rotação, carga do piso ou estabilidade;
não verifica se o conteúdo realmente cabe na embalagem. Será necessário definir
contêineres, regras de acomodação, unidades parciais e validar especificações reais
antes de qualquer uso operacional. Custo de origem e datas/fontes reais continuam
pendentes; não há calculadora de contêineres implementada nesta etapa.


## Países e localidades portuárias (etapa 2)

O painel usa uma cópia local da publicação oficial **UNECE UN/LOCODE 2025-1**,
obtida em 05/11/2026: **16.126 localidades elegíveis em 232 países/territórios**,
com **206 opções brasileiras**. Localidade cadastrada não confirma terminal de
contêineres nem serviço comercial.

Nos controles, selecione Brasil e o porto de origem (Santos é o padrão), país e
porto de destino e **Moeda de apresentação**. Pesquise por nome ou UN/LOCODE;
subdivisão e código distinguem nomes semelhantes. Use o botão de favorito para
destacar opções durante a sessão. Os seis destinos antigos continuam disponíveis.
A moeda local só é sugerida quando já está configurada; nos demais países,
escolha uma das moedas suportadas. A base não precisa de internet para consulta;
o câmbio continua dependendo da Frankfurter.

Sem tarifa para a combinação exata, a tela mostra **Frete indisponível para esta
rota**, sem incluir zero ou apresentar um total completo. Alterar a seleção
invalida resultados anteriores. O histórico existente é preservado.

Consulte [fonte, filtros, atribuição, limitações e atualização da base](docs/portos.md).
Para atualizar a mesma publicação: `python -B scripts/importar_unlocode.py`.


## Novo painel e navegação

A aplicação abre no **Dashboard**, com métricas reais do catálogo, da base de
portos e do histórico local. A sidebar agrupa **Visão geral**, **Operações**,
**Dados e análises** e **Sistema**, com nove páginas. O tema agora é claro,
com sidebar azul-marinho, cards brancos e ações azuis.

Abra **Simulador** para o fluxo existente; as entradas estão em **Mercadoria**
e **Trajeto e moeda**. Consulte o catálogo em **Produtos**, a base UN/LOCODE em
**Fretes e rotas**, e as abas **Histórico** e **Relatórios** na página correspondente.
Impostos e Precificação estão identificados como **Planejado**; Contêineres possui calculadora didática.
Integrações informa o estado conhecido do câmbio e os recursos futuros.
Seleções úteis são preservadas entre páginas; navegar não dispara consulta externa.

Consulte [o guia de navegação, componentes e verificações](docs/navegacao.md)
e as [capturas para revisão](docs/capturas/).


## Calculadora de contêineres

Abra **Operações → Contêineres** para estimar peso, volume, ocupação e quantidade
de Dry 20 pés, Dry 40 pés ou Dry 40 pés High Cube. Selecione uma variante, informe
a quantidade de produtos e escolha entre estimativa automática e avaliação de uma
quantidade de contêineres. É possível reaproveitar a seleção atual do simulador.

A calculadora considera unidades de embarque retangulares iguais, grade uniforme,
orientações permitidas, abertura da porta, empilhamento e carga útil. Embalagem
parcial mantém as dimensões e o peso bruto completos. A distribuição mostra o
último contêiner parcialmente ocupado e separa demanda excedente da carga alocada.
Os dados de carga continuam simulados; as especificações dos equipamentos são
exemplos publicados pela Hapag-Lloyd, consultados em 05/11/2026.

Consulte [as fontes, fórmulas, unidades e limitações](docs/conteineres.md).
A estimativa não é otimização 3D nem plano certificado de estufagem e não inclui
frete ou impostos. A documentação da etapa 1 descreve a base histórica; a
calculadora antes planejada agora está disponível com este escopo.


## Frete e despesas logísticas

Abra **Fretes e rotas → Simulação logística**. Há nove tarifas FCL **simuladas**:
Santos (`BRSSZ`) → Gioia Tauro (`ITGIT`), Los Angeles (`USLAX`) e Manzanillo
(`MXZLO`), nos tipos `dry20`, `dry40` e `hc40`. Outros portos/equipamentos ficam
sem tarifa automática e permitem entrada manual. Os valores não são cotações reais.

Edite os itens nas abas **Origem**, **Frete marítimo**, **Seguro**, **Destino** e
**Extras**, escolha estado/base/moeda e informe locais de coleta/entrega quando
houver transporte terrestre. Seguro fixo usa Por operação; percentual exige
componentes e valor declarado escolhidos explicitamente. Inclusões não são
cobradas novamente. É possível restaurar o modelo sem alterar os arquivos.

Consulte câmbio pelo botão específico. Sem taxa ou valor necessário, a tela
mostra pendências e subtotais por moeda, sem somar moedas diferentes. Quantidade
de contêineres é estimada pelo módulo existente ou manual, mantendo verificação
de capacidade. **Levar cenário ao simulador para salvar** permite gravar a cópia
logística no histórico junto à operação financeira. Mercadoria e logística ficam
separadas; impostos ainda não compõem um custo completo ao cliente.

Veja [modelos, fórmulas, seguro, moedas e limitações](docs/fretes.md).
