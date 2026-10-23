"""App state in SQLite (built into Python; one file in app_data/). job.json stays the source of truth for an edit;
the database holds what the app adds: projects it knows, runs, notes, versions, connection test results, and the agent
team's dispatches with each agent's run."""
import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
create table if not exists projects (id integer primary key, path text unique not null, created real not null,
    brief text not null default '{}');
create table if not exists runs (id integer primary key, project integer not null, stage text not null, force integer not null,
    status text not null, queued real not null, started real, ended real, log text not null default '', result text);
create table if not exists notes (id integer primary key, project integer not null, variant text, t real, beat integer,
    text text not null, owner text not null, reason text not null, status text not null default 'open',
    created real not null, fixed_in integer, agent_reply text);
create table if not exists versions (id integer primary key, project integer not null, n integer not null, created real not null,
    final integer not null, files text not null, qa_score real, qa_passed integer, run integer);
create table if not exists connection_tests (id text primary key, ok integer not null, message text not null, at real not null);
create table if not exists dispatches (id integer primary key, project integer not null, kind text not null,
    status text not null, budget real not null, spent real not null default 0, message text not null default '',
    started real not null, ended real);
create table if not exists agent_runs (id integer primary key, project integer not null, dispatch integer not null,
    role text not null, round integer not null, status text not null, task text not null, reply text not null default '',
    cost real not null default 0, changes integer not null default 0, log text not null default '', started real,
    ended real);
"""


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.Lock()
        self.con = sqlite3.connect(str(path), check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        with self.lock:
            self.con.executescript(SCHEMA)
            self.con.commit()

    def q(self, sql: str, args=()) -> list:
        with self.lock:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def one(self, sql: str, args=()):
        r = self.q(sql, args)
        return r[0] if r else None

    def close(self):
        with self.lock:
            self.con.close()

    def x(self, sql: str, args=()) -> int:
        with self.lock:
            cur = self.con.execute(sql, args)
            self.con.commit()
            return cur.lastrowid


def now() -> float:
    return round(time.time(), 3)


def dumps(x) -> str:
    return json.dumps(x, ensure_ascii=False)
