from fastapi import APIRouter,Depends,Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import User
from app.schemas.contracts import LoginRequest,AuthResponse,AuthUser
from app.core.security import verify_password,create_access_token,get_current_user
router=APIRouter(prefix="/auth",tags=["auth"])
@router.post("/login",response_model=AuthResponse)
def login(payload:LoginRequest,response:Response,db:Session=Depends(get_db)):
    u=db.query(User).filter(User.email==payload.email).first()
    if not u or not verify_password(payload.password,u.password_hash):
        from fastapi import HTTPException; raise HTTPException(401,"Invalid credentials")
    token=create_access_token(u); response.set_cookie("access_token",token,httponly=True,samesite="lax",secure=False,max_age=28800)
    return AuthResponse(access_token=token,user=AuthUser(id=u.id,email=u.email,role=u.role))
@router.get("/me",response_model=AuthUser)
def me(u:User=Depends(get_current_user)): return AuthUser(id=u.id,email=u.email,role=u.role)
@router.post("/logout")
def logout(response:Response): response.delete_cookie("access_token"); return {"ok":True}
