class VisionService:
    async def analyze_image(self,image_bytes:bytes,question:str)->dict:
        return {"answer":"Vision provider is not configured. The upload was accepted for integration with a multimodal provider.","detected_text":"","question":question}
vision_service=VisionService()
