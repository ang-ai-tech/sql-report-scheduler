"""Demo data: a small SQLite database of a fictional online store, and the Excel templates.

Order dates are relative to today, so "last week" and "last month" always contain data.
"""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

DEMO_DB = Path("data/demo_shop.db")
TEMPLATES = Path("templates")

COUNTRIES = {"IT": 0.30, "DE": 0.25, "FR": 0.20, "ES": 0.15, "NL": 0.10}
PRODUCTS = [
    ("Ceramic mug set", "Kitchen", 24.90),
    ("Chef knife", "Kitchen", 59.00),
    ("Glass storage jars", "Kitchen", 29.90),
    ("Desk lamp", "Lighting", 49.00),
    ("Floor lamp", "Lighting", 129.00),
    ("LED string lights", "Lighting", 14.90),
    ("Notebook A5", "Office", 9.90),
    ("Monitor stand", "Office", 45.00),
    ("Fountain pen", "Office", 34.00),
    ("Linen cushion cover", "Textiles", 18.90),
    ("Wool throw blanket", "Textiles", 69.00),
    ("Scented candle", "Decor", 16.90),
    ("Wall clock", "Decor", 42.00),
    ("Wall mirror", "Decor", 119.00),
]
SCHEMA = """
create table customers (customer_id integer primary key, email text, country_code text);
create table products (product_id integer primary key, product_name text, category text,
                       unit_price real);
create table orders (order_id integer primary key, customer_id integer references customers,
                     order_date date, status text, channel text);
create table order_items (order_id integer references orders, product_id integer references
                          products, quantity integer, unit_price real);
"""


def create_demo_db(path: Path = DEMO_DB, today: date | None = None, seed: int = 42) -> Path:
    """About 400 days of orders up to yesterday. Replaces an existing demo database."""
    today = today or date.today()
    rng = random.Random(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        countries = list(COUNTRIES)
        db.executemany(
            "insert into customers values (?, ?, ?)",
            [
                (n, f"user{n:05d}@example.com", rng.choices(countries, COUNTRIES.values())[0])
                for n in range(1, 1201)
            ],
        )
        db.executemany(
            "insert into products values (?, ?, ?, ?)",
            [(n, *product) for n, product in enumerate(PRODUCTS, start=1)],
        )
        order_id = 0
        for days_ago in range(400, 0, -1):
            day = today - timedelta(days=days_ago)
            for _ in range(rng.randint(8, 20) + (6 if day.weekday() >= 5 else 0)):
                order_id += 1
                status = rng.choices(["completed", "cancelled", "refunded"], [90, 6, 4])[0]
                channel = rng.choices(["web", "app"], [70, 30])[0]
                db.execute(
                    "insert into orders values (?, ?, ?, ?, ?)",
                    (order_id, rng.randint(1, 1200), day.isoformat(), status, channel),
                )
                for product_id in rng.sample(range(1, len(PRODUCTS) + 1), rng.randint(1, 3)):
                    price = PRODUCTS[product_id - 1][2]
                    quantity = rng.choices([1, 2, 3], [80, 15, 5])[0]
                    db.execute(
                        "insert into order_items values (?, ?, ?, ?)",
                        (order_id, product_id, quantity, price),
                    )
    return path


# ---- Excel templates --------------------------------------------------------------------

HEADER_FILL = PatternFill("solid", start_color="1F4E79")
THIN = Side(style="thin", color="BFBFBF")
EURO = '#,##0.00 "€"'


def _template(path: Path, sheet: str, columns: list[tuple[str, int, str | None]]) -> None:
    """Title block in rows 1-3, headers in row 5, formatted first data row in row 6."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws["A1"] = "{{ title }}"
    ws["A1"].font = Font(size=16, bold=True, color="1F4E79")
    ws["A2"] = "Period: {{ start_date }} - {{ end_date }}"
    ws["A3"] = "Generated on {{ generated_at }} · {{ rows }} rows"
    ws["A3"].font = Font(italic=True, color="7F7F7F")
    for col, (header, width, number_format) in enumerate(columns, start=1):
        head = ws.cell(5, col, header)
        head.font = Font(bold=True, color="FFFFFF")
        head.fill = HEADER_FILL
        head.alignment = Alignment(horizontal="center")
        data = ws.cell(6, col)
        data.border = Border(bottom=THIN)
        if number_format:
            data.number_format = number_format
        ws.column_dimensions[head.column_letter].width = width
    ws.freeze_panes = "A6"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def create_templates(directory: Path = TEMPLATES) -> list[Path]:
    specs = {
        "weekly_sales.xlsx": (
            "Sales",
            [
                ("Category", 18, None),
                ("Orders", 10, "#,##0"),
                ("Units", 10, "#,##0"),
                ("Revenue", 16, EURO),
            ],
        ),
        "monthly_countries.xlsx": (
            "Countries",
            [
                ("Country", 10, None),
                ("Customers", 12, "#,##0"),
                ("Orders", 10, "#,##0"),
                ("Revenue", 16, EURO),
                ("Average order", 16, EURO),
            ],
        ),
        "cancelled_orders.xlsx": (
            "Orders",
            [
                ("Order", 10, "0"),
                ("Date", 12, "DD/MM/YYYY"),
                ("Customer e-mail", 28, None),
                ("Country", 10, None),
                ("Status", 12, None),
                ("Amount", 14, EURO),
            ],
        ),
    }
    paths = []
    for name, (sheet, columns) in specs.items():
        _template(directory / name, sheet, columns)
        paths.append(directory / name)
    return paths
