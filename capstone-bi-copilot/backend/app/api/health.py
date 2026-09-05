from fastapi import APIRouter
router=APIRouter(tags=["health"])
@router.get("/health")
def health(): return {"status":"ok","service":"ai-business-intelligence-copilot"}
