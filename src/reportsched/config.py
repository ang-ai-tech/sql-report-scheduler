"""Read and check the configuration: database connections and one YAML file per report."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from apscheduler.triggers.cron import CronTrigger

from reportsched.params import RELATIVE_DATES

CONFIG_DIR = Path("config")


class ConfigError(ValueError):
    """A report or connection is not configured correctly."""


DAY_NAMES = ["sun", "mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def cron_trigger(expression: str, timezone=None) -> CronTrigger:
    """A standard 5-field cron expression: minute hour day-of-month month day-of-week.

    In standard cron 0 or 7 = Sunday and 1 = Monday, while APScheduler counts Monday as 0.
    Day numbers are therefore converted to names first ("1-5" -> "mon-fri").
    """
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("a cron expression has 5 fields: minute hour day month day-of-week")
    minute, hour, day, month, day_of_week = fields
    day_of_week = re.sub(r"(?<![/\d])[0-7](?!\d)", lambda m: DAY_NAMES[int(m.group())], day_of_week)
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=timezone,
    )


@dataclass(frozen=True)
class EmailSpec:
    to: list[str]
    subject: str
    body: str
    cc: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Report:
    name: str  # file name without .yml, used in commands: `reports run <name>`
    title: str
    description: str
    connection: str
    query: str
    template: Path
    params: dict[str, str] = field(default_factory=dict)
    schedule: str | None = None  # cron expression, e.g. "0 8 * * 1" = Mondays at 8:00
    email: EmailSpec | None = None
    total_columns: list[str] = field(default_factory=list)
    header_row: int = 5
    sheet: str | None = None


def _expand_env(value: str, where: str) -> str:
    """Replace ${VAR} with environment variables, so passwords stay out of the files."""
    missing = [name for name in re.findall(r"\$\{(\w+)\}", value) if name not in os.environ]
    if missing:
        raise ConfigError(f"{where}: environment variable(s) not set: {', '.join(missing)}")
    return os.path.expandvars(value)


def load_connections(path: Path = CONFIG_DIR / "connections.yml") -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        name: _expand_env(str(url), f"connection '{name}'")
        for name, url in (data.get("connections") or {}).items()
    }


def _check_query(query: str, where: str) -> None:
    """Reports only read data: the query must be a single SELECT (or WITH ... SELECT)."""
    cleaned = re.sub(r"--[^\n]*", "", query).strip().rstrip(";")
    if not re.match(r"(?is)^(select|with)\b", cleaned):
        raise ConfigError(f"{where}: the query must start with SELECT or WITH")
    if ";" in cleaned:
        raise ConfigError(f"{where}: only one SQL statement is allowed")


def parse_report(name: str, data: dict, base_dir: Path = Path(".")) -> Report:
    where = f"report '{name}'"
    for key in ("title", "connection", "query", "template"):
        if not data.get(key):
            raise ConfigError(f"{where}: '{key}' is required")
    _check_query(data["query"], where)

    params = {key: str(value) for key, value in (data.get("params") or {}).items()}
    for key, value in params.items():
        if value.endswith(("_start", "_end", "day")) and value not in RELATIVE_DATES:
            raise ConfigError(f"{where}: unknown relative date '{value}' for parameter '{key}'")
        if f":{key}" not in data["query"]:
            raise ConfigError(f"{where}: parameter '{key}' is not used in the query (:{key})")

    schedule = data.get("schedule")
    if schedule:
        try:
            cron_trigger(schedule)
        except ValueError as exc:
            raise ConfigError(f"{where}: invalid schedule '{schedule}': {exc}") from None

    template = base_dir / data["template"]
    if not template.exists():
        raise ConfigError(f"{where}: template not found: {template}")

    email = None
    if data.get("email"):
        mail = data["email"]
        if not mail.get("to"):
            raise ConfigError(f"{where}: e-mail needs at least one recipient in 'to'")
        email = EmailSpec(
            to=list(mail["to"]),
            cc=list(mail.get("cc") or []),
            subject=mail.get("subject", data["title"]),
            body=mail.get("body", "Please find the report attached."),
        )

    return Report(
        name=name,
        title=data["title"],
        description=data.get("description", ""),
        connection=data["connection"],
        query=data["query"],
        template=template,
        params=params,
        schedule=schedule,
        email=email,
        total_columns=list(data.get("total_columns") or []),
        header_row=int(data.get("header_row", 5)),
        sheet=data.get("sheet"),
    )


def load_reports(directory: Path = CONFIG_DIR / "reports", base_dir: Path = Path(".")):
    """All reports in the folder, by name. Every file is checked when it is loaded."""
    reports = {}
    for path in sorted(directory.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        reports[path.stem] = parse_report(path.stem, data, base_dir)
    return reports
