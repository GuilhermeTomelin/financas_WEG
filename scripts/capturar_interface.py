"""Revisão local via Chrome DevTools. Requer Chrome headless na porta 9227.

Inicie o Streamlit na porta 8507 antes de executar. Não instala navegador nem
altera dados da aplicação; salva apenas screenshots e relatório em docs/capturas.
"""
import base64
import json
from pathlib import Path
import time
import requests
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[1]


def main():
    destino=ROOT/"docs"/"capturas"
    destino.mkdir(exist_ok=True)
    paginas=requests.get("http://127.0.0.1:9227/json",timeout=5).json()
    pagina=next(p for p in paginas if p["type"]=="page" and (p["url"]=="about:blank" or p["url"].startswith("http://127.0.0.1:8507")))
    relatorio=[]
    with connect(pagina["webSocketDebuggerUrl"],max_size=None) as ws:
        contador=0
        def cdp(metodo,parametros=None):
            nonlocal contador
            contador+=1
            ws.send(json.dumps(dict(id=contador,method=metodo,params=parametros or {})))
            while True:
                msg=json.loads(ws.recv(timeout=30))
                if msg.get("id")==contador:
                    if "error" in msg:
                        raise RuntimeError(msg["error"])
                    return msg.get("result",{})
        def avaliar(js):
            resultado=cdp("Runtime.evaluate",dict(expression=js,returnByValue=True))
            if "exceptionDetails" in resultado:
                raise RuntimeError(resultado["exceptionDetails"])
            return resultado["result"].get("value")
        cdp("Page.enable")
        for tamanho,largura,altura in (("desktop",1440,1050),("mobile",390,844)):
            cdp("Emulation.setDeviceMetricsOverride",dict(width=largura,height=altura,deviceScaleFactor=1,mobile=False,screenWidth=largura,screenHeight=altura))
            for nome,caminho in (("dashboard",""),("simulador","simulador"),("produtos","produtos"),("historico","historico"),("conteineres","conteineres"),("fretes","rotas")):
                cdp("Page.navigate",dict(url="http://127.0.0.1:8507/"+caminho))
                titulo={"dashboard":"Dashboard","simulador":"Simulador","produtos":"Produtos","historico":"Histórico e relatórios","conteineres":"Contêineres","fretes":"Fretes e rotas"}[nome]
                marcador={"simulador":"Mercadorias e logística por moeda","conteineres":"Resumo da carga","fretes":"Resumo logístico"}.get(nome,titulo)
                for _ in range(150):
                    pronto=avaliar("Boolean(document.querySelector('h1')?.textContent === " + json.dumps(titulo) + " && document.body.innerText.includes(" + json.dumps(marcador) + ") && document.querySelectorAll('[data-testid=stSkeleton]').length === 0)")
                    if pronto:
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError("Página não carregou: "+nome)
                time.sleep(.7)
                resumo=avaliar("""JSON.stringify({titulo:document.querySelector('h1').textContent,
                    largura:innerWidth,scroll:document.documentElement.scrollWidth,
                    erro:document.querySelector('[data-testid=stException]')?.textContent || null,
                    sidebar: getComputedStyle(document.querySelector('[data-testid=stSidebar]')).backgroundColor,
                    fundo:getComputedStyle(document.querySelector('[data-testid=stAppViewContainer]')).backgroundColor,
                    legenda:getComputedStyle(document.querySelector('[data-testid=stMain] [data-testid=stCaptionContainer] p')).color})""")
                resumo=json.loads(resumo)
                if nome == "conteineres" and not avaliar("document.body.innerText.includes('Resumo da carga')"):
                    raise RuntimeError("Servidor não está exibindo a calculadora atual; reinicie o Streamlit antes de capturar.")
                if nome == "fretes" and not avaliar("document.body.innerText.includes('Resumo logístico')"):
                    raise RuntimeError("Servidor não está exibindo a simulação logística atual; reinicie o Streamlit.")
                if nome in ("simulador","fretes") and not avaliar("document.body.innerText.includes('Mercadorias e logística por moeda')"):
                    raise RuntimeError("Servidor não está exibindo a consolidação monetária atual; reinicie o Streamlit.")
                if resumo["erro"] or resumo["scroll"]>largura:
                    raise RuntimeError(resumo)
                captura=cdp("Page.captureScreenshot",dict(format="png",captureBeyondViewport=False))
                arquivo=destino/f"{nome}-{tamanho}.png"
                arquivo.write_bytes(base64.b64decode(captura["data"]))
                relatorio.append(dict(pagina=nome,tamanho=tamanho,arquivo=arquivo.name,**resumo))
                print(nome,tamanho,resumo)
                if nome == "simulador":
                    avaliar("[...document.querySelectorAll('h2,h3')].find(e=>e.textContent==='Mercadorias e logística por moeda').scrollIntoView({block:'start'})")
                    time.sleep(.3)
                    captura_cambio=cdp("Page.captureScreenshot",dict(format="png",captureBeyondViewport=False))
                    (destino/f"conversao-{tamanho}.png").write_bytes(base64.b64decode(captura_cambio["data"]))
                if nome == "fretes":
                    avaliar("[...document.querySelectorAll('h2,h3')].find(e=>e.textContent==='Resumo logístico').scrollIntoView({block:'start'})")
                    time.sleep(.3)
                    captura_resumo=cdp("Page.captureScreenshot",dict(format="png",captureBeyondViewport=False))
                    (destino/f"fretes-resumo-{tamanho}.png").write_bytes(base64.b64decode(captura_resumo["data"]))
        (destino/"verificacao.json").write_text(json.dumps(relatorio,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
