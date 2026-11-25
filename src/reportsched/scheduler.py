"""Run every report at the times given by its cron schedule."""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from reportsched.config import Report, cron_trigger
from reportsched.runner import run_report


def timezone() -> ZoneInfo:
    return ZoneInfo(os.environ.get("REPORTS_TIMEZONE", "Europe/Rome"))


def next_runs(report: Report, count: int = 3, now: datetime | None = None) -> list[datetime]:
    """The next times a report will run (empty if it has no schedule)."""
    if not report.schedule:
        return []
    trigger = cron_trigger(report.schedule, timezone())
    moments, previous = [], None
    current = now or datetime.now(timezone())
    for _ in range(count):
        moment = trigger.get_next_fire_time(previous, current)
        moments.append(moment)
        previous, current = moment, moment
    return moments


def build_scheduler(reports: dict[str, Report], connections: dict[str, str]) -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=timezone())
    for report in reports.values():
        if not report.schedule:
            continue
        scheduler.add_job(
            run_report,
            cron_trigger(report.schedule, timezone()),
            args=[report, connections],
            kwargs={"trigger": "schedule"},
            id=report.name,
            name=report.title,
            coalesce=True,  # if several runs were missed, run only once
            misfire_grace_time=3600,  # still run if the scheduler was down for up to an hour
            max_instances=1,
        )
    return scheduler
