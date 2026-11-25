from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import ROOT

from reportsched.config import ConfigError, cron_trigger, load_connections, parse_report
from reportsched.params import display, render, resolve
from reportsched.scheduler import next_runs

VALID = {
    "title": "Test",
    "connection": "demo_shop",
    "query": "select * from orders where order_date >= :start_date",
    "params": {"start_date": "last_week_start"},
    "template": "templates/weekly_sales.xlsx",
}


# ---- Relative dates and placeholders ----------------------------------------------------


def test_relative_dates_from_a_wednesday():
    values = resolve(
        {
            "a": "last_week_start",
            "b": "last_week_end",
            "c": "last_month_start",
            "d": "last_month_end",
            "e": "yesterday",
            "f": "2026-01-31",
            "g": "IT",
        },
        date(2026, 11, 18),
    )
    assert values["a"] == date(2026, 11, 9)  # Monday
    assert values["b"] == date(2026, 11, 15)  # Sunday
    assert values["c"] == date(2026, 10, 1)
    assert values["d"] == date(2026, 10, 31)
    assert values["e"] == date(2026, 11, 17)
    assert values["f"] == date(2026, 1, 31)
    assert values["g"] == "IT"


def test_last_month_in_january():
    values = resolve({"s": "last_month_start", "e": "last_month_end"}, date(2027, 1, 15))
    assert values == {"s": date(2026, 12, 1), "e": date(2026, 12, 31)}


def test_placeholders():
    text = "Sales {{ start_date }} - {{end_date}} ({{ rows }}) {{ unknown }}"
    values = {"start_date": date(2026, 11, 9), "end_date": date(2026, 11, 15), "rows": 5}
    assert render(text, values) == "Sales 09/11/2026 - 15/11/2026 (5) {{ unknown }}"
    assert display(datetime(2026, 11, 9, 8, 5)) == "09/11/2026 08:05"


# ---- Cron -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("0 8 * * 1", datetime(2026, 11, 23, 8, 0)),  # standard cron: 1 = Monday
        ("0 9 * * 1-5", datetime(2026, 11, 19, 9, 0)),  # next weekday: Thursday
        ("0 7 1 * *", datetime(2026, 12, 1, 7, 0)),
        ("30 6 * * 0", datetime(2026, 11, 22, 6, 30)),  # 0 = Sunday
    ],
)
def test_cron_uses_standard_day_numbers(expression, expected):
    rome = ZoneInfo("Europe/Rome")
    now = datetime(2026, 11, 18, 12, 0, tzinfo=rome)  # Wednesday noon
    fire = cron_trigger(expression, rome).get_next_fire_time(None, now)
    assert fire.replace(tzinfo=None) == expected


def test_invalid_cron():
    with pytest.raises(ValueError):
        cron_trigger("every monday")


def test_next_runs(reports):
    runs = next_runs(reports["weekly_sales_by_category"], count=3)
    assert len(runs) == 3
    assert all(moment.weekday() == 0 and moment.hour == 8 for moment in runs)


# ---- Report files -----------------------------------------------------------------------


def test_sample_reports_load(reports):
    assert set(reports) == {
        "weekly_sales_by_category",
        "monthly_country_summary",
        "daily_cancelled_orders",
    }
    weekly = reports["weekly_sales_by_category"]
    assert weekly.email.to == ["sales-team@example.com"]
    assert weekly.total_columns == ["orders", "units", "revenue"]


def test_valid_report():
    report = parse_report("test", VALID, ROOT)
    assert report.params == {"start_date": "last_week_start"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"title": ""}, "'title' is required"),
        ({"query": "delete from orders where order_date >= :start_date"}, "must start with SELECT"),
        ({"query": "select 1 where 1 = :start_date; drop table orders"}, "only one SQL statement"),
        ({"params": {"start_date": "last_wek_start"}}, "unknown relative date"),
        ({"params": {"end_date": "today"}}, "not used in the query"),
        ({"schedule": "0 25 * * *"}, "invalid schedule"),
        ({"template": "templates/missing.xlsx"}, "template not found"),
        ({"email": {"subject": "x"}}, "at least one recipient"),
    ],
)
def test_invalid_reports_are_rejected(change, message):
    with pytest.raises(ConfigError, match=message):
        parse_report("test", {**VALID, **change}, ROOT)


def test_connections_read_passwords_from_environment(tmp_path, monkeypatch):
    path = tmp_path / "connections.yml"
    path.write_text('connections:\n  dw: "postgresql://${DB_USER}:${DB_PASS}@host/db"\n')
    monkeypatch.setenv("DB_USER", "reader")
    monkeypatch.setenv("DB_PASS", "secret")
    assert load_connections(path) == {"dw": "postgresql://reader:secret@host/db"}

    monkeypatch.delenv("DB_PASS")
    with pytest.raises(ConfigError, match="DB_PASS"):
        load_connections(path)
