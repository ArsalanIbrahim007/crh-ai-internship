"""Server-side Google OAuth provider boundary."""
from __future__ import annotations

from base64 import urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from typing import Protocol
from urllib.parse import urlencode
from email.message import EmailMessage

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
import httpx

from app.core.config import get_settings
from app.db.models import OAuthConnection, OAuthState, User
from app.db.session import SessionLocal


PROVIDERS = {
    "google-calendar": {"name": "Google Calendar", "description": "View your schedule and check availability with your assistant.", "scopes": ["https://www.googleapis.com/auth/calendar.events"]},
    "gmail": {"name": "Gmail", "description": "Find email and bring conversation context into your work.", "scopes": ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.send"]},
}
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class IntegrationProvider(Protocol):
    async def status(self, user: User, provider: str) -> dict: ...
    async def connect(self, user: User, provider: str) -> dict: ...
    async def disconnect(self, user: User, provider: str) -> dict: ...
    async def list_events(self, user: User, start_iso: str, end_iso: str) -> list[dict]: ...
    async def create_calendar_event(self, user: User, arguments: dict) -> dict: ...
    async def send_email(self, user: User, arguments: dict) -> dict: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


class GoogleIntegrationProvider:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.google_client_id and self.settings.google_client_secret and
                    self.settings.google_redirect_uri and self.settings.oauth_token_encryption_key)

    def _require_configured(self) -> None:
        if not self.configured:
            raise HTTPException(503, "Google OAuth is not configured. Add the server credentials and token encryption key, then restart the backend.")

    def _cipher(self) -> Fernet:
        self._require_configured()
        key = urlsafe_b64encode(sha256(self.settings.oauth_token_encryption_key.encode()).digest())
        return Fernet(key)

    def _encrypt(self, value: str | None) -> str | None:
        return self._cipher().encrypt(value.encode()).decode("ascii") if value else None

    def _decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self._cipher().decrypt(value.encode("ascii")).decode()
        except InvalidToken as error:
            raise HTTPException(503, "Stored Google credentials cannot be decrypted. Reconnect this integration.") from error

    @staticmethod
    def _connection(db, user_id: int, provider: str) -> OAuthConnection | None:
        return db.query(OAuthConnection).filter_by(user_id=user_id, provider=provider).first()

    async def status(self, user: User, provider: str) -> dict:
        with SessionLocal() as db:
            connection = self._connection(db, user.id, provider)
            state = "not_connected"
            granted = set((connection.scopes if connection else "").split())
            missing = [scope for scope in PROVIDERS[provider]["scopes"] if scope not in granted]
            if connection and self.configured:
                expires = _aware(connection.token_expires_at)
                state = "needs_reauthorization" if missing or (expires and expires <= _utcnow() and not connection.refresh_token_encrypted) else "connected"
            return {"provider": provider, "name": PROVIDERS[provider]["name"],
                    "description": PROVIDERS[provider]["description"],
                    "state": state,
                    "configured": self.configured, "account": connection.account_email if connection else None,
                    "has_required_scope": bool(connection) and not missing, "missing_scopes": missing,
                    "message": None if self.configured else "Google OAuth is not configured. No account is connected."}

    def _require_scope(self, user_id: int, provider: str, required: str, message: str) -> None:
        with SessionLocal() as db:
            connection = self._connection(db, user_id, provider)
            if not connection or required not in connection.scopes.split():
                raise HTTPException(403, message)

    async def connect(self, user: User, provider: str) -> dict:
        self._require_configured()
        state = secrets.token_urlsafe(40)
        with SessionLocal() as db:
            db.query(OAuthState).filter(OAuthState.expires_at < _utcnow()).delete(synchronize_session=False)
            db.add(OAuthState(state_hash=sha256(state.encode()).hexdigest(), user_id=user.id,
                              provider=provider, expires_at=_utcnow() + timedelta(minutes=10)))
            db.commit()
        scopes = ["openid", "email", *PROVIDERS[provider]["scopes"]]
        query = urlencode({"client_id": self.settings.google_client_id,
                           "redirect_uri": self.settings.google_redirect_uri, "response_type": "code",
                           "scope": " ".join(scopes), "access_type": "offline",
                           "include_granted_scopes": "true", "prompt": "consent select_account", "state": state})
        return {"authorization_url": f"{GOOGLE_AUTH_URL}?{query}"}

    async def complete_callback(self, state: str, code: str) -> str:
        self._require_configured()
        with SessionLocal() as db:
            record = db.get(OAuthState, sha256(state.encode()).hexdigest())
            if not record or (_aware(record.expires_at) or _utcnow()) < _utcnow():
                if record:
                    db.delete(record); db.commit()
                raise HTTPException(400, "Invalid or expired OAuth state. Start the connection again.")
            user_id, provider = record.user_id, record.provider
            db.delete(record)
            db.commit()
        payload = {"code": code, "client_id": self.settings.google_client_id,
                   "client_secret": self.settings.google_client_secret,
                   "redirect_uri": self.settings.google_redirect_uri, "grant_type": "authorization_code"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=payload)
            if response.is_error:
                raise HTTPException(400, "Google rejected the authorization code. Start the connection again.")
            tokens = response.json()
            access_token = tokens.get("access_token")
            if not access_token:
                raise HTTPException(400, "Google did not return an access token.")
            profile = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            if profile.is_error:
                raise HTTPException(400, "Could not read the connected Google account.")
            account_email = profile.json().get("email")
        with SessionLocal() as db:
            connection = self._connection(db, user_id, provider)
            if connection is None:
                connection = OAuthConnection(user_id=user_id, provider=provider, access_token_encrypted="", scopes="")
                db.add(connection)
            connection.account_email = account_email
            connection.access_token_encrypted = self._encrypt(access_token) or ""
            if tokens.get("refresh_token"):
                connection.refresh_token_encrypted = self._encrypt(tokens["refresh_token"])
            connection.token_expires_at = _utcnow() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
            connection.scopes = tokens.get("scope", " ".join(PROVIDERS[provider]["scopes"]))
            db.commit()
        return provider

    async def _access_token(self, user_id: int, provider: str) -> str:
        self._require_configured()
        with SessionLocal() as db:
            connection = self._connection(db, user_id, provider)
            if connection is None:
                raise HTTPException(409, f"Connect {PROVIDERS[provider]['name']} before using it.")
            expires = _aware(connection.token_expires_at)
            if expires and expires > _utcnow() + timedelta(minutes=1):
                return self._decrypt(connection.access_token_encrypted) or ""
            refresh_token = self._decrypt(connection.refresh_token_encrypted)
            if not refresh_token:
                raise HTTPException(401, "Google authorization expired. Reconnect this integration.")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data={"client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret, "refresh_token": refresh_token,
                "grant_type": "refresh_token"})
        if response.is_error:
            raise HTTPException(401, "Google authorization needs to be renewed. Reconnect this integration.")
        tokens = response.json()
        access_token = tokens.get("access_token")
        if not access_token:
            raise HTTPException(502, "Google did not return a refreshed access token.")
        with SessionLocal() as db:
            connection = self._connection(db, user_id, provider)
            if connection:
                connection.access_token_encrypted = self._encrypt(access_token) or ""
                connection.token_expires_at = _utcnow() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
                db.commit()
        return access_token

    async def disconnect(self, user: User, provider: str) -> dict:
        with SessionLocal() as db:
            connection = self._connection(db, user.id, provider)
            token = (self._decrypt(connection.refresh_token_encrypted or connection.access_token_encrypted)
                     if connection and self.configured else None)
        if token:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    await client.post(GOOGLE_REVOKE_URL, params={"token": token})
            except httpx.HTTPError:
                pass
        with SessionLocal() as db:
            connection = self._connection(db, user.id, provider)
            if connection:
                db.delete(connection); db.commit()
        return await self.status(user, provider)

    async def list_events(self, user: User, start_iso: str, end_iso: str) -> list[dict]:
        token = await self._access_token(user.id, "google-calendar")
        params = {"timeMin": start_iso, "timeMax": end_iso, "singleEvents": "true",
                  "orderBy": "startTime", "maxResults": 500}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(CALENDAR_EVENTS_URL, params=params,
                                        headers={"Authorization": f"Bearer {token}"})
        if response.status_code in (401, 403):
            raise HTTPException(401, "Google Calendar access needs authorization. Reconnect Calendar.")
        if response.is_error:
            raise HTTPException(502, "Google Calendar could not be reached. Try again shortly.")
        return response.json().get("items", [])

    async def create_calendar_event(self, user: User, arguments: dict) -> dict:
        self._require_scope(user.id, "google-calendar", "https://www.googleapis.com/auth/calendar.events",
                            "Google Calendar needs write permission. Reconnect Calendar and approve access.")
        token = await self._access_token(user.id, "google-calendar")
        attendee = str(arguments.get("attendees") or arguments.get("attendee") or "").strip()
        payload = {"summary": arguments["meeting_title"],
                   "start": {"dateTime": arguments["start"]},
                   "end": {"dateTime": arguments["end"]}}
        if attendee:
            payload["attendees"] = [{"email": attendee}]
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(CALENDAR_EVENTS_URL, json=payload,
                                         headers={"Authorization": f"Bearer {token}"})
        if response.status_code in (401, 403):
            raise HTTPException(401, "Google Calendar needs write permission. Reconnect Calendar and approve access.")
        if response.is_error:
            raise HTTPException(502, "Google Calendar could not create the meeting. Try again shortly.")
        return response.json()

    async def send_email(self, user: User, arguments: dict) -> dict:
        self._require_scope(user.id, "gmail", "https://www.googleapis.com/auth/gmail.send",
                            "Gmail needs permission to send email. Reconnect Gmail and approve email access.")
        token = await self._access_token(user.id, "gmail")
        message = EmailMessage()
        message["To"], message["Subject"] = arguments["to"], arguments["subject"]
        message.set_content(arguments["message"])
        raw = urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(GMAIL_SEND_URL, json={"raw": raw}, headers={"Authorization": f"Bearer {token}"})
        if response.status_code in (401, 403):
            raise HTTPException(403, "Gmail needs permission to send email. Reconnect Gmail and approve email access.")
        if response.is_error:
            detail = response.json().get("error", {}).get("message") if response.headers.get("content-type", "").startswith("application/json") else None
            raise HTTPException(502, detail or "Gmail could not send the email. Try again shortly.")
        return response.json()


_provider = GoogleIntegrationProvider()


def get_integration_provider() -> IntegrationProvider:
    return _provider
