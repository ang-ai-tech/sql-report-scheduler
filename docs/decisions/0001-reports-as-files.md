# ADR 0001 — One YAML file per report, templates made in Excel

**Status:** accepted

## Context
Reports change often: a new recipient, a different period, an extra column. If every change needs a developer, the tool does not save much time. Business users also care about the look of their Excel file, which is hard to describe in code.

## Decision
- Each report is a YAML file in `config/reports/`: title, connection, query, parameters, template, totals, recipients, schedule.
- The layout is a real `.xlsx` template prepared in Excel. The program only fills data, totals and placeholders.
- Files are checked when loaded, so a mistake is reported with the report name before anything is sent.

## Consequences
- Adding a report means adding a file and, if needed, a template: no code change, and the change is visible in Git history.
- Formatting, column widths, logos or extra sheets stay exactly as designed in Excel.
- Users who cannot edit YAML files still need someone to do it; an editor in the web interface is a possible next step.
- The data area of the template is fixed (one header row, data below); more complex layouts would need more options.
