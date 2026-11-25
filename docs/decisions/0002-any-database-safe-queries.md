# ADR 0002 — Any database through SQLAlchemy, with safe read-only queries

**Status:** accepted

## Context
Company data lives in different databases (SQL Server, PostgreSQL, MySQL...). A report scheduler holds database credentials and runs SQL automatically, so it must not become a security problem.

## Decision
- Connect through **SQLAlchemy** URLs, one per named connection in `config/connections.yml`; drivers are optional extras.
- User names and passwords are written as `${VARIABLE}` and read from the environment; a missing variable stops the program with its name.
- Parameters are **bound by the driver** (`:start_date`), never pasted into the SQL text, so a value cannot change the query.
- A report query must be a single `SELECT` or `WITH ... SELECT` statement.

## Consequences
- The same report code works on every supported database; the demo uses SQLite, which needs no driver.
- SQL injection through parameters is not possible; a test proves that a malicious value matches nothing.
- The SELECT check protects against mistakes, not against a malicious administrator: the database account used for reports should still have **read-only** permissions. This is stated in the README.
