class MockEmailAdapter:
    async def search(self,query_text:str)->list[dict]: return []
    async def draft(self,recipient:str,subject:str,body:str)->dict: return {"draft_id":"mock-draft","recipient":recipient,"subject":subject,"body":body}
    async def send(self,draft_id:str)->dict: return {"status":"sent","draft_id":draft_id}
email_adapter=MockEmailAdapter()
