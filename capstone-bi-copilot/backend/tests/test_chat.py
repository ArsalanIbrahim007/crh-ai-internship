def test_general_chat_contract(client):
    r=client.post("/api/chat",json={"query_text":"hello"}); assert r.status_code==200; d=r.json(); assert d["conversation_id"].startswith("conv_"); assert d["error"] is None
def test_analytics_chat(client):
    d=client.post("/api/chat",json={"query_text":"show sales revenue"}).json(); assert d["intent"]=="analytics"; assert d["kpis"]; assert d["chart_spec"]["type"]=="line"
def test_forecast_chat(client):
    d=client.post("/api/chat",json={"query_text":"forecast next quarter"}).json(); assert d["intent"]=="forecast"; assert len(d["forecast"]["points"])==3

def test_chat_history_lists_loads_and_continues(client):
    assert client.post('/api/auth/login',json={'email':'admin@example.com','password':'Admin123!'}).status_code==200
    signed_in=client
    first=signed_in.post("/api/chat",json={"query_text":"show sales revenue"}).json()
    conversations=signed_in.get("/api/chat/conversations")
    assert conversations.status_code==200
    saved=next(item for item in conversations.json() if item["id"]==first["conversation_id"])
    assert saved["message_count"]==2
    detail=signed_in.get(f"/api/chat/conversations/{first['conversation_id']}")
    assert detail.status_code==200
    assert [item["role"] for item in detail.json()["messages"]]==["user","assistant"]
    continued=signed_in.post("/api/chat",json={"conversation_id":first["conversation_id"],"query_text":"show sales orders"})
    assert continued.status_code==200
    assert continued.json()["conversation_id"]==first["conversation_id"]
    assert signed_in.get(f"/api/chat/conversations/{first['conversation_id']}").json()["messages"][-2]["content"]=="show sales orders"
