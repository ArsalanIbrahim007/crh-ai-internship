from datetime import date
class BriefingService:
    def build(self,kpis:list[dict],alerts:list[dict],meetings:list[dict])->dict:
        return {"date":date.today().isoformat(),"title":"Daily Executive Briefing","kpis":kpis,"alerts":alerts,"meetings":meetings}
briefing_service=BriefingService()
