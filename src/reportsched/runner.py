"""Run one report from start to finish: parameters -> query -> Excel -> e-mail -> history."""

from __future__ import annotations

import logging
import smtplib
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.exc import OperationalError

from reportsched import history, mailer
from reportsched.config import Report
from reportsched.excel import fill_template
from reportsched.params import render, resolve
from reportsched.query import run_query

log = logging.getLogger(__name__)

OUTPUT_DIR = Path("output")
# Problems that can go away by themselves (database or mail server briefly unreachable).
TRANSIENT_ERRORS = (OperationalError, smtplib.SMTPException, ConnectionError, TimeoutError)


@dataclass
class RunResult:
    report: str
    status: str  # success | failed
    rows: int = 0
    output_file: Path | None = None
    emailed_to: list[str] | None = None
    attempts: int = 0
    error: str | None = None


def placeholder_values(report: Report, run_date: date) -> dict[str, object]:
    """Values available as {{ name }} in the Excel template, subject and body."""
    return {
        "title": report.title,
        "report": report.name,
        "run_date": run_date,
        "generated_at": datetime.now(),
        **resolve(report.params, run_date),
    }


def preview(report: Report, connections: dict[str, str], run_date: date) -> pd.DataFrame:
    """Only run the query: used by `reports preview` and the web interface."""
    return run_query(connections[report.connection], report.query, resolve(report.params, run_date))


def build_excel(
    report: Report, connections: dict[str, str], run_date: date, output_dir: Path = OUTPUT_DIR
) -> tuple[Path, int]:
    data = preview(report, connections, run_date)
    output = output_dir / report.name / f"{report.name}_{run_date:%Y-%m-%d}.xlsx"
    fill_template(
        report.template,
        data,
        output,
        header_row=report.header_row,
        sheet=report.sheet,
        total_columns=report.total_columns,
        placeholders=placeholder_values(report, run_date),
    )
    return output, len(data)


def run_report(
    report: Report,
    connections: dict[str, str],
    *,
    run_date: date | None = None,
    send_email: bool = True,
    trigger: str = "manual",
    output_dir: Path = OUTPUT_DIR,
    history_db: Path = history.HISTORY_DB,
    smtp: mailer.SmtpSettings | None = None,
    smtp_factory=smtplib.SMTP,
    retries: int = 2,
    retry_delay: float = 60,
    sleep=time.sleep,
) -> RunResult:
    """Never raises: failures are logged and recorded in the history."""
    run_date = run_date or date.today()
    result = RunResult(report.name, "failed")
    connection = history.connect(history_db)
    run_id = history.start_run(connection, report.name, trigger)

    for attempt in range(1, retries + 2):
        result.attempts = attempt
        try:
            result.output_file, result.rows = build_excel(report, connections, run_date, output_dir)
            if send_email and report.email:
                values = {**placeholder_values(report, run_date), "rows": result.rows}
                message = mailer.build_message(
                    (smtp or mailer.SmtpSettings.from_env()).sender,
                    report.email.to,
                    report.email.cc,
                    render(report.email.subject, values),
                    render(report.email.body, values),
                    result.output_file,
                )
                mailer.send(message, smtp or mailer.SmtpSettings.from_env(), smtp_factory)
                result.emailed_to = report.email.to + report.email.cc
            result.status, result.error = "success", None
            break
        except TRANSIENT_ERRORS as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            log.warning("%s attempt %d failed: %s", report.name, attempt, result.error)
            if attempt <= retries:
                sleep(retry_delay)
        except Exception as exc:  # configuration problems: retrying would not help
            result.error = f"{type(exc).__name__}: {exc}"
            log.error("%s failed: %s", report.name, result.error)
            break

    history.finish_run(
        connection,
        run_id,
        status=result.status,
        rows=result.rows,
        attempts=result.attempts,
        output_file=str(result.output_file) if result.output_file else None,
        emailed_to=", ".join(result.emailed_to or []) or None,
        error_message=result.error,
    )
    connection.close()
    log.info("%s: %s, %d rows", report.name, result.status, result.rows)
    return result
