"""Run a report query on any database supported by SQLAlchemy."""

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import Date, bindparam, create_engine, text


def run_query(url: str, sql: str, values: dict[str, object]) -> pd.DataFrame:
    """Parameters are bound by the database driver, never pasted into the SQL text.

    This prevents SQL injection and lets each database handle dates in its own way.
    """
    statement = text(sql)
    date_params = [name for name, value in values.items() if isinstance(value, date)]
    if date_params:
        statement = statement.bindparams(*(bindparam(name, type_=Date) for name in date_params))
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return pd.read_sql(statement, connection, params=values)
    finally:
        engine.dispose()
