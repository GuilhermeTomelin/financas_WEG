# Interface e navegação

O ponto de entrada continua `interface/app.py`, com Streamlit e navegação nativa
`st.navigation` / `st.Page`. Validado com Streamlit 1.65.0 instalado; o projeto
mantém suas dependências existentes. Não foi feita migração de frontend.

## Menu lateral

| Grupo | Página | Estado e conteúdo |
| --- | --- | --- |
| Visão geral | Dashboard | Métricas calculadas a partir das bases locais, atalho para simular, histórico recente e gráfico somente quando houver registros |
| Operações | Simulador | Catálogo, portos, câmbio e salvamento; custos por comprador/vendedor, atribuição manual e inclusões, com resumo/composição/premissas |
| Operações | Contêineres | Calculadora operacional: grade uniforme, peso, volume, ocupação, quantidade automática/manual e comparação dos três equipamentos |
| Operações | Fretes e rotas | Simulação editável de frete/despesas e aba de consulta UN/LOCODE |
| Operações | Impostos | Cenário, classificação, regras editáveis e memória: modo manual e dois exercícios didáticos; sem cenário legal ativado |
| Operações | Precificação | Planejado: análise futura de custo, margem e preço |
| Dados e análises | Produtos | Busca e filtro de catálogo, abas Comercial e Logística, sem editor |
| Dados e análises | Histórico e relatórios | Filtros compartilhados e abas Histórico e Relatórios, sem inventar atividade |
| Sistema | Integrações | Frankfurter implementada, estado conforme sessão; ThingSpeak planejado; API de outro projeto com escopo futuro a definir |

Os números do dashboard não medem cobertura de frete ou tributação. A contagem
de países com portos para destino exclui o Brasil, única origem habilitada. Não
há indicadores de lucro, notificações ou usuários fictícios. Quando o histórico
não pode ser lido, o total é indisponível, nunca zero artificial.

O simulador possui abas internas **Mercadoria** e **Trajeto e moeda** apenas para
organizar entradas. Os resultados permanecem no mesmo fluxo; preço é separado
de custo de origem e subtotal não é custo completo ao cliente. O botão de salvar
continua dependente de uma conversão válida, inclusive conversão local BRL/BRL.
Não foi adicionado exportador ou CRUD; não existiam no frontend anterior.

## Estado e consultas externas

As chaves estáveis dos widgets do simulador foram preservadas. Seleções do
catálogo, da consulta de portos e dos filtros de histórico também são mantidas
ao navegar. Trocar produto, variante, quantidade, porto ou moeda continua
invalidando resultados pelo módulo `consumo/portos.py`. A navegação simples
não consulta câmbio. A tela de integrações apresenta a última referência válida
da sessão, sem declarar conexão ativa ou testar a API automaticamente.
O dashboard não cria um arquivo SQLite apenas para exibir um estado vazio.
As operações salvas não são reescritas, e registros legados continuam legíveis.

## Organização dos arquivos

- `interface/app.py`: configuração, preservação de seleções e menu.
- `interface/paginas/`: pontos de entrada das nove páginas.
- `interface/simulador.py`: apresentação do fluxo operacional existente.
- `interface/painel.py`: dashboard, consultas e estados planejados.
- `interface/relatorios.py`: filtros, histórico e visualizações existentes.
- `interface/componentes.py`: cabeçalhos, formatação, estados e logística.
- `interface/tema.py` e `interface/estilos.css`: acabamento visual centralizado.
- `.streamlit/config.toml`: tema nativo claro com sidebar azul-marinho.
- `interface/assets/`: marca vetorial simples e ícone para sidebar recolhida.

A pasta antiga `.streamlite` foi preservada, mas não é a pasta de configuração
reconhecida pelo Streamlit. O tema ativo está na pasta correta `.streamlit`.
As cores centrais são fundo #F5F7FB, superfície branca, sidebar #101C44, ação
#3B63F6 e destaque roxo #7C3AED. Controles permanecem nativos e os ícones usam
Material Symbols. O CSS usa classes próprias e identificadores de componentes,
sem selecionar elementos por posição. Mantém foco visível e o recolhimento nativo
da sidebar. Em telas estreitas, as colunas se empilham e tabelas têm área própria.

## Verificação e capturas

```powershell
python -B -m unittest discover -s tests -v
python -m streamlit run interface/app.py
```

Foram executados testes de regras antigas, navegação das nove páginas,
preservação de estado, filtros, histórico legado e telas vazias/preenchidas.
Os registros preenchidos dos testes são fixtures, não dados de demonstração
inseridos no banco do usuário.

A pasta `docs/capturas/` contém dashboard, simulador, produtos, histórico, contêineres, fretes e impostos em
**1440 × 1050** e **390 × 844**, capturados no Chrome headless. O relatório
`verificacao.json` registra títulos, cores de fundo e ausência de exceções e
rolagem horizontal da página nesses viewports. São capturas da área visível,
não da página inteira; os demais trechos podem exigir rolagem vertical.
O script `scripts/capturar_interface.py` reproduz a captura com Streamlit em
127.0.0.1:8507 e um Chrome headless com DevTools na porta 9227. Não é necessário
para executar o produto nem adiciona dependências à aplicação.

Limites: revisão visual local em Chrome, sem matriz de navegadores ou auditoria
com leitor de tela. Precificação continua planejada. Impostos tem modo manual e exemplos didáticos; consulte `docs/tributos.md`. A calculadora de Contêineres está operacional para estimativas didáticas; consulte `docs/conteineres.md`. As tarifas e regras tributárias pré-carregadas são didáticas, sem validade comercial ou legal. Os controles operacionais continuam sendo os do Streamlit,
com adaptação das referências, sem copiar seus elementos publicitários.

Detalhes da calculadora: [fontes, fórmulas, premissas e limitações](conteineres.md).

Frete e despesas: [guia de modelos, moedas, edição e histórico](fretes.md).

Conversão compartilhada: [duas moedas, taxas, datas e histórico](cambio.md).

Detalhes da simulação tributária e sua integração ao histórico: [tributos.md](tributos.md).

Consolidação por perspectiva no simulador: [custos.md](custos.md).
