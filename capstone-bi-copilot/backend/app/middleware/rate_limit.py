import time
from collections import defaultdict,deque
from fastapi import HTTPException,Request
from app.core.config import get_settings
_hits=defaultdict(deque)
async def rate_limit(request:Request):
    key=request.client.host if request.client else "unknown"; now=time.time(); q=_hits[key]
    while q and q[0]<=now-60:q.popleft()
    if len(q)>=get_settings().rate_limit_per_minute: raise HTTPException(429,"Rate limit exceeded")
    q.append(now)
