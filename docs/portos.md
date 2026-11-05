# Localidades portuárias e rotas

## Fonte e atribuição

Dados: **UNECE / United Nations Economic Commission for Europe, UN/LOCODE 2025-1**,
publicação de produção indicada na [página oficial](https://unlocode.unece.org/publications/).
[ZIP oficial](https://opensource.unicc.org/un/unece/uncefact/vocab-locode/-/jobs/artifacts/2025-1/download?job=package-release).
Obtido em **05/11/2026**. O timestamp UTC exato, SHA-256, filtros e contagens estão
em `dados/portos_unlocode.json`, no objeto `metadados`. São 16.126 localidades de
232 países/territórios após filtros, com 206 localidades brasileiras.

A página da publicação informa **CC BY 4.0** para os padrões UN/CEFACT; manter
esta atribuição, o link da fonte e a indicação das alterações (filtragem,
normalização de código e consolidação de aliases). Consultar também os
[termos gerais do site](https://unlocode.unece.org/terms/), que contêm restrições
genéricas de uso e redistribuição, e a [licença CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
A indicação específica de licença da publicação foi registrada nos metadados;
o projeto não declara endosso da ONU nem altera a responsabilidade pelos dados.
A UNECE não garante exatidão ou adequação operacional das entradas.

## Procedimento de importação

Sem bibliotecas novas, a partir da raiz do projeto:

```powershell
python -B scripts/importar_unlocode.py
```

O comando baixa o ZIP oficial e gera `dados/portos_unlocode.json` em UTF-8.
Não execute a atualização com o painel aberto; reinicie-o depois para limpar
o cache local. Para fornecer um ZIP já obtido:

```powershell
python -B scripts/importar_unlocode.py --arquivo C:/Downloads/publicacao.zip --versao 2025-1 --obtido-em DATA_HORA_ISO_REAL
```

Substitua `DATA_HORA_ISO_REAL` pela data/hora real da obtenção, com fuso.
Para outra publicação, forneça **também** `--url URL_OFICIAL_CORRESPONDENTE`.
O importador suporta o layout oficial ZIP com três `UNLOCODE CodeListPartN.csv`
e `SubdivisionCodes.csv` em UTF-8. Mudanças de layout exigem revisão explícita.
O ZIP bruto local fica em `dados/fontes/`, ignorado pelo Git; não é necessário
para executar a aplicação ou os testes. A cópia JSON processada deve acompanhar
o projeto. Não há consulta à UNECE durante a navegação.

## Filtros e significado

Critérios conforme [Recommendation 16 e Annex II](https://unlocode.unece.org/recommendation16/):

- Código canônico: duas letras do país ISO 3166-1 e três caracteres da localidade
  (letras ou dígitos de 2 a 9), maiúsculos, sem espaço: `BRSSZ`.
- Primeiro caractere da função igual a `1`, função marítima. Não basta ter
  função multimodal `6` ou transporte interior `8`. A classificação da fonte
  não é uma verificação geográfica ou operacional feita pelo projeto.
- Status aceitos: `AA`, `AC`, `AF`, `AI`, `AM`, `AS`, `RL`. `RL` confirma existência
  e representação do nome, mas não confirma relevância para comércio internacional.
  Excluídos os demais, incluindo `AQ` (funções não verificadas), `RQ` (pendente),
  `XX` (remoção), `QQ`, `RN` e status desconhecidos. Critério conservador do projeto.
- Indicadores `X` (remoção) e `=` (referência) são excluídos. Nomes com acentos,
  subdivisão, status, função, coordenadas e observações são preservados.
- A publicação contém 68 códigos com registros repetidos elegíveis. Aliases com
  mesma função, status e subdivisão são consolidados por data de atualização;
  no empate, prefere-se indicador `#`, depois nome lexical. Os outros nomes
  continuam pesquisáveis. O conflito de função/status em **FIHEL** foi excluído
  conservadoramente e consta dos metadados. Não se criam códigos para corrigir a fonte.

A classificação registra uma **localidade com função portuária**, não um terminal
específico. Não garante contêineres, calado, disponibilidade, serviço regular,
frete, prazo ou cobertura tributária.

## Configuração, moedas e histórico

`dados/navegacao.json` configura nomes traduzidos, moedas herdadas, portos padrão,
favoritos e rotas comerciais. Os países restantes usam o nome da publicação e
moeda local **não configurada**. UN/LOCODE não é fonte de moedas.
Relacionamentos usam ISO e UN/LOCODE; nomes são apenas exibição.

`dados/rotas.json` foi mantido integralmente para compatibilidade. Antes havia
somente Santos e os seis destinos, sem tarifas ou prazos. O mapeamento conferido é
BRSSZ → ITGIT, USLAX, DEHAM, MXZLO, CLSAI e ZADUR. São seleções padrão, não serviços
confirmados. Hamburg é o nome oficial exibido para o antigo rótulo Hamburgo.
O cadastro comercial `rotas` está vazio; quando houver dados reais, cada registro
usará `origem_unlocode` e `destino_unlocode` exatos. Não há expansão automática
por país ou reutilização de frete entre portos diferentes.

A aplicação mantém as seis moedas já suportadas por `consumo/cambio.py`: BRL,
EUR, USD, MXN, CLP, ZAR. O endpoint oficial `/v2/currencies` lista essas moedas;
os cinco pares externos com BRL responderam à verificação real em 05/11/2026.
A verificação está registrada na configuração. BRL/BRL usa fator 1 localmente.
A API suporta outras moedas, mas o aplicativo continua com sua lista explícita.
As associações país/moeda são herdadas do projeto, sem inventar novas associações.
Para país sem configuração, USD é apenas o padrão de **apresentação**, editável;
não é apresentada como moeda local. Moeda local configurada fora da cobertura
gera aviso e permite escolher outra. Falhas de rede mantêm o subtotal em BRL.
[Documentação Frankfurter](https://frankfurter.dev/) e
[moedas do provedor](https://api.frankfurter.dev/v2/currencies).

Os controles permitem pesquisar nomes sem acentos ou códigos, mostram subdivisão
e código e destacam favoritos. O botão de favorito altera apenas a sessão atual;
para definir favoritos iniciais persistentes, edite `favoritos` na configuração.
Brasil continua sendo a única origem habilitada; outros países já estão separados
no cadastro para uma etapa futura. Santos inicia selecionado.
Alterar país limpa porto incompatível, e alterar produto, variante, quantidade,
porto ou moeda invalida câmbio, fotografia e identificação de resultado anteriores.
A cotação só é aplicada novamente após clicar em **Calcular conversão**.

Sem dado comercial exato, a tela informa **Frete indisponível para esta rota**;
não substitui por zero, não promete serviço e mostra somente subtotal da mercadoria.
Simulações antigas continuam sendo lidas sem migração. Novas simulações incluem
ISO, UN/LOCODE e os nomes na fotografia salva, mantendo as chaves anteriores.
Nenhum registro histórico existente é atualizado retroativamente.

## Verificação

```powershell
python -B -m unittest discover -s tests -v
```

Os testes usam a cópia local, arquivos temporários para histórico e câmbio
simulado explicitamente nos testes da tela, sem rede. A consulta real de pares
foi uma verificação separada; os testes não garantem disponibilidade futura.
