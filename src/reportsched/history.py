"""Run history in a small SQLite database: when each report ran, with what result."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

HISTORY_DB = Path("data/history.db")

SCHEMA = """
create table if not exists runs (
    id            integer primary key autoincrement,
    report        text not null,
    trigger       text not null check (trigger in ('manual', 'schedule')),
    started_at    text not null,
    finished_at   text,
    status        text not null check (status in ('running', 'success', 'failed')),
    rows          integer,
    attempts      integer,
    output_file   text,
    emailed_to    text,
    error_message text
);
"""


def connect(path: Path = HISTORY_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def start_run(connection: sqlite3.Connection, report: str, trigger: str) -> int:
    with connection:
        cursor = connection.execute(
            "insert into runs (report, trigger, started_at, status) values (?, ?, ?, 'running')",
            (report, trigger, _now()),
        )
    return cursor.lastrowid


def finish_run(connection: sqlite3.Connection, run_id: int, **values) -> None:
    columns = ", ".join(f"{name} = ?" for name in values)
    with connection:
        connection.execute(
            f"update runs set finished_at = ?, {columns} where id = ?",
            (_now(), *values.values(), run_id),
        )


def list_runs(connection: sqlite3.Connection, report: str | None = None, limit: int = 50):
    query = "select * from runs"
    args: tuple = ()
    if report:
        query += " where report = ?"
        args = (report,)
    query += " order by id desc limit ?"
    return [dict(row) for row in connection.execute(query, (*args, limit))]
