from fastapi import APIRouter,Response
from app.services.report_service import report_service
router=APIRouter(prefix="/reports",tags=["reports"])
@router.post("/export/csv")
def csv_export(rows:list[dict]): return Response(report_service.csv_bytes(rows),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=report.csv"})
@router.post("/export/xlsx")
def xlsx_export(rows:list[dict]): return Response(report_service.xlsx_bytes(rows),media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",headers={"Content-Disposition":"attachment; filename=report.xlsx"})
@router.post("/export/pdf")
def pdf_export(title:str="Executive Report",summary:str=""): return Response(report_service.pdf_bytes(title,summary),media_type="application/pdf",headers={"Content-Disposition":"attachment; filename=report.pdf"})
