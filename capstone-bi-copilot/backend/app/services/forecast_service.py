class ForecastService:
    def moving_average(self,values:list[float],horizon:int=3,window:int=3)->dict:
        if horizon<1 or horizon>24: raise ValueError("horizon must be 1..24")
        hist=[float(x) for x in values]; points=[]
        for i in range(horizon):
            pred=sum(hist[-window:])/min(window,len(hist)) if hist else 0.0; hist.append(pred); points.append({"step":i+1,"value":round(pred,2)})
        return {"method":"moving_average","horizon":horizon,"points":points,"confidence":"baseline"}
forecast_service=ForecastService()
