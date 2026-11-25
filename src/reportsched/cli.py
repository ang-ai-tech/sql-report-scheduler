"""Command line: `reports list | preview | run | schedule | history | demo`."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from reportsched import history
from reportsched.config import ConfigError, load_connections, load_reports
from reportsched.demo import create_demo_db, create_templates
from reportsched.runner import preview, run_report
from reportsched.scheduler import build_scheduler, next_runs


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="reports", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List the reports and their next scheduled run")
    for name, text in (
        ("preview", "Show the data of a report without creating files"),
        ("run", "Create the Excel file and send it by e-mail now"),
    ):
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("report")
        cmd.add_argument("--date", type=date.fromisoformat, help="pretend today is this date")
    sub.choices["run"].add_argument("--no-email", action="store_true", help="only create the file")
    schedule = sub.add_parser("schedule", help="Keep running and send reports on schedule")
    schedule.add_argument("--run-now", action="store_true", help="also run every report at start")
    sub.add_parser("history", help="Show the last runs")
    demo = sub.add_parser("demo", help="Create the demo database and Excel templates")
    demo.add_argument("--if-missing", action="store_true", help="keep an existing demo database")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv)
    try:
        _run(args)
    except (ConfigError, KeyError) as exc:
        sys.exit(f"Error: {exc}")


def _run(args) -> None:
    if args.command == "demo":
        from reportsched.demo import DEMO_DB

        if not (args.if_missing and DEMO_DB.exists()):
            print(f"Demo database: {create_demo_db()}")
        for path in create_templates():
            print(f"Template: {path}")
        return

    if args.command == "history":
        for run in history.list_runs(history.connect(), limit=20):
            print(
                f"{run['started_at']}  {run['report']:<28} {run['trigger']:<8} "
                f"{run['status']:<8} rows={run['rows']}  {run['error_message'] or ''}"
            )
        return

    reports = load_reports()
    connections = load_connections()

    if args.command == "list":
        for report in reports.values():
            upcoming = next_runs(report, count=1)
            when = f"{upcoming[0]:%a %d/%m/%Y %H:%M}" if upcoming else "manual only"
            print(f"{report.name:<28} {report.schedule or '-':<14} next: {when}  {report.title}")
        return

    if args.command in ("preview", "run") and args.report not in reports:
        raise KeyError(f"no report named '{args.report}'. Available: {', '.join(reports)}")

    if args.command == "preview":
        data = preview(reports[args.report], connections, args.date or date.today())
        print(data.to_string(index=False) if not data.empty else "No data for this period")

    elif args.command == "run":
        result = run_report(
            reports[args.report],
            connections,
            run_date=args.date,
            send_email=not args.no_email,
        )
        print(f"{result.status}: {result.rows} rows -> {result.output_file}")
        if result.emailed_to:
            print(f"Sent to {', '.join(result.emailed_to)}")
        if result.status != "success":
            sys.exit(f"Error: {result.error}")

    elif args.command == "schedule":
        if args.run_now:
            for report in reports.values():
                run_report(report, connections, trigger="schedule")
        scheduler = build_scheduler(reports, connections)
        for job in scheduler.get_jobs():
            print(f"Scheduled {job.id}: {job.trigger}")
        print("Waiting for the next run (Ctrl+C to stop)...")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    main()
