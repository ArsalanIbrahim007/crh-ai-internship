from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from app.integrations.email_adapter import email_adapter
from app.integrations.provider import PROVIDERS, IntegrationProvider, get_integration_provider
from app.core.security import get_current_user
from app.db.models import User
from app.core.config import get_settings

router = APIRouter(prefix='/integrations', tags=['integrations'])


def validate_provider(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(404, 'Unknown integration')


@router.get('')
async def integrations(user: User = Depends(get_current_user), adapter: IntegrationProvider = Depends(get_integration_provider)):
    return [await adapter.status(user, key) for key in PROVIDERS]


@router.get('/calendar/events')
async def events(start_iso: str, end_iso: str, user: User = Depends(get_current_user), adapter: IntegrationProvider = Depends(get_integration_provider)):
    try:
        start, end = datetime.fromisoformat(start_iso.replace('Z', '+00:00')), datetime.fromisoformat(end_iso.replace('Z', '+00:00'))
        if start >= end:
            raise ValueError()
    except (ValueError, TypeError) as error:
        raise HTTPException(422, 'Provide a valid start and end time range') from error
    status = await adapter.status(user, 'google-calendar')
    if status['state'] != 'connected':
        raise HTTPException(409, 'Connect Google Calendar before loading events.')
    return await adapter.list_events(user, start_iso, end_iso)


@router.get('/{provider}/status')
async def status(provider: str, user: User = Depends(get_current_user), adapter: IntegrationProvider = Depends(get_integration_provider)):
    validate_provider(provider)
    return await adapter.status(user, provider)


@router.post('/{provider}/connect')
async def connect(provider: str, user: User = Depends(get_current_user), adapter: IntegrationProvider = Depends(get_integration_provider)):
    validate_provider(provider)
    return await adapter.connect(user, provider)


@router.post('/{provider}/disconnect')
async def disconnect(provider: str, user: User = Depends(get_current_user), adapter: IntegrationProvider = Depends(get_integration_provider)):
    validate_provider(provider)
    return await adapter.disconnect(user, provider)


@router.get('/google/callback')
async def google_callback(state: str | None = None, code: str | None = None,
                          error: str | None = None,
                          adapter: IntegrationProvider = Depends(get_integration_provider)):
    frontend = get_settings().frontend_url.rstrip('/')
    if error:
        return RedirectResponse(f"{frontend}/connections?oauth=error&reason=denied")
    if not state or not code or not hasattr(adapter, 'complete_callback'):
        raise HTTPException(400, 'Missing or unsupported Google OAuth callback')
    try:
        provider = await adapter.complete_callback(state, code)
    except HTTPException:
        return RedirectResponse(f"{frontend}/connections?oauth=error&reason=callback")
    return RedirectResponse(f"{frontend}/connections?oauth=connected&provider={provider}")


@router.post('/email/draft')
async def draft(recipient: str, subject: str, body: str):
    # Preserve the existing local draft contract; no email is sent.
    return await email_adapter.draft(recipient, subject, body)


@router.post('/calendar/events')
@router.patch('/calendar/events/{event_id}')
@router.delete('/calendar/events/{event_id}')
@router.post('/email/send')
async def blocked_write(user: User = Depends(get_current_user)):
    # No new execution path may bypass the supervisor's proposed tool actions.
    raise HTTPException(409, 'External writes require an approved tool action. Direct calendar changes and email sending are not enabled.')
