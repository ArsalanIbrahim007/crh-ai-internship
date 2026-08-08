"""Read-only SQL access to the business database.

The model writes the SQL, which means untrusted text reaches the database on every query.
Three layers of containment, in order of how much I trust them:

1. The connection is opened read-only at the SQLite level (mode=ro). Even a perfectly
   formed DROP TABLE fails here. This is the layer that actually matters - it does not
   depend on me anticipating what the model might write.
2. Only SELECT and WITH statements are accepted, and only one statement per call. This
   catches obvious misuse early and produces a clearer error than a driver exception.
3. Results are capped and queries are interrupted after a deadline, so a careless join
   cannot hang the app or return a million rows into the model's context.

Layer 1 is the security boundary. Layers 2 and 3 are about failing usefully.
"""

import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "business.db"

MAX_ROWS = 200          # more than this is not useful to a language model
TIMEOUT_SECONDS = 5.0

# A statement must start with one of these. Anything else is rejected before execution.
ALLOWED_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)

# Cheap check for a second statement. Trailing semicolons are fine.
MULTIPLE_STATEMENTS = re.compile(r";\s*\S")


@dataclass
class SQLResult:
    ok: bool
    sql: str
    columns: list[str] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    error: str = ""
    seconds: float = 0.0

    def to_text(self, max_render: int = 30) -> str:
        """Compact rendering for the model. Wide tables waste context, so this stays terse."""
        if not self.ok:
            return f"SQL ERROR: {self.error}"
        if not self.rows:
            return "Query ran successfully but returned no rows."

        lines = [" | ".join(self.columns)]
        for row in self.rows[:max_render]:
            lines.append(" | ".join("" if v is None else str(v) for v in row))

        if len(self.rows) > max_render:
            lines.append(f"... {len(self.rows) - max_render} more rows not shown")
        if self.truncated:
            lines.append(f"(result capped at {MAX_ROWS} rows)")
        return "\n".join(lines)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"{DB_PATH} not found. Build it first with: python data/seed_db.py"
        )
    # mode=ro is the real protection. Writes fail at the driver, not at my regex.
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def run_sql(query: str) -> SQLResult:
    """Run one read-only SELECT and return the rows."""
    query = (query or "").strip()

    if not query:
        return SQLResult(ok=False, sql=query, error="Empty query.")

    if not ALLOWED_START.match(query):
        return SQLResult(
            ok=False, sql=query,
            error="Only SELECT and WITH statements are allowed. "
                  "This database is read-only.",
        )

    if MULTIPLE_STATEMENTS.search(query):
        return SQLResult(
            ok=False, sql=query,
            error="Only one statement per call. Remove anything after the semicolon.",
        )

    started = time.perf_counter()
    deadline = started + TIMEOUT_SECONDS

    try:
        conn = _connect()
        # Called every N bytecode instructions; returning non-zero aborts the query.
        conn.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 2000)

        cursor = conn.execute(query)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchmany(MAX_ROWS + 1)

        truncated = len(rows) > MAX_ROWS
        rows = rows[:MAX_ROWS]
        conn.close()

        return SQLResult(
            ok=True, sql=query, columns=columns, rows=rows,
            row_count=len(rows), truncated=truncated,
            seconds=round(time.perf_counter() - started, 3),
        )

    except sqlite3.OperationalError as e:
        msg = str(e)
        if "interrupted" in msg.lower():
            msg = f"Query took longer than {TIMEOUT_SECONDS}s and was cancelled."
        return SQLResult(ok=False, sql=query, error=msg,
                         seconds=round(time.perf_counter() - started, 3))
    except sqlite3.Error as e:
        return SQLResult(ok=False, sql=query, error=f"{type(e).__name__}: {e}",
                         seconds=round(time.perf_counter() - started, 3))


def get_schema() -> str:
    """The schema, formatted for a system prompt.

    The model cannot write correct SQL without knowing the tables, and guessing produces
    confident nonsense. This goes into the system prompt once per conversation.
    """
    conn = _connect()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )]

    parts = []
    for t in tables:
        cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
        col_text = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        parts.append(f"{t}({col_text})")

    conn.close()
    return "\n".join(parts)


def get_schema_notes() -> str:
    """Things the schema alone does not convey.

    Without these the model writes plausible SQL that is quietly wrong - the usual case is
    using products.unit_price for revenue instead of the negotiated price on the line item.
    """
    return (
        "Notes:\n"
        "- Revenue must use order_items.unit_price (the negotiated price at time of sale), "
        "NOT products.unit_price (the list price).\n"
        "- Revenue for a line item is quantity * unit_price.\n"
        "- Only orders with status='completed' count toward revenue. "
        "Statuses are completed, pending, cancelled.\n"
        "- Dates are stored as TEXT in YYYY-MM-DD format. Use strftime for grouping.\n"
        "- Data covers 2024-08-01 to 2026-07-31.\n"
        "- customers.segment is one of Enterprise, SMB, Startup."
    )


if __name__ == "__main__":
    print("SCHEMA")
    print("-" * 70)
    print(get_schema())
    print()
    print(get_schema_notes())

    print("\n\nTESTS")
    print("-" * 70)

    checks = [
        ("valid aggregate", "SELECT COUNT(*) AS n FROM customers"),
        ("join with revenue", """
            SELECT r.name AS region, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue
            FROM order_items oi
            JOIN orders o ON o.order_id = oi.order_id
            JOIN customers c ON c.customer_id = o.customer_id
            JOIN regions r ON r.region_id = c.region_id
            WHERE o.status = 'completed'
            GROUP BY r.name ORDER BY revenue DESC
        """),
        ("blocked: write", "DELETE FROM customers"),
        ("blocked: drop", "DROP TABLE orders"),
        ("blocked: stacked", "SELECT 1; DROP TABLE orders"),
        ("blocked: update", "UPDATE customers SET name='x'"),
        ("bad column", "SELECT nonexistent FROM customers"),
    ]

    for label, sql in checks:
        res = run_sql(sql)
        status = "OK  " if res.ok else "FAIL"
        detail = f"{res.row_count} rows" if res.ok else res.error[:60]
        print(f"  [{status}] {label:<20} {detail}")

    print("\n\nSAMPLE OUTPUT")
    print("-" * 70)
    print(run_sql(checks[1][1]).to_text())

    # Even if every regex above were removed, this must still fail.
    print("\n\nREAD-ONLY CONNECTION HOLDS WITHOUT THE REGEX")
    print("-" * 70)
    try:
        c = _connect()
        c.execute("DELETE FROM customers")
        print("  PROBLEM: the write succeeded")
    except sqlite3.OperationalError as e:
        print(f"  blocked at driver level: {e}")
