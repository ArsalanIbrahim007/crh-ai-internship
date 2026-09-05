from dataclasses import dataclass
@dataclass
class Alert: alert_id:str; title:str; severity:str; message:str
class AlertService:
    def evaluate(self,kpi_key:str,value:float,warning_below:float|None=None,critical_below:float|None=None)->list[Alert]:
        if critical_below is not None and value<critical_below:return [Alert(f"{kpi_key}-critical",f"{kpi_key} critical","critical",f"Current value: {value}")]
        if warning_below is not None and value<warning_below:return [Alert(f"{kpi_key}-warning",f"{kpi_key} below threshold","warning",f"Current value: {value}")]
        return []
alert_service=AlertService()
