from uuid import uuid4
from fastapi import Request
async def request_context(request:Request,call_next):
    request.state.request_id=request.headers.get("x-request-id",f"req_{uuid4().hex}"); response=await call_next(request); response.headers["x-request-id"]=request.state.request_id; return response
