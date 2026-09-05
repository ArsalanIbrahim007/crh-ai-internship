from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from app.services.voice_service import voice_service

router=APIRouter(prefix="/voice",tags=["voice"])

class SynthesisRequest(BaseModel): text:str

@router.post("/transcribe")
async def transcribe(audio:UploadFile=File(...),mime_type:str=Form("audio/webm")):
    return {"text":await voice_service.transcribe(await audio.read(),mime_type)}

@router.post("/synthesize")
async def synthesize(payload:SynthesisRequest):
    return Response(await voice_service.synthesize(payload.text),media_type="audio/wav")
