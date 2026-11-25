# ADR 0003 — APScheduler with standard cron, SMTP tested with Mailpit

**Status:** accepted

## Context
Reports must run at fixed times. Options range from the operating system's scheduler (cron, Windows Task Scheduler) to an orchestrator such as Airflow. E-mail sending must be testable without sending real e-mails.

## Decision
- Use **APScheduler** inside one Python process (`reports schedule`): no extra infrastructure, and the same code runs on Windows, Linux and in Docker.
- Write schedules in **standard 5-field cron syntax**, known to IT people, and convert day numbers because APScheduler counts Monday as 0.
- Send e-mails with Python's `smtplib`, configured from environment variables.
- Use **Mailpit** (a fake SMTP server with a web inbox) in Docker and in CI.

## Consequences
- Simple to run and to explain; Airflow (used in the Financial Data Platform project) would be oversized for sending a few files.
- One scheduler process is a single point of failure; APScheduler can keep jobs in a shared database if high availability is needed.
- The demo and CI send real SMTP messages that never leave the machine, and CI checks the attachment through Mailpit's API.
