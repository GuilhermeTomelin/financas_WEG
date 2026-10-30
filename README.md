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
