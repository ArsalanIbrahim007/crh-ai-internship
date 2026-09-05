import pytest
from app.services.analytics_service import analytics_service
from app.db.session import SessionLocal


def test_overview_endpoint(client):
    r = client.get("/api/analytics/overview")
    assert r.status_code == 200
    body = r.json()
    assert "kpis" in body and "chart_spec" in body and "insights" in body and "recommendations" in body
    keys = [k["key"] for k in body["kpis"]]
    assert "revenue" in keys and "gross_margin" in keys
    assert body["chart_spec"]["type"] == "line"
    assert body["chart_spec"]["x_key"] == "sale_date"


def test_query_endpoint_accepts_question_as_query_param(client):
    r = client.post("/api/analytics/query", params={"question": "What is total revenue?"})
    assert r.status_code == 200
    body = r.json()
    assert "kpis" in body and "chart_spec" in body


def test_query_endpoint_rejects_json_body(client):
    # Documented gotcha: `question` binds as a query param, not a JSON body.
    r = client.post("/api/analytics/query", json={"question": "What is total revenue?"})
    assert r.status_code == 422


def test_query_falls_back_when_llm_offline(client):
    # No GEMINI_API_KEY is set in the test environment, so llm_service.complete()
    # returns an offline stub that cannot be parsed as SQL, and answer_question()
    # should silently degrade to the same fixed overview query rather than error.
    r = client.post("/api/analytics/query", params={"question": "asdkjaslkdj nonsense"})
    assert r.status_code == 200
    body = r.json()
    keys = [k["key"] for k in body["kpis"]]
    assert "revenue" in keys and "gross_margin" in keys


def test_alerts_endpoint_returns_list(client):
    r = client.get("/api/analytics/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    for alert in r.json():
        assert set(alert.keys()) == {"alert_id", "title", "severity", "message"}


def test_briefing_endpoint_returns_expected_shape(client):
    r = client.get("/api/analytics/briefing")
    assert r.status_code == 200
    body = r.json()
    assert "kpis" in body and "alerts" in body and "meetings" in body
    assert body["meetings"] == []


def test_forecast_endpoint_accepts_json_array_body(client):
    # Unlike `question: str` on /query (a scalar, so it binds to a query param),
    # `values: list[float]` is a collection type, so FastAPI binds it as a JSON
    # array body by default.
    r = client.post("/api/analytics/forecast", json=[10.0, 20.0, 30.0])
    assert r.status_code == 200


def test_forecast_endpoint_rejects_repeated_query_params(client):
    r = client.post("/api/analytics/forecast", params=[("values", 10.0), ("values", 20.0), ("values", 30.0)])
    assert r.status_code == 422


@pytest.mark.anyio
async def test_answer_question_returns_fallback_shape_directly():
    db = SessionLocal()
    try:
        kpis, chart, insights, recommendations = await analytics_service.answer_question(db, "irrelevant question")
        assert any(k.key == "revenue" for k in kpis)
        assert chart.type == "line"
        assert isinstance(insights, list) and len(insights) >= 1
        assert isinstance(recommendations, list) and len(recommendations) >= 1
    finally:
        db.close()
