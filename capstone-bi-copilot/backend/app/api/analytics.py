from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.alert_service import alert_service
from app.services.analytics_service import analytics_service
from app.services.briefing_service import briefing_service
from app.services.forecast_service import forecast_service

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    k, c, i, r = analytics_service.sales_overview(db)
    return {"kpis": [x.model_dump() for x in k], "chart_spec": c.model_dump(), "insights": i, "recommendations": r}

@router.post("/query")
async def query_analytics(question: str, db: Session = Depends(get_db)):
    k, c, i, r = await analytics_service.answer_question(db, question)
    return {"kpis": [x.model_dump() for x in k], "chart_spec": c.model_dump(), "insights": i, "recommendations": r}

@router.get("/alerts")
def alerts(db: Session = Depends(get_db)):
    k, _, _, _ = analytics_service.sales_overview(db)
    triggered = []
    for item in k:
        val = float(item.value) if isinstance(item.value, (int, float)) else 0.0
        if item.key == "revenue":
            triggered.extend(alert_service.evaluate(item.key, val, warning_below=100000.0, critical_below=50000.0))
        elif item.key == "gross_margin":
            triggered.extend(alert_service.evaluate(item.key, val, warning_below=20.0, critical_below=10.0))
    return [{"alert_id": a.alert_id, "title": a.title, "severity": a.severity, "message": a.message} for a in triggered]

@router.get("/briefing")
def briefing(db: Session = Depends(get_db)):
    k, _, i, _ = analytics_service.sales_overview(db)
    triggered = []
    for item in k:
        val = float(item.value) if isinstance(item.value, (int, float)) else 0.0
        if item.key == "revenue":
            triggered.extend(alert_service.evaluate(item.key, val, warning_below=100000.0, critical_below=50000.0))
        elif item.key == "gross_margin":
            triggered.extend(alert_service.evaluate(item.key, val, warning_below=20.0, critical_below=10.0))
    alert_dicts = [{"alert_id": a.alert_id, "title": a.title, "severity": a.severity, "message": a.message} for a in triggered]
    kpi_dicts = [x.model_dump() for x in k]
    return briefing_service.build(kpi_dicts, alert_dicts, meetings=[])

@router.post("/forecast")
def forecast(values: list[float], horizon: int = 3):
    return forecast_service.moving_average(values, horizon)
