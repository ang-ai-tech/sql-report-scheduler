"""Report parameters with relative dates ("last week", "last month"...) and text placeholders."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta


def _month_start(day: date) -> date:
    return day.replace(day=1)


def _last_month_end(day: date) -> date:
    return _month_start(day) - timedelta(days=1)


# Each name is computed from the date the report runs.
RELATIVE_DATES = {
    "today": lambda d: d,
    "yesterday": lambda d: d - timedelta(days=1),
    "week_start": lambda d: d - timedelta(days=d.weekday()),  # Monday of this week
    "last_week_start": lambda d: d - timedelta(days=d.weekday() + 7),  # Monday
    "last_week_end": lambda d: d - timedelta(days=d.weekday() + 1),  # Sunday
    "month_start": _month_start,
    "last_month_start": lambda d: _month_start(_last_month_end(d)),
    "last_month_end": _last_month_end,
    "year_start": lambda d: d.replace(month=1, day=1),
}


def resolve(params: dict[str, str], run_date: date) -> dict[str, date | str]:
    """Turn the parameters of a report into values for the query.

    "last_week_start" becomes a date, "2026-01-31" becomes that date, anything else stays text.
    """
    values: dict[str, date | str] = {}
    for name, value in params.items():
        text = str(value).strip()
        if text in RELATIVE_DATES:
            values[name] = RELATIVE_DATES[text](run_date)
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            values[name] = date.fromisoformat(text)
        else:
            values[name] = text
    return values


def display(value: object) -> str:
    """How a value appears in Excel titles and e-mails (European date format)."""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    return str(value)


PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render(text: str, values: dict[str, object]) -> str:
    """Replace {{ name }} with the value of name; unknown names are left as they are."""

    def replace(match: re.Match) -> str:
        name = match.group(1)
        return display(values[name]) if name in values else match.group(0)

    return PLACEHOLDER.sub(replace, text)
