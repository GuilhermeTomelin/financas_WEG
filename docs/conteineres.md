# Calculadora de contêineres

A página **Contêineres** está operacional para estimativas didáticas de um lote
de uma única variante, em unidades de embarque retangulares iguais. Não calcula
frete, impostos ou preço e não altera o catálogo ou simulações financeiras salvas.

## Equipamentos e fontes

As especificações ficam em `dados/conteineres.json`, em cm e kg. Foram consultadas
em **05/11/2026** nas tabelas de cada exemplo de equipamento da frota Hapag-Lloyd:

| Equipamento | Internas C × L × A (cm) | Porta L × A (cm) | Tara (kg) | Bruto máximo (kg) | Carga útil (kg) |
| --- | --- | --- | --- | --- | --- |
| [Dry 20 pés](https://www.hapag-lloyd.com/en/services-information/cargo-fleet/container/20-standard.html) | 590 × 235,2 × 239,5 | 234 × 229,2 | 2.350 | 30.480 | 28.130 |
| [Dry 40 pés](https://www.hapag-lloyd.com/en/services-information/cargo-fleet/container/40-standard.html) | 1.203,2 × 235,2 × 239,5 | 234 × 229,2 | 3.750 | 32.500 | 28.750 |
| [Dry 40 pés High Cube](https://www.hapag-lloyd.com/en/services-information/cargo-fleet/container/40-standard-high-cube.html) | 1.203,2 × 235 × 270 | 234 × 259,7 | 3.900 | 32.500 | 28.600 |

Os campos são transcritos das tabelas **Inside Dimension**, **Door Opening** e
**Weight**, convertendo mm para cm. No High Cube foi usada a largura de **2.350 mm
da tabela**, mesmo havendo indicação de 2.352 mm na ilustração da página.
Os valores são referências publicadas, não um equipamento reservado. A própria
transportadora informa variação conforme fabricante/equipamento. Fonte, URL,
data de consulta, referência e observação acompanham cada registro.

Tara é massa do contêiner vazio. Carga útil é massa admissível da carga;
peso bruto máximo inclui contêiner e carga. A validação exige tara + carga útil
menor ou igual ao bruto máximo. A capacidade por peso usa **carga útil diretamente**:
a tara não é descontada de novo. O volume é calculado pelo produto das dimensões
internas, podendo diferir do volume arredondado na página da transportadora.

## Carga e dados essenciais

A calculadora usa o catálogo já carregado pela camada de dados. Quantidade de
produtos e produtos por embalagem são inteiros positivos. Dimensões externas
e peso bruto da unidade completa devem ser positivos e finitos. As unidades
aceitas nesta etapa são caixas, engradados e paletes completos, modelados como
paralelepípedos externos. Outras embalagens exigem confirmação/modelagem futura.
Dimensões do produto sem embalagem não substituem as dimensões de embarque.

`nivel_calculo` deve ser `unidade_embarque`. `usa_palete` e `palete_incluido`
precisam confirmar que o palete, quando presente, já está incluído na massa e
no envelope externo. Nada é somado outra vez. Peso líquido, quando informado,
confere a coerência da massa bruta. Custo de origem ausente não bloqueia logística.
A validação geral de `consumo/logistica.py` também é executada e devolvida no
resultado como diagnóstico do catálogo, sem transformar pendências de preço ou
custo em erro da calculadora. Regras de cálculo ficam em `calculos/conteineres.py`.

Os dados físicos atuais das 20 variantes continuam **simulados pelo projeto**;
não são especificações WEG. Não há substituição manual de características nesta
versão; a interface informa o que falta quando um dado essencial está ausente.

## Fórmulas e orientação

Para quantidade de produtos Q e produtos por unidade P:

- Unidades de embarque U = teto(Q / P).
- Volume externo unitário V = C × L × A / 1.000.000, com dimensões em cm e V em m³.
- Volume total = U × V. Peso bruto total = U × peso bruto unitário.
- Se Q não for múltiplo de P, a embalagem parcial mantém **peso bruto e dimensões
  completos**, conservadoramente. Não se aplica proporção ao peso bruto.

Orientações são expressas pela lista `orientacoes_permitidas` do empilhamento:

- `vertical`: altura original como altura de transporte, comprimento/largura
  podem trocar de lugar por giro no plano horizontal.
- `invertida`: mesmo eixo vertical da altura, topo para baixo, somente se
  explicitamente autorizado; gera as mesmas dimensões da posição vertical.
- `lateral`: comprimento ou largura original passa a ser altura, com duas
  possibilidades de giro horizontal para cada caso, totalizando quatro opções.

Não há combinação de orientações na mesma grade. Lista ausente ou inválida
bloqueia o cálculo. Restrições textuais conhecidas de transporte em pé (expressões
“não tombar”, “na vertical” e “em pé”) contradizendo lateral/invertida bloqueiam
o cálculo. Esse reconhecimento não interpreta linguagem natural em geral;
as permissões estruturadas devem ser conferidas junto com as restrições reais.

Para cada orientação permitida, a grade usa:

- nx = piso(comprimento interno / comprimento orientado).
- ny = piso(largura interna / largura orientada).
- nz_altura = piso(altura interna / altura orientada).
- A unidade precisa passar pela porta na mesma posição: largura orientada ≤
  largura da porta e altura orientada ≤ altura da porta. Não se simulam inclinação
  ou manobras para atravessar a porta; unidades, não pilhas pré-montadas, são avaliadas.
- Se empilhamento é proibido, usa uma camada. Se permissão, máximo de camadas
  ou limite de carga sobreposta forem desconhecidos, usa somente piso com aviso.
- Com empilhamento permitido e limites conhecidos, nz_limite = mínimo(máximo
  de camadas, 1 + piso(carga suportada sobre a embalagem / peso bruto unitário)).
- nz = mínimo(nz_altura, nz_limite). Capacidade geométrica G = nx × ny × nz.

A camada apoiada no piso conta como 1. Carga sobreposta não inclui o peso da
própria embalagem inferior. O limite suportado pode reduzir as camadas declaradas;
a ausência de limite não autoriza carga superior. Informações explicitamente
contraditórias são rejeitadas. Os limites cadastrados são aplicados a cada
orientação autorizada; não há modelo de resistência por face.

As divisões geométricas usam `Decimal` a partir da representação decimal dos
valores, evitando operações binárias intermediárias que excluiriam encaixes
exatos como 0,3 / 0,1. Arredondamento é aplicado somente na exibição.

## Peso, escolha e indicadores

Capacidade por peso W = piso(carga útil / peso bruto de uma unidade completa).
Capacidade final F = mínimo(G, W). Escolhe-se a grade de maior G entre as
alternativas elegíveis; W é igual para todas. No empate, prefere-se menos camadas
e então a ordem determinística vertical, invertida, lateral e respectivos giros.

Contêineres necessários N = teto(U / F), para o **tipo selecionado**. Se nenhuma
grade passa pelo interior/porta ou uma unidade excede a carga útil, o resultado
é incompatível, F = 0 e N = null, sem quantidade finita fictícia.

O resultado indica peso e/ou geometria quando empatam no menor limite. Quando
a geometria é determinante, informa também empilhamento se reduzir as camadas;
orientação se uma posição não autorizada permitiria grade maior; porta se uma
posição permitida descartada pela abertura permitiria grade maior. Essas
comparações são diagnósticas, não autorizam as posições descartadas nem alteram
a grade escolhida.

No modo manual, M é inteiro positivo. Alocam-se A = mínimo(U, M × F) unidades,
com excedente U − A. Os percentuais agregados usam **somente A**, não toda a demanda:

- Ocupação volumétrica = A × V / (M × volume interno) × 100.
- Utilização de carga útil = A × peso unitário / (M × carga útil) × 100.
- Posições utilizadas = A / (M × F) × 100.
- Volume restante = M × volume interno − A × V.
- Carga útil restante = M × carga útil − A × peso unitário.

No modo automático, M = N. Volume restante pode ser fragmentado e não representar
espaço utilizável por outra embalagem. Os indicadores não equivalem entre si
nem provam distribuição segura de peso.

## Distribuição e interface

Os contêineres são numerados sequencialmente. Primeiro são preenchidos até F,
depois vem o contêiner parcialmente ocupado; eventuais contêineres adicionais
ficam vazios. Dentro de cada grade, a quantidade pode ser distribuída em colunas
apoiadas, evitando unidades superiores sem apoio. Não são produzidas coordenadas
tridimensionais, animação de carregamento ou avaliação da sequência de manobras.

O resultado guarda até três faixas de contêineres com a mesma carga: completos,
parcial e vazios. O campo `quantidade_conteineres` é a repetição da faixa; todos
os pesos, volumes, posições e saldos na linha são **por contêiner**. Para totais,
multiplicar pela repetição. Na tela, até 200 contêineres são listados individualmente;
em lotes maiores, faixas idênticas são agrupadas, mantendo o último parcialmente
ocupado explícito. Isso evita criar listas enormes ou esconder o último em médias.

A comparação dos três equipamentos usa as mesmas entradas e premissas. No modo
manual, todos usam a quantidade M informada e mostram se atendem ao lote. Não há
recomendação de menor preço, mistura de tipos ou promessa de mínimo global.

Para conferir, execute `python -m streamlit run interface/app.py` e abra
**Operações → Contêineres**. Escolha produto, variante, quantidade, equipamento
e modo. Se já usou o simulador, o botão de reaproveitar copia sua seleção para a
calculadora sem alterar o simulador. Entradas são preservadas ao navegar.
Resultados são recalculados a cada mudança; nenhum resultado anterior é reutilizado.

## Verificação e limites

```powershell
python -B -m unittest discover -s tests -v
```

Os testes cobrem lote pequeno, embalagem parcial, encaixe decimal exato, peso,
porta/interior, empilhamento, camadas, carga suportada, orientação, palete,
quantidades inválidas, modo manual, totais e distribuição, as 20 variantes nos
três tipos e a navegação/reaproveitamento das entradas. Não há rede nesses testes.

O método usa grade uniforme de unidades iguais. Não resolve arranjo misto,
otimização 3D, folgas de operação, resistência por face, limites do piso/carga
concentrada, centro de gravidade, amarração, ventilação, estabilidade ou restrições
da rota/equipamento efetivo. Não certifica segurança, capacidade operacional
ou plano de estufagem. Dados reais e avaliação operacional continuam necessários.
