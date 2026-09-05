import pytest
from urllib.parse import parse_qs, urlparse
from app.main import app
from app.integrations.provider import get_integration_provider


@pytest.fixture
def signed_in(client):
    assert client.post('/api/auth/login', json={'email': 'admin@example.com', 'password': 'Admin123!'}).status_code == 200
    return client


def test_status_requires_user(client):
    assert client.get('/api/integrations').status_code == 401


def test_local_provider_never_fakes_connection(signed_in):
    statuses = signed_in.get('/api/integrations').json()
    assert {item['provider'] for item in statuses} == {'google-calendar', 'gmail'}
    assert all(item['state'] == 'not_connected' and not item['configured'] for item in statuses)
    assert signed_in.post('/api/integrations/google-calendar/connect').status_code == 503
    assert signed_in.get('/api/integrations/google-calendar/status').json()['state'] == 'not_connected'
    assert signed_in.post('/api/integrations/gmail/disconnect').json()['state'] == 'not_connected'
    assert signed_in.get('/api/integrations/calendar/events', params={'start_iso': '2026-09-05T00:00:00', 'end_iso': '2026-09-06T00:00:00'}).status_code == 409


def test_connected_provider_events_and_disconnect(signed_in):
    class TestProvider:
        connected = True
        async def status(self, user, provider):
            return {'provider': provider, 'state': 'connected' if self.connected else 'not_connected', 'configured': True}
        async def list_events(self, user, start_iso, end_iso):
            return [{'id': 'real-event', 'title': 'Review', 'start': start_iso, 'end': end_iso}]
        async def disconnect(self, user, provider):
            self.connected = False
            return await self.status(user, provider)
    provider = TestProvider()
    app.dependency_overrides[get_integration_provider] = lambda: provider
    try:
        params = {'start_iso': '2026-09-05T08:00:00', 'end_iso': '2026-09-05T09:00:00'}
        assert signed_in.get('/api/integrations/calendar/events', params=params).json()[0]['id'] == 'real-event'
        assert signed_in.get('/api/integrations/calendar/events', params={'start_iso': 'bad', 'end_iso': 'bad'}).status_code == 422
        signed_in.post('/api/integrations/google-calendar/disconnect')
        assert signed_in.get('/api/integrations/calendar/events', params=params).status_code == 409
    finally:
        app.dependency_overrides.pop(get_integration_provider, None)


@pytest.mark.parametrize('method,path', [('post', '/api/integrations/calendar/events'), ('patch', '/api/integrations/calendar/events/meeting'), ('delete', '/api/integrations/calendar/events/meeting'), ('post', '/api/integrations/email/send')])
def test_direct_writes_cannot_bypass_approval(signed_in, method, path):
    response = getattr(signed_in, method)(path)
    assert response.status_code == 409
    assert 'approved tool action' in response.json()['detail']


def test_chat_keeps_approval_contract(signed_in):
    response = signed_in.post('/api/chat', json={'query_text': 'schedule a meeting'})
    assert response.status_code == 200
    assert response.json()['requires_approval'] is True
    assert response.json()['tool_calls']


def test_calendar_action_executes_only_after_approval(signed_in):
    class ApprovalProvider:
        created = []
        async def create_calendar_event(self, user, arguments):
            self.created.append(arguments)
            return {'id': 'google-event-id'}

    provider = ApprovalProvider()
    app.dependency_overrides[get_integration_provider] = lambda: provider
    try:
        proposed = signed_in.post('/api/chat', json={
            'query_text': 'Create a meeting titled Final review of the project before submission with zahsan2006@gmail.com today at 5:00 PM'
        }).json()
        assert provider.created == []
        call = proposed['tool_calls'][0]
        assert call['arguments']['meeting_title'] == 'Final review of the project before submission'
        assert call['arguments']['attendees'] == 'zahsan2006@gmail.com'

        approved = signed_in.post(f"/api/chat/{proposed['message_id']}/approval", json={'decision': 'approve'})
        assert approved.status_code == 200
        assert approved.json()['status'] == 'executed'
        assert len(provider.created) == 1

        cancelled_proposal = signed_in.post('/api/chat', json={
            'query_text': 'Schedule a meeting tomorrow at 9 AM'
        }).json()
        cancelled = signed_in.post(f"/api/chat/{cancelled_proposal['message_id']}/approval", json={'decision': 'cancel'})
        assert cancelled.status_code == 200
        assert cancelled.json()['status'] == 'cancelled'
        assert len(provider.created) == 1
    finally:
        app.dependency_overrides.pop(get_integration_provider, None)


def test_real_google_oauth_callback_encrypts_tokens_and_reads_calendar(signed_in, monkeypatch):
    from app.core.config import get_settings
    from app.db.models import OAuthConnection
    from app.db.session import SessionLocal
    from app.integrations import provider as provider_module

    settings = get_settings()
    previous = (settings.google_client_id, settings.google_client_secret,
                settings.google_redirect_uri, settings.oauth_token_encryption_key,
                settings.frontend_url)
    settings.google_client_id = 'google-client-id'
    settings.google_client_secret = 'google-client-secret'
    settings.google_redirect_uri = 'http://localhost:8000/api/integrations/google/callback'
    settings.oauth_token_encryption_key = 'test-encryption-key'
    settings.frontend_url = 'http://localhost:5173'

    class Response:
        def __init__(self, data, status_code=200):
            self._data = data
            self.status_code = status_code
            self.is_error = status_code >= 400
        def json(self): return self._data

    class GoogleClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            if url == provider_module.GOOGLE_TOKEN_URL:
                return Response({'access_token': 'plain-access-token', 'refresh_token': 'plain-refresh-token',
                                 'expires_in': 3600, 'scope': 'openid email https://www.googleapis.com/auth/calendar.events'})
            return Response({})
        async def get(self, url, **kwargs):
            if url == provider_module.GOOGLE_USERINFO_URL:
                return Response({'email': 'owner@example.com'})
            return Response({'items': [{'id': 'meeting', 'summary': 'Planning',
                                        'start': {'dateTime': '2026-09-05T10:00:00Z'},
                                        'end': {'dateTime': '2026-09-05T11:00:00Z'}}]})

    monkeypatch.setattr(provider_module.httpx, 'AsyncClient', GoogleClient)
    try:
        connect = signed_in.post('/api/integrations/google-calendar/connect')
        assert connect.status_code == 200
        authorization_url = connect.json()['authorization_url']
        query = parse_qs(urlparse(authorization_url).query)
        assert query['client_id'] == ['google-client-id']
        assert query['access_type'] == ['offline']
        assert 'https://www.googleapis.com/auth/calendar.events' in query['scope'][0]

        callback = signed_in.get('/api/integrations/google/callback',
                                 params={'state': query['state'][0], 'code': 'authorization-code'},
                                 follow_redirects=False)
        assert callback.status_code in (302, 307)
        assert callback.headers['location'] == 'http://localhost:5173/connections?oauth=connected&provider=google-calendar'
        assert signed_in.get('/api/integrations/google-calendar/status').json()['account'] == 'owner@example.com'
        events = signed_in.get('/api/integrations/calendar/events', params={
            'start_iso': '2026-09-05T00:00:00Z', 'end_iso': '2026-09-06T00:00:00Z'})
        assert events.status_code == 200
        assert events.json()[0]['summary'] == 'Planning'
        with SessionLocal() as db:
            stored = db.query(OAuthConnection).filter_by(provider='google-calendar').one()
            assert 'plain-access-token' not in stored.access_token_encrypted
            assert 'plain-refresh-token' not in stored.refresh_token_encrypted
        assert signed_in.get('/api/integrations/google/callback',
                             params={'state': query['state'][0], 'code': 'replay'},
                             follow_redirects=False).headers['location'].endswith('oauth=error&reason=callback')
        gmail_connect = signed_in.post('/api/integrations/gmail/connect')
        gmail_scope = parse_qs(urlparse(gmail_connect.json()['authorization_url']).query)['scope'][0]
        assert 'https://www.googleapis.com/auth/gmail.send' in gmail_scope
        assert 'https://www.googleapis.com/auth/calendar.events' not in gmail_scope
    finally:
        (settings.google_client_id, settings.google_client_secret,
         settings.google_redirect_uri, settings.oauth_token_encryption_key,
         settings.frontend_url) = previous
