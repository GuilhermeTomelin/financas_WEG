import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

BANCO = Path(__file__).resolve().parents[1] / "dados" / "simulacoes.sqlite3"


def conectar():
    BANCO.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(BANCO, timeout=10)
    db.execute("""CREATE TABLE IF NOT EXISTS simulacoes (
        id INTEGER PRIMARY KEY, resultado TEXT UNIQUE NOT NULL,
        salvo TEXT NOT NULL, operacao TEXT NOT NULL)""")
    return db


def salvar(chave, operacao):
    with closing(conectar()) as db, db:
        db.execute("""INSERT INTO simulacoes(resultado,salvo,operacao) VALUES(?,?,?)
                   ON CONFLICT(resultado) DO NOTHING""",
                   (chave, datetime.now(timezone.utc).isoformat(),
                    json.dumps(operacao, ensure_ascii=False, allow_nan=False)))
        return db.execute("SELECT id FROM simulacoes WHERE resultado=?", (chave,)).fetchone()[0]


def listar():
    with closing(conectar()) as db:
        return [dict(json.loads(dados), id=id_, salvo=salvo)
                for id_, salvo, dados in db.execute(
                    "SELECT id,salvo,operacao FROM simulacoes ORDER BY salvo DESC,id DESC")]
