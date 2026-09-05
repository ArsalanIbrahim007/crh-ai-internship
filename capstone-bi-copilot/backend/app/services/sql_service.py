import re
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
FORBIDDEN=re.compile(r"\b(insert|update|delete|drop|alter|truncate|create|attach|detach|pragma|replace|vacuum|grant|revoke)\b",re.I)
class SQLService:
    def validate_read_only(self,sql_query:str)->str:
        q=sql_query.strip().rstrip(";")
        if ";" in q or not q.lower().startswith("select") or FORBIDDEN.search(q): raise ValueError("Only one read-only SELECT statement is allowed")
        return q
    def execute(self,db:Session,sql_query:str)->list[dict]:
        q=self.validate_read_only(sql_query); return [dict(r._mapping) for r in db.execute(text(q))]
    def schema_summary(self,db:Session)->str:
        i=inspect(db.bind); out=[]
        for t in i.get_table_names():
            if t in {"audit_logs","users"}: continue
            out.append(f"{t}({', '.join(c['name'] for c in i.get_columns(t))})")
        return "; ".join(out)
sql_service=SQLService()
