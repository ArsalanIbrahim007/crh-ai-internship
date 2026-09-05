from __future__ import annotations

import base64
import struct
from typing import Protocol
import httpx
from fastapi import HTTPException
from app.core.config import get_settings

class SpeechToTextProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str: ...

class TextToSpeechProvider(Protocol):
    async def synthesize(self, text: str) -> bytes: ...

class GeminiSpeechProvider:
    def __init__(self) -> None: self.settings = get_settings()

    def _key(self) -> str:
        if not self.settings.gemini_api_key: raise HTTPException(503, "Voice service is not configured.")
        return self.settings.gemini_api_key

    async def _generate(self, model: str, payload: dict) -> httpx.Response:
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=60) as client:
            return await client.post(url,headers={"x-goog-api-key":self._key()},json=payload)

    async def transcribe(self, audio_bytes: bytes, mime_type: str) -> str:
        if not audio_bytes: raise HTTPException(422, "The recording was empty.")
        model=self.settings.voice_stt_model or self.settings.gemini_model
        payload={"contents":[{"parts":[{"text":"Transcribe this speech exactly. Return only the spoken words."},
                  {"inlineData":{"mimeType":mime_type,"data":base64.b64encode(audio_bytes).decode()}}]}]}
        response=await self._generate(model,payload)
        if response.is_error:
            detail=_provider_error(response)
            raise HTTPException(502,f"Speech transcription failed using {model}: {detail}")
        try: text=response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError,IndexError,TypeError): text=""
        if not text: raise HTTPException(422,"No speech was detected.")
        return text

    async def synthesize(self, text: str) -> bytes:
        if not text.strip(): raise HTTPException(422,"There is no text to speak.")
        payload={"contents":[{"parts":[{"text":text[:1800]}]}],"generationConfig":{"responseModalities":["AUDIO"],
                 "speechConfig":{"voiceConfig":{"prebuiltVoiceConfig":{"voiceName":self.settings.voice_tts_voice}}}}}
        response=await self._generate(self.settings.voice_tts_model,payload)
        if response.is_error: raise HTTPException(502,f"Voice playback could not be generated: {_provider_error(response)}")
        try: pcm=base64.b64decode(response.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        except (KeyError,IndexError,TypeError,ValueError) as error: raise HTTPException(502,"Voice playback could not be generated.") from error
        return _pcm_to_wav(pcm)

def _pcm_to_wav(pcm: bytes, rate: int=24000) -> bytes:
    header=b"RIFF"+struct.pack("<I",36+len(pcm))+b"WAVEfmt "+struct.pack("<IHHIIHH",16,1,1,rate,rate*2,2,16)+b"data"+struct.pack("<I",len(pcm))
    return header+pcm

def _provider_error(response:httpx.Response)->str:
    try: message=response.json().get("error",{}).get("message")
    except ValueError: message=None
    return str(message or f"provider returned HTTP {response.status_code}")[:240]

class VoiceService:
    def __init__(self, stt: SpeechToTextProvider, tts: TextToSpeechProvider) -> None: self.stt,self.tts=stt,tts
    async def transcribe(self,audio_bytes:bytes,mime_type:str)->str: return await self.stt.transcribe(audio_bytes,mime_type)
    async def synthesize(self,text:str)->bytes: return await self.tts.synthesize(text)

_provider=GeminiSpeechProvider()
voice_service=VoiceService(_provider,_provider)
