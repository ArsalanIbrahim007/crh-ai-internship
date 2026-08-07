"""Builds the SQLite database the copilot queries.

Deterministic - the same seed produces the same data every run, so numbers quoted in
the README and notebooks stay correct. Run this once before starting the app:

    python data/seed_db.py
"""

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "business.db"
random.seed(42)

SCHEMA = """
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS regions;

CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL
);

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    region_id   INTEGER NOT NULL REFERENCES regions(region_id),
    hired_on    DATE NOT NULL
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    segment     TEXT NOT NULL,          -- Enterprise, SMB, Startup
    region_id   INTEGER NOT NULL REFERENCES regions(region_id),
    signed_on   DATE NOT NULL,
    email       TEXT NOT NULL
);

CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit_price  REAL NOT NULL
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
    order_date  DATE NOT NULL,
    status      TEXT NOT NULL           -- completed, pending, cancelled
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL         -- price at time of sale
);

CREATE INDEX idx_orders_date ON orders(order_date);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_items_order ON order_items(order_id);
"""

REGIONS = [
    (1, "South Asia", "Pakistan"),
    (2, "Middle East", "UAE"),
    (3, "Western Europe", "Germany"),
    (4, "North America", "United States"),
    (5, "Southeast Asia", "Singapore"),
]

PRODUCTS = [
    ("Analytics Platform - Standard", "Software", 4800.0),
    ("Analytics Platform - Enterprise", "Software", 18500.0),
    ("Data Warehouse Connector", "Software", 2400.0),
    ("Realtime Streaming Add-on", "Software", 6200.0),
    ("Implementation Services", "Services", 12000.0),
    ("Priority Support - Annual", "Support", 9500.0),
    ("Standard Support - Annual", "Support", 3200.0),
    ("Training Workshop", "Services", 5500.0),
    ("Custom Dashboard Build", "Services", 7800.0),
    ("API Gateway Licence", "Software", 3900.0),
]

FIRST = ["Ayesha", "Bilal", "Fatima", "Hassan", "Zara", "Omar", "Nadia", "Imran",
         "Lena", "Marcus", "Priya", "Daniel", "Sofia", "Karim", "Elena", "Yusuf"]
LAST = ["Khan", "Ahmed", "Malik", "Raza", "Weber", "Schmidt", "Chen", "Patel",
        "Rodriguez", "Okafor", "Tan", "Novak", "Haddad", "Larsen"]

COMPANY_A = ["Northwind", "Zenith", "Cobalt", "Meridian", "Vertex", "Lumen", "Arcadia",
             "Sable", "Halcyon", "Pinnacle", "Cascade", "Orion", "Solstice", "Bastion"]
COMPANY_B = ["Systems", "Logistics", "Health", "Financial", "Retail", "Energy",
             "Media", "Manufacturing", "Analytics", "Networks"]

SEGMENTS = ["Enterprise", "SMB", "Startup"]
ROLES = ["Account Executive", "Senior Account Executive", "Regional Manager"]


def person():
    return f"{random.choice(FIRST)} {random.choice(LAST)}"


def company():
    return f"{random.choice(COMPANY_A)} {random.choice(COMPANY_B)}"


def build():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    conn.executemany("INSERT INTO regions VALUES (?,?,?)", REGIONS)

    # employees
    employees = []
    for i in range(1, 19):
        employees.append((
            i, person(), random.choice(ROLES), random.randint(1, 5),
            (date(2022, 1, 1) + timedelta(days=random.randint(0, 900))).isoformat(),
        ))
    conn.executemany("INSERT INTO employees VALUES (?,?,?,?,?)", employees)

    # customers
    used = set()
    customers = []
    for i in range(1, 121):
        name = company()
        while name in used:
            name = company()
        used.add(name)
        slug = name.lower().replace(" ", "")
        customers.append((
            i, name,
            random.choices(SEGMENTS, weights=[3, 5, 2])[0],
            random.randint(1, 5),
            (date(2023, 1, 1) + timedelta(days=random.randint(0, 850))).isoformat(),
            f"contact@{slug}.com",
        ))
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?)", customers)

    # products
    products = [(i + 1, n, c, p) for i, (n, c, p) in enumerate(PRODUCTS)]
    conn.executemany("INSERT INTO products VALUES (?,?,?,?)", products)

    # orders spread over two years, with a seasonal lift in Q4
    orders, items = [], []
    order_id, item_id = 1, 1
    start = date(2024, 8, 1)

    for day_offset in range((date(2026, 7, 31) - start).days + 1):
        d = start + timedelta(days=day_offset)
        base = 2 if d.month in (10, 11, 12) else 1
        for _ in range(random.randint(0, base + 1)):
            status = random.choices(
                ["completed", "pending", "cancelled"], weights=[85, 10, 5]
            )[0]
            orders.append((order_id, random.randint(1, 120), random.randint(1, 18),
                           d.isoformat(), status))

            for _ in range(random.randint(1, 3)):
                pid = random.randint(1, len(PRODUCTS))
                base_price = PRODUCTS[pid - 1][2]
                # small negotiated discount
                price = round(base_price * random.uniform(0.88, 1.0), 2)
                items.append((item_id, order_id, pid, random.randint(1, 5), price))
                item_id += 1
            order_id += 1

    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", orders)
    conn.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)
    conn.commit()

    # summary
    print(f"database written to {DB_PATH}")
    for tbl in ["regions", "employees", "customers", "products", "orders", "order_items"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:<14} {n:>6,} rows")

    revenue = conn.execute("""
        SELECT ROUND(SUM(oi.quantity * oi.unit_price), 2)
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.status = 'completed'
    """).fetchone()[0]
    print(f"\n  total completed revenue: ${revenue:,.2f}")

    conn.close()


if __name__ == "__main__":
    build()
