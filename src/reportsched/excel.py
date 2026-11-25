"""Fill a predefined Excel template with the query result.

The template is a normal .xlsx file prepared in Excel:
- a header row with the column titles (row `header_row`);
- the row just below it formatted as the data should look (number formats, fonts, borders);
- optional placeholders anywhere, such as {{ title }} or {{ start_date }}.

The program writes one row per record, copying the format of that first data row, and adds
a total row with SUM formulas if requested. Everything else in the template is kept.
"""

from __future__ import annotations

import math
from copy import copy
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from reportsched.params import render


class TemplateError(ValueError):
    """The template does not match the query result."""


def _plain(value):
    """pandas / numpy values -> plain Python values that openpyxl can write."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):  # numpy number
        return value.item()
    return value


def _replace_placeholders(workbook, values: dict[str, object]) -> None:
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and "{{" in cell.value:
                    cell.value = render(cell.value, values)


def fill_template(
    template: Path,
    data: pd.DataFrame,
    output: Path,
    *,
    header_row: int = 5,
    sheet: str | None = None,
    total_columns: list[str] | None = None,
    placeholders: dict[str, object] | None = None,
) -> Path:
    workbook = load_workbook(template)
    ws = workbook[sheet] if sheet else workbook.active

    headers = [cell.value for cell in ws[header_row] if cell.value is not None]
    if len(headers) != len(data.columns):
        raise TemplateError(
            f"{template.name} has {len(headers)} columns ({', '.join(map(str, headers))}) "
            f"but the query returns {len(data.columns)} ({', '.join(data.columns)})"
        )

    first = header_row + 1
    styles = [copy(ws.cell(first, col)._style) for col in range(1, len(headers) + 1)]

    if data.empty:
        ws.cell(first, 1, "No data for this period")
    for offset, record in enumerate(data.itertuples(index=False)):
        for col, value in enumerate(record, start=1):
            cell = ws.cell(first + offset, col, _plain(value))
            cell._style = copy(styles[col - 1])

    last = first + max(len(data), 1) - 1
    if total_columns and not data.empty:
        total_row = last + 1
        label = ws.cell(total_row, 1, "Total")
        label.font = Font(bold=True)
        for name in total_columns:
            if name not in data.columns:
                raise TemplateError(f"total column '{name}' is not in the query result")
            col = list(data.columns).index(name) + 1
            letter = get_column_letter(col)
            cell = ws.cell(total_row, col, f"=SUM({letter}{first}:{letter}{last})")
            cell._style = copy(styles[col - 1])
            cell.font = Font(bold=True)

    _replace_placeholders(workbook, {"rows": len(data), **(placeholders or {})})
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    return output
