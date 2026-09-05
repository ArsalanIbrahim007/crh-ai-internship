from __future__ import annotations

import json
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.contracts import KPI, ChartSpec
from app.services.llm_service import llm_service
from app.services.sql_service import sql_service


class AnalyticsService:
    async def answer_question(self, db: Session, question: str) -> tuple[list[KPI], ChartSpec, list[str], list[str]]:
        try:
            schema = sql_service.schema_summary(db)
            sql_query = await self._generate_sql(question, schema)
            validated_sql = sql_service.validate_read_only(sql_query)
            rows = sql_service.execute(db, validated_sql)
            if not rows:
                return self._fallback_overview(db)
            kpis = self._derive_kpis(rows)
            chart = self._derive_chart(rows, question)
            try:
                insights = await self._generate_insights(question, rows)
            except Exception:
                insights = [f"Retrieved {len(rows)} records matching your query."]
            recommendations = self._derive_recommendations(rows)
            return kpis, chart, insights, recommendations
        except Exception:
            return self._fallback_overview(db)

    def sales_overview(self, db: Session) -> tuple[list[KPI], ChartSpec, list[str], list[str]]:
        return self._fallback_overview(db)

    async def _generate_sql(self, question: str, schema: str) -> str:
        system_prompt = (
            "You translate a manager's business question into exactly one read-only "
            "SQLite SELECT statement. Rules:\n"
            "- Output ONLY the SQL statement, no explanation, no markdown fences.\n"
            "- Use only tables/columns from the schema provided.\n"
            "- Never use INSERT, UPDATE, DELETE, DROP, ALTER, or multiple statements.\n"
            "- Always include a LIMIT clause, maximum 200 rows.\n"
            f"Schema: {schema}"
        )
        raw_response = await llm_service.complete(system_prompt, question)
        return self._extract_sql(raw_response)

    def _extract_sql(self, raw_response: str) -> str:
        cleaned = re.sub(r"```(?:sql)?", "", raw_response, flags=re.I).strip()
        match = re.search(r"select\b.*", cleaned, re.I | re.S)
        return match.group(0).strip() if match else cleaned

    def _derive_kpis(self, rows: list[dict]) -> list[KPI]:
        numeric_columns = [
            key for key in rows[0]
            if key.lower() not in ("id", "pk") and all(isinstance(row.get(key), (int, float)) for row in rows)
        ]
        kpis = []
        for column in numeric_columns[:4]:
            total = sum(row[column] for row in rows)
            kpis.append(KPI(key=column, label=column.replace("_", " ").title(), value=round(total, 2)))
        return kpis or [KPI(key="count", label="Record Count", value=len(rows))]

    def _derive_chart(self, rows: list[dict], question: str) -> ChartSpec:
        columns = list(rows[0].keys())
        label_column = next((c for c in columns if not isinstance(rows[0][c], (int, float))), columns[0])
        value_columns = [c for c in columns if c != label_column and c.lower() not in ("id", "pk") and isinstance(rows[0][c], (int, float))]
        is_date = any(term in label_column.lower() for term in ["date", "month", "year", "time", "day"])
        is_trend = any(term in question.lower() for term in ["trend", "over time", "history", "revenue", "sales"])
        chart_type = "line" if (is_date or is_trend or len(rows) > 20) else "bar"
        return ChartSpec(
            type=chart_type,
            title=question[:80],
            x_key=label_column,
            y_keys=value_columns[:3],
            rows=rows,
        )

    async def _generate_insights(self, question: str, rows: list[dict]) -> list[str]:
        sample = json.dumps(rows[:20])
        system_prompt = (
            "You are a business analyst. Given a question and its query result rows, "
            "write 1-3 short factual insight sentences. Only state facts visible in the "
            "data. Never invent numbers not present in the rows. Return plain sentences, "
            "one per line, no bullets, no markdown."
        )
        response = await llm_service.complete(system_prompt, f"Question: {question}\nRows: {sample}")
        return [line.strip() for line in response.splitlines() if line.strip()][:3]

    def _derive_recommendations(self, rows: list[dict]) -> list[str]:
        return ["Review this result alongside prior periods before adjusting targets."]

    def _fallback_overview(self, db: Session) -> tuple[list[KPI], ChartSpec, list[str], list[str]]:
        rows = sql_service.execute(
            db,
            "SELECT sale_date, SUM(revenue) AS revenue, SUM(cost) AS cost, SUM(orders) AS orders "
            "FROM sales GROUP BY sale_date ORDER BY sale_date LIMIT 200",
        )
        total_revenue = sum(r["revenue"] for r in rows)
        total_cost = sum(r["cost"] for r in rows)
        margin = ((total_revenue - total_cost) / total_revenue * 100) if total_revenue else 0
        delta = (
            (rows[-1]["revenue"] - rows[0]["revenue"]) / rows[0]["revenue"] * 100
            if len(rows) > 1 and rows[0]["revenue"]
            else None
        )
        kpis = [
            KPI(key="revenue", label="Revenue", value=round(total_revenue, 2), unit="USD", delta=delta),
            KPI(key="gross_margin", label="Gross Margin", value=round(margin, 1), unit="%"),
        ]
        chart = ChartSpec(type="line", title="Revenue Trend", x_key="sale_date", y_keys=["revenue"], rows=rows)
        insights = [f"Total revenue is ${total_revenue:,.0f} with gross margin of {margin:.1f}%."]
        recommendations = ["Review performance by region and product before changing targets."]
        return kpis, chart, insights, recommendations


analytics_service = AnalyticsService()
