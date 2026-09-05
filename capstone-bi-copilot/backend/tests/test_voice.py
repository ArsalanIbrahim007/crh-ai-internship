from app.services.voice_service import voice_service
import asyncio

def test_voice_routes_use_replaceable_providers(client):
    class STT:
        async def transcribe(self,audio_bytes,mime_type):
            assert audio_bytes==b"voice" and mime_type=="audio/webm"
            return "show last month's sales"
    class TTS:
        async def synthesize(self,text):
            assert text=="Sales increased."
            return b"RIFFvoice"
    previous=voice_service.stt,voice_service.tts
    voice_service.stt,voice_service.tts=STT(),TTS()
    try:
        transcription=client.post('/api/voice/transcribe',files={'audio':('recording.webm',b'voice','audio/webm')},data={'mime_type':'audio/webm'})
        assert transcription.status_code==200 and transcription.json()['text']=="show last month's sales"
        speech=client.post('/api/voice/synthesize',json={'text':'Sales increased.'})
        assert speech.status_code==200 and speech.content==b"RIFFvoice" and speech.headers['content-type']=='audio/wav'
    finally: voice_service.stt,voice_service.tts=previous

def test_gemini_stt_uses_header_working_model_and_rest_audio_shape(monkeypatch):
    from app.core.config import get_settings
    from app.services import voice_service as module
    captured={}
    settings=get_settings(); previous=(settings.gemini_api_key,settings.gemini_model,settings.voice_stt_model)
    settings.gemini_api_key="secret-key"; settings.gemini_model="gemini-working"; settings.voice_stt_model=""
    class Response:
        is_error=False; status_code=200
        def json(self): return {"candidates":[{"content":{"parts":[{"text":"hello"}]}}]}
    class Client:
        def __init__(self,*args,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def post(self,url,**kwargs): captured.update(url=url,**kwargs); return Response()
    monkeypatch.setattr(module.httpx,"AsyncClient",Client)
    try:
        assert asyncio.run(module.GeminiSpeechProvider().transcribe(b"audio","audio/webm"))=="hello"
        assert captured["url"].endswith("models/gemini-working:generateContent") and "key=" not in captured["url"]
        assert captured["headers"]=={"x-goog-api-key":"secret-key"}
        inline=captured["json"]["contents"][0]["parts"][1]["inlineData"]
        assert inline["mimeType"]=="audio/webm" and inline["data"]
    finally: settings.gemini_api_key,settings.gemini_model,settings.voice_stt_model=previous
