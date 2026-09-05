import pytest
from app.agents.tool_routing import classify_tool_intent
from app.integrations.provider import get_integration_provider
from app.main import app

@pytest.fixture
def signed_in(client):
    assert client.post('/api/auth/login',json={'email':'admin@example.com','password':'Admin123!'}).status_code==200
    return client

@pytest.mark.parametrize("prompt,intent,tool", [
    ("Send john@example.com an email about tomorrow's meeting", "email_send", "send_email"),
    ("Schedule a meeting with john@example.com tomorrow at 3 PM", "calendar_create", "create_calendar_event"),
    ("Email John asking if he is available at 3 PM", "email_send", "send_email"),
    ("Check whether I am free at 3 PM", "calendar_availability", "check_calendar_availability"),
    ("Send John a reminder about our calendar meeting", "email_send", "send_email"),
    ("What meetings do I have today?", "calendar_read", "list_calendar_events"),
    ("Read my latest email from finance", "email_read", "read_email"),
])
def test_action_first_tool_routing(prompt, intent, tool):
    route=classify_tool_intent(prompt)
    assert route and route.intent==intent and route.tool_name==tool

def test_email_proposal_and_send_use_gmail(signed_in):
    class Provider:
        sent=[]
        async def send_email(self,user,arguments):
            self.sent.append(arguments); return {"id":"gmail-message"}
    provider=Provider()
    app.dependency_overrides[get_integration_provider]=lambda:provider
    try:
        response=signed_in.post('/api/chat',json={'query_text':'send an email to zahsan2006@gmail.com at 5:00 today to attend a meeting for the final review of project before submission'}).json()
        call=response['tool_calls'][0]
        assert call['tool_name']=='send_email'
        assert call['arguments']['to']=='zahsan2006@gmail.com'
        assert call['arguments']['subject']=='Final Project Review Meeting'
        assert '5:00 PM today' in call['arguments']['message']
        assert provider.sent==[]
        result=signed_in.post(f"/api/chat/{response['message_id']}/approval",json={'decision':'approve'}).json()
        assert result['status']=='executed' and len(provider.sent)==1
    finally: app.dependency_overrides.pop(get_integration_provider,None)

def test_ambiguous_calendar_time_requests_clarification(signed_in):
    response=signed_in.post('/api/chat',json={'query_text':'Schedule a meeting tomorrow at 5:00'}).json()
    assert response['tool_calls']==[]
    assert 'AM or 5:00 PM' in response['answer']
