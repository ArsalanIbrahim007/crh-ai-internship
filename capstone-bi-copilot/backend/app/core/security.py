from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib, hmac, os
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.db.models import User

PBKDF2_ITERATIONS=210_000

def hash_password(password: str) -> str:
    salt=os.urandom(16)
    digest=hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex=encoded.split("$",3)
        if scheme!="pbkdf2_sha256": return False
        got=hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)).hex()
        return hmac.compare_digest(got,digest_hex)
    except Exception:
        return False

def create_access_token(user: User) -> str:
    s=get_settings(); now=datetime.now(timezone.utc)
    payload={"sub":str(user.id),"role":user.role,"email":user.email,"iat":now,"exp":now+timedelta(minutes=s.access_token_minutes)}
    return jwt.encode(payload,s.jwt_secret,algorithm=s.jwt_algorithm)

def _token_from_request(request: Request) -> str | None:
    auth=request.headers.get("authorization","")
    if auth.lower().startswith("bearer "): return auth.split(" ",1)[1].strip()
    return request.cookies.get("access_token")

def get_current_user(request: Request, db: Session=Depends(get_db)) -> User:
    token=_token_from_request(request)
    s=get_settings()
    if not token:
        # The current frontend has no sign-in screen. Local development can opt
        # into a seeded identity without weakening test or production auth.
        if s.environment == "development" and s.development_auth_email:
            user=db.query(User).filter(User.email==s.development_auth_email).first()
            if user and user.is_active:
                return user
            raise HTTPException(status_code=503,detail="Configured development user is unavailable")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Not authenticated")
    try: payload=jwt.decode(token,s.jwt_secret,algorithms=[s.jwt_algorithm]); uid=int(payload["sub"])
    except Exception: raise HTTPException(status_code=401,detail="Invalid or expired token")
    user=db.get(User,uid)
    if not user or not user.is_active: raise HTTPException(status_code=401,detail="User unavailable")
    return user

def get_optional_current_user(request: Request, db: Session=Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException as error:
        if error.status_code == 401:
            return None
        raise

def require_roles(*roles: str):
    def dep(user: User=Depends(get_current_user)) -> User:
        if user.role not in roles: raise HTTPException(status_code=403,detail="Insufficient role")
        return user
    return dep
