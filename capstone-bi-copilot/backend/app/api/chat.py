from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.middleware.rate_limit import rate_limit
from app.schemas.contracts import ApprovalRequest,ChatRequest,ChatResponse,ConversationDetail,ConversationMessage,ConversationSummary,ToolCall
from app.agents.supervisor import supervisor
from app.core.security import get_optional_current_user
from app.db.models import User
from app.core.security import get_current_user
from app.db.models import Conversation,Message,ToolAction
from app.integrations.provider import IntegrationProvider,get_integration_provider
from fastapi import HTTPException
import json
from sqlalchemy import func
from app.core.config import get_settings
from app.agents.tool_registry import tool_registry
router=APIRouter(prefix="/chat",tags=["chat"])
@router.post("",response_model=ChatResponse,dependencies=[Depends(rate_limit)])
async def chat(payload:ChatRequest,db:Session=Depends(get_db),user:User|None=Depends(get_optional_current_user)):
    # Chat remains usable without login to preserve the current GitHub frontend behavior.
    return await supervisor.run(db,payload,user_id=user.id if user else None,user_role=user.role if user else "manager")

@router.get("/conversations",response_model=list[ConversationSummary])
async def conversations(db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    if get_settings().environment == "development":
        db.query(Conversation).filter(Conversation.user_id.is_(None)).update({Conversation.user_id:user.id},synchronize_session=False)
        db.commit()
    rows=(db.query(Conversation.id,Conversation.title,func.max(Message.created_at),func.count(Message.id))
          .join(Message,Message.conversation_id==Conversation.id)
          .filter(Conversation.user_id==user.id)
          .group_by(Conversation.id,Conversation.title)
          .order_by(func.max(Message.created_at).desc()).all())
    return [ConversationSummary(id=row[0],title=row[1],updated_at=row[2],message_count=row[3]) for row in rows]

@router.get("/conversations/{conversation_id}",response_model=ConversationDetail)
async def conversation(conversation_id:str,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    record=db.get(Conversation,conversation_id)
    if record and record.user_id is None and get_settings().environment == "development":
        record.user_id=user.id; db.commit()
    if not record or record.user_id != user.id:
        raise HTTPException(404,"Conversation not found")
    messages=(db.query(Message).filter_by(conversation_id=conversation_id)
              .order_by(Message.created_at.asc(),Message.id.asc()).all())
    return ConversationDetail(id=record.id,title=record.title,messages=[
        ConversationMessage(id=item.id,role=item.role,content=item.content,created_at=item.created_at) for item in messages])

@router.post("/{message_id}/approval",response_model=ToolCall)
async def decide_approval(message_id:str,payload:ApprovalRequest,db:Session=Depends(get_db),
                          user:User=Depends(get_current_user),adapter:IntegrationProvider=Depends(get_integration_provider)):
    action=db.query(ToolAction).filter_by(message_id=message_id).first()
    if not action:
        raise HTTPException(404,"Proposed action not found")
    if action.user_id is not None and action.user_id != user.id:
        raise HTTPException(403,"This proposed action belongs to another user")
    arguments=json.loads(action.arguments_json)
    if action.status != "proposed":
        return ToolCall(tool_name=action.tool_name,arguments=arguments,status=action.status,error=action.error)
    action.user_id=user.id
    if payload.decision == "cancel":
        action.status="cancelled"; db.commit()
        return ToolCall(tool_name=action.tool_name,arguments=arguments,status="cancelled")
    action.status="approved"; db.commit()
    try:
        registered=tool_registry.get(action.tool_name)
        if not registered or not registered.requires_approval:
            raise HTTPException(422,"This action is not registered for approval")
        if action.tool_name == "create_calendar_event":
            result=await adapter.create_calendar_event(user,arguments)
        elif action.tool_name == "send_email":
            result=await adapter.send_email(user,arguments)
        else:
            raise HTTPException(422,"This action does not have an execution handler")
        action.status="executed"; action.result_json=json.dumps(result); action.error=None; db.commit()
        return ToolCall(tool_name=action.tool_name,arguments=arguments,status="executed")
    except Exception as error:
        action.status="failed"
        action.error=error.detail if isinstance(error,HTTPException) else "The external action failed."
        db.commit()
        return ToolCall(tool_name=action.tool_name,arguments=arguments,status="failed",error=action.error)
