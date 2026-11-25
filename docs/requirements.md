# Requirements & Acceptance Criteria

## 1. Business context

In a (fictional) online store, sales, management and customer service receive the same Excel reports every week or month. Today an analyst runs the queries by hand, pastes the results into Excel files with the usual formatting and sends them by e-mail. When the analyst is on holiday, the reports are late or missing.

## 2. Goal

Define each report once (query, Excel template, recipients, schedule) and have it delivered automatically, with a record of every run.

## 3. Stakeholders

| Persona | Need |
|---|---|
| Report recipient | Their usual Excel file, formatted as always, in the inbox on time |
| Analyst | Stop doing it by hand; add or change a report without writing code |
| IT | No secrets in files, read-only access to the databases, a log of what was sent |

## 4. Scope

**In scope:** SQL queries on any SQLAlchemy-supported database, relative date parameters, Excel templates, e-mail delivery, cron schedules, run history, retries, a web interface to preview, download and send now.

**Out of scope (v1):** a report editor in the web interface, user login and permissions, PDF output, delivery channels other than e-mail.

## 5. Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | A report is defined in one YAML file: title, connection, query, parameters, template, recipients, schedule. |
| FR-2 | Parameters can be relative dates computed from the run date (last week, last month...). |
| FR-3 | The query result fills an Excel template, keeping its formatting, with optional totals and placeholders. |
| FR-4 | The Excel file is e-mailed to the recipients, with subject and body built from placeholders. |
| FR-5 | Reports run automatically on their cron schedule. |
| FR-6 | Every run is recorded with time, trigger, rows, recipients, status and error. |
| FR-7 | A web interface lists reports and next runs, previews data, downloads the Excel and sends a report now. |
| FR-8 | The command line can list, preview, run (also for another date) and schedule reports. |

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Security:** passwords only in environment variables; parameters bound by the driver; only single SELECT statements. |
| NFR-2 | **Reliability:** temporary database or mail errors are retried; a failure never stops the scheduler. |
| NFR-3 | **Early errors:** every report file is checked when loaded (fields, SQL, parameters, schedule, template). |
| NFR-4 | **Testable:** e-mails are tested with Mailpit, a fake mail server, in Docker and in CI. |
| NFR-5 | **Portable:** `docker compose up` runs scheduler, web interface and Mailpit. |

## 7. Acceptance criteria

- [x] The three sample reports are delivered with the right period, totals and attachment.
- [x] "Every Monday at 8:00" (`0 8 * * 1`) runs on Mondays (standard cron day numbers).
- [x] A malicious parameter value cannot change the SQL.
- [x] A temporary mail server failure is retried; a permanent one is recorded as failed.
- [x] An invalid report file is rejected with a clear message.
- [x] `docker compose up` delivers the sample reports to Mailpit.
- [ ] CI is green on GitHub, including the end-to-end e-mail test.
