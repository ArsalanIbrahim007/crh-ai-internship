from __future__ import annotations
import csv,io
from pathlib import Path
from uuid import uuid4
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook
class ReportService:
    def csv_bytes(self,rows:list[dict])->bytes:
        if not rows:return b""
        s=io.StringIO(); w=csv.DictWriter(s,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows); return s.getvalue().encode()
    def xlsx_bytes(self,rows:list[dict])->bytes:
        wb=Workbook(); ws=wb.active; ws.title="Report"
        if rows: ws.append(list(rows[0])); [ws.append([r.get(k) for k in rows[0]]) for r in rows]
        b=io.BytesIO(); wb.save(b); return b.getvalue()
    def pdf_bytes(self,title:str,summary:str)->bytes:
        b=io.BytesIO(); c=canvas.Canvas(b,pagesize=A4); c.setTitle(title); c.drawString(50,800,title); y=770
        for line in summary.splitlines() or [summary]: c.drawString(50,y,line[:100]); y-=18
        c.save(); return b.getvalue()
report_service=ReportService()
