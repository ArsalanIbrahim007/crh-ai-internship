class MockCalendarAdapter:
    async def list_events(self,start_iso:str,end_iso:str)->list[dict]: return []
    async def create_event(self,title:str,start_iso:str,end_iso:str,attendees:list[str])->dict: return {"event_id":"mock-event","title":title,"start":start_iso,"end":end_iso,"attendees":attendees}
calendar_adapter=MockCalendarAdapter()
