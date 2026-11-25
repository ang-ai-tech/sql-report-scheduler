from datetime import date

import pandas as pd
import pytest
from conftest import TODAY
from openpyxl import load_workbook

from reportsched import history
from reportsched.excel import TemplateError, fill_template
from reportsched.mailer import SmtpSettings
from reportsched.query import run_query
from reportsched.runner import run_report
from reportsched.scheduler import build_scheduler

SMTP = SmtpSettings(host="mail.test", port=25, sender="reports@example.com")


# ---- Query ------------------------------------------------------------------------------


def test_query_with_date_parameters(demo_url):
    data = run_query(
        demo_url,
        "select count(*) as n from orders where order_date between :start and :end",
        {"start": date(2026, 11, 9), "end": date(2026, 11, 15)},
    )
    assert data.loc[0, "n"] > 50


def test_parameters_are_not_pasted_into_sql(demo_url):
    """A malicious value is treated as text, so it simply matches nothing."""
    data = run_query(
        demo_url,
        "select count(*) as n from customers where country_code = :country",
        {"country": "IT' or '1'='1"},
    )
    assert data.loc[0, "n"] == 0


# ---- Excel ------------------------------------------------------------------------------


def _data():
    return pd.DataFrame(
        {"category": ["Decor", "Office"], "orders": [3, 2], "units": [4, 2], "revenue": [10.5, 4.0]}
    )


def test_template_is_filled_with_formats_totals_and_placeholders(templates, tmp_path):
    out = fill_template(
        templates / "weekly_sales.xlsx",
        _data(),
        tmp_path / "out.xlsx",
        total_columns=["orders", "revenue"],
        placeholders={"title": "Weekly sales", "start_date": date(2026, 11, 9)},
    )
    ws = load_workbook(out).active
    assert ws["A1"].value == "Weekly sales"
    assert ws["A2"].value.startswith("Period: 09/11/2026")
    assert "2 rows" in ws["A3"].value
    assert [ws.cell(6, c).value for c in range(1, 5)] == ["Decor", 3, 4, 10.5]
    assert ws["D7"].number_format == ws["D6"].number_format == '#,##0.00 "€"'
    assert ws["A8"].value == "Total"
    assert ws["B8"].value == "=SUM(B6:B7)"
    assert ws["D8"].value == "=SUM(D6:D7)"
    assert ws["C8"].value is None  # units not in total_columns


def test_template_column_mismatch(templates, tmp_path):
    with pytest.raises(TemplateError, match="4 columns"):
        fill_template(templates / "weekly_sales.xlsx", _data()[["category"]], tmp_path / "x.xlsx")


def test_empty_result_says_so(templates, tmp_path):
    out = fill_template(templates / "weekly_sales.xlsx", _data().iloc[0:0], tmp_path / "e.xlsx")
    assert load_workbook(out).active["A6"].value == "No data for this period"


# ---- Whole run --------------------------------------------------------------------------


def _run(report, connections, tmp_path, fake_smtp, **kwargs):
    return run_report(
        report,
        connections,
        run_date=TODAY,
        output_dir=tmp_path / "output",
        history_db=tmp_path / "history.db",
        smtp=SMTP,
        smtp_factory=fake_smtp,
        sleep=lambda seconds: None,
        **kwargs,
    )


def test_run_sends_the_excel_and_records_history(reports, connections, tmp_path, fake_smtp):
    result = _run(reports["weekly_sales_by_category"], connections, tmp_path, fake_smtp)
    assert result.status == "success"
    assert result.rows == 5  # five categories
    assert result.output_file.name == "weekly_sales_by_category_2026-11-18.xlsx"

    message = fake_smtp.sent[0]
    assert message["To"] == "sales-team@example.com"
    assert message["Cc"] == "management@example.com"
    assert message["Subject"] == "Weekly sales by category 09/11/2026 - 15/11/2026"
    attachment = next(message.iter_attachments())
    assert attachment.get_filename() == result.output_file.name

    run = history.list_runs(history.connect(tmp_path / "history.db"))[0]
    assert run["status"] == "success" and run["rows"] == 5 and run["attempts"] == 1


def test_temporary_mail_problem_is_retried(reports, connections, tmp_path, fake_smtp):
    fake_smtp.failures_left = 1
    result = _run(reports["daily_cancelled_orders"], connections, tmp_path, fake_smtp)
    assert result.status == "success"
    assert result.attempts == 2


def test_failure_is_recorded_not_raised(reports, connections, tmp_path, fake_smtp):
    fake_smtp.failures_left = 5
    result = _run(reports["daily_cancelled_orders"], connections, tmp_path, fake_smtp, retries=2)
    assert result.status == "failed"
    assert result.attempts == 3
    assert "SMTPServerDisconnected" in result.error
    run = history.list_runs(history.connect(tmp_path / "history.db"))[0]
    assert run["status"] == "failed" and "SMTPServerDisconnected" in run["error_message"]


def test_run_without_email(reports, connections, tmp_path, fake_smtp):
    result = _run(
        reports["monthly_country_summary"], connections, tmp_path, fake_smtp, send_email=False
    )
    assert result.status == "success" and result.output_file.exists()
    assert fake_smtp.sent == [] and result.emailed_to is None


def test_scheduler_has_one_job_per_scheduled_report(reports, connections):
    jobs = build_scheduler(reports, connections).get_jobs()
    assert {job.id for job in jobs} == set(reports)
