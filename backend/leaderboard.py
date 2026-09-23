"""Persistent demo ranking. Scores always come from the server, never the client."""
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.engine import Scenario, simulate


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_name: str = Field(min_length=2, max_length=40)
    token: UUID
    scenario: Scenario

    @field_validator("team_name")
    @classmethod
    def clean_name(cls, value):
        value = " ".join(value.split())
        if len(value) < 2 or any(not (c.isalnum() or c in " -_.") for c in value):
            raise ValueError("Используйте буквы, цифры, пробел, дефис или точку в названии команды.")
        return value


@contextmanager
def database():
    path = Path(os.getenv("DATABASE_PATH", "runtime/city.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS scores (
            owner TEXT NOT NULL, team_name TEXT NOT NULL, name_key TEXT NOT NULL,
            ruleset TEXT NOT NULL, event_id TEXT NOT NULL, score REAL NOT NULL,
            spent INTEGER NOT NULL, critical INTEGER NOT NULL, scenario TEXT NOT NULL,
            updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(owner, ruleset, event_id), UNIQUE(name_key, ruleset, event_id))""")
        db.execute("CREATE TABLE IF NOT EXISTS ai_usage (day TEXT PRIMARY KEY, calls INTEGER NOT NULL)")
        yield db
        db.commit()
    finally:
        db.close()


def submit(value):
    result = simulate(value.scenario)
    owner = sha256(str(value.token).encode()).hexdigest()
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        previous = db.execute("SELECT 1 FROM scores WHERE owner=? AND ruleset=? AND event_id=?",
                              (owner, value.scenario.ruleset, value.scenario.event_id)).fetchone()
        if not previous and db.execute("SELECT COUNT(*) FROM scores").fetchone()[0] >= 1000:
            raise ValueError("Таблица заполнена. Обратитесь к организатору демонстрации.")
        try:
            db.execute("""INSERT INTO scores(owner,team_name,name_key,ruleset,event_id,score,spent,critical,scenario)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(owner,ruleset,event_id) DO UPDATE SET
                team_name=excluded.team_name,name_key=excluded.name_key,score=excluded.score,
                spent=excluded.spent,critical=excluded.critical,scenario=excluded.scenario,updated=CURRENT_TIMESTAMP""",
                (owner, value.team_name, value.team_name.casefold(), value.scenario.ruleset,
                 value.scenario.event_id, result["result"]["score"], result["spent"],
                 result["result"]["critical_count"], value.scenario.model_dump_json()))
        except sqlite3.IntegrityError:
            raise ValueError("Это название уже занято. Выберите другое.") from None
    return {"score": result["result"]["score"], "team_name": value.team_name}


def ranking(ruleset, event_id):
    with database() as db:
        rows = db.execute("""SELECT team_name,score,spent,critical,updated FROM scores
            WHERE ruleset=? AND event_id=? ORDER BY score DESC,spent ASC,name_key ASC LIMIT 50""",
            (ruleset, event_id)).fetchall()
    return {"entries": [dict(row) for row in rows], "ruleset": ruleset, "event_id": event_id,
            "notice": "Демонстрационный рейтинг: названия команд не удостоверяют личность. Публикуется последний отправленный результат."}


def reserve_ai_call():
    """Shared daily cap survives restart. Failed provider requests also count."""
    limit = max(0, int(os.getenv("AI_DAILY_LIMIT", "100")))
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO ai_usage(day,calls) VALUES(date('now'),0)")
        changed = db.execute("UPDATE ai_usage SET calls=calls+1 WHERE day=date('now') AND calls<?", (limit,)).rowcount
    return bool(changed)
