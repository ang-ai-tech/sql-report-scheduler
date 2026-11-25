"""Web interface: see the reports, preview the data, download the Excel, send it now.

Run: streamlit run app.py
The scheduled sending is done by `reports schedule`, a separate process.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from reportsched import history
from reportsched.config import ConfigError, load_connections, load_reports
from reportsched.params import display
from reportsched.runner import build_excel, placeholder_values, preview, run_report
from reportsched.scheduler import next_runs

st.set_page_config(page_title="Report scheduler", layout="wide")
st.title("Report scheduler")
st.caption("SQL query → Excel template → e-mail, on a schedule.")

try:
    reports = load_reports()
    connections = load_connections()
except ConfigError as exc:
    st.error(f"Configuration error: {exc}")
    st.stop()

if not reports:
    st.info("No reports found in config/reports/.")
    st.stop()

connection = history.connect()
runs = pd.DataFrame(history.list_runs(connection, limit=500))


def last_status(name: str) -> str:
    if runs.empty or name not in set(runs["report"]):
        return "never run"
    last = runs[runs["report"] == name].iloc[0]
    return f"{'✅' if last['status'] == 'success' else '❌'} {last['started_at']}"


def describe(report) -> str:
    upcoming = next_runs(report, count=1)
    return f"{upcoming[0]:%a %d/%m/%Y %H:%M}" if upcoming else "manual only"


overview_tab, report_tab, history_tab = st.tabs(["Reports", "Open a report", "History"])

# ---- Overview ---------------------------------------------------------------------------
with overview_tab:
    st.dataframe(
        pd.DataFrame(
            {
                "report": [r.name for r in reports.values()],
                "title": [r.title for r in reports.values()],
                "schedule (cron)": [r.schedule or "-" for r in reports.values()],
                "next run": [describe(r) for r in reports.values()],
                "recipients": [
                    ", ".join(r.email.to + r.email.cc) if r.email else "-" for r in reports.values()
                ],
                "last run": [last_status(r.name) for r in reports.values()],
            }
        ),
        hide_index=True,
        width="stretch",
    )

# ---- One report -------------------------------------------------------------------------
with report_tab:
    name = st.selectbox("Report", list(reports), format_func=lambda n: f"{reports[n].title} ({n})")
    report = reports[name]
    left, right = st.columns([2, 1])
    with left:
        st.write(report.description)
        with st.expander("SQL query"):
            st.code(report.query, language="sql")
    with right:
        run_date = st.date_input(
            "Run as if today were", date.today(), help="Relative dates are computed from this day"
        )
        upcoming = next_runs(report)
        if upcoming:
            st.write("Next runs: " + ", ".join(f"{m:%a %d/%m %H:%M}" for m in upcoming))

    params = {
        key: value
        for key, value in placeholder_values(report, run_date).items()
        if key in report.params
    }
    if params:
        st.write("Parameters: " + ", ".join(f"**{k}** = {display(v)}" for k, v in params.items()))

    try:
        data = preview(report, connections, run_date)
    except Exception as exc:  # database not reachable, SQL error...
        st.error(f"The query failed: {exc}")
        st.stop()
    st.write(f"{len(data)} rows")
    st.dataframe(data.head(200), hide_index=True, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        path, _ = build_excel(report, connections, run_date)
        st.download_button(
            "Download the Excel file",
            path.read_bytes(),
            file_name=path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with col2:
        recipients = ", ".join(report.email.to + report.email.cc) if report.email else ""
        if report.email and st.button(f"Send now to {recipients}", type="primary"):
            with st.spinner("Sending..."):
                result = run_report(report, connections, run_date=run_date, retries=0)
            if result.status == "success":
                st.success(f"Sent: {result.rows} rows to {', '.join(result.emailed_to)}")
            else:
                st.error(f"Failed: {result.error}")

# ---- History ----------------------------------------------------------------------------
with history_tab:
    fresh = pd.DataFrame(history.list_runs(connection, limit=200))
    if fresh.empty:
        st.info("No runs yet.")
    else:
        st.dataframe(
            fresh[
                [
                    "started_at",
                    "report",
                    "trigger",
                    "status",
                    "rows",
                    "attempts",
                    "emailed_to",
                    "error_message",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
