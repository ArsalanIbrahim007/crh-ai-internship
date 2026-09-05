# AI Business Intelligence Copilot

An AI workspace for business questions, document search, persistent chat, voice interaction, and approval-gated actions in Google Calendar and Gmail.

## Features

- Business analysis and conversational assistance powered by Gemini
- Natural-language analytics workspace: ask a business question and get KPIs, a chart, insights, and recommendations, backed by NL→SQL generation over the sales data
- Document upload, extraction, indexing, and semantic search
- Persistent conversations that can be reopened and continued
- Google Calendar and Gmail connections through OAuth
- Human approval before calendar events or emails are created
- Browser voice input and optional spoken responses
- Responsive React interface with calendar, documents, connections, analytics, and history views

## Technology

- **Frontend:** React, TypeScript, Vite, React Router, Lucide icons
- **Backend:** FastAPI, SQLAlchemy, Pydantic, SQLite by default
- **AI and integrations:** Gemini API and Google OAuth APIs
- **Testing:** Pytest, Vitest, Testing Library, and Playwright

## Project structure

```text
backend/             FastAPI application, tests, and configuration template
frontend/            React application and browser tests
docs/                Project documentation
scene.splinecode     Orb scene asset
```

Runtime databases, uploaded documents, vector indexes, test output, build output, local environments, and agent metadata are ignored by Git.

## Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- A Gemini API key
- Google OAuth credentials for Calendar or Gmail connections

## Backend setup

From PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload --port 8000
```

On macOS or Linux, activate the environment with `source .venv/bin/activate` and copy the environment file with `cp .env.example .env`.

The API is available at `http://127.0.0.1:8000`; interactive API documentation is at `http://127.0.0.1:8000/docs`.

## Frontend setup

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite serves the application at `http://localhost:5173` by default.

## Environment configuration

Create `backend/.env` from `backend/.env.example` and configure the values needed by your environment.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy database connection; SQLite works for local development |
| `JWT_SECRET` | Secret used to sign authentication tokens |
| `GEMINI_API_KEY` | Gemini API credential |
| `GEMINI_MODEL` | Gemini model used by the assistant |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | Backend OAuth callback URL registered in Google Cloud |
| `OAUTH_TOKEN_ENCRYPTION_KEY` | Key used to encrypt stored OAuth tokens |
| `FRONTEND_URL` | Frontend URL used after OAuth completes |
| `CORS_ORIGINS` | Browser origins permitted to call the API |
| `DEVELOPMENT_AUTH_EMAIL` | Local development user identity |
| `VOICE_STT_MODEL` | Gemini model used for speech transcription |
| `VOICE_TTS_MODEL` | Gemini model used for speech generation |
| `VOICE_TTS_VOICE` | Voice selected for generated speech |

Do not commit `backend/.env`. If a credential has ever appeared in a commit, log, screenshot, or shared message, rotate it in the provider console.

## Google OAuth setup

1. Create or select a project in Google Cloud Console.
2. Enable the Google Calendar API and Gmail API.
3. Configure the OAuth consent screen and add your account as a test user while the app is in testing mode.
4. Create a Web application OAuth client.
5. Register the exact callback URL configured in `GOOGLE_REDIRECT_URI`, typically `http://127.0.0.1:8000/api/integrations/google/callback` for local development.
6. Add the client ID and secret to `backend/.env`, restart the API, and connect the service from the Connections screen.

Calendar events and email sends remain pending until the user approves the proposed action in chat.

## Voice interaction

Voice input requires microphone permission and a browser that supports media capture. Configure the voice model variables in `backend/.env`; the assistant still follows the same approval flow for external write actions issued by voice.

## Analytics architecture

The analytics workspace (`frontend/src/pages/AnalyticsPage.tsx`) talks to five endpoints under `/api/analytics`, implemented in `backend/app/api/analytics.py` and `backend/app/services/analytics_service.py`:

- `GET /overview` — a fixed revenue/margin summary over the sales table, used as the default landing view and as the fallback for the other read endpoints below.
- `POST /query` — the natural-language entry point. `answer_question()` sends the question and a summary of the sales schema to Gemini, asks it to return a single read-only SQL `SELECT`, validates the statement (`sql_service.validate_read_only`), executes it, and derives KPIs, a chart, and short insights from the resulting rows.
- `GET /alerts` — evaluates the overview KPIs against fixed warning/critical thresholds for revenue and gross margin.
- `GET /briefing` — combines the overview KPIs and any triggered alerts into a single daily-briefing payload.
- `POST /forecast` — a simple moving-average projection over a list of numbers; not currently called from the frontend.

Two request-binding details are easy to get wrong when extending this API, and are covered by regression tests in `backend/tests/test_analytics.py`:

- `POST /query`'s `question` parameter is a plain `str`, so FastAPI binds it as a **query parameter** (`/query?question=...`), not a JSON body. Sending `{"question": "..."}` as a JSON body returns `422`.
- `POST /forecast`'s `values` parameter is a `list[float]`, so FastAPI binds it as a **JSON array body**, not repeated query parameters. Sending `?values=1&values=2` returns `422`.

## Known limitations

- **NL→SQL depends on Gemini API availability.** `answer_question()` calls the Gemini API to translate the question into SQL. If that call fails — including the free-tier `429 Too Many Requests` responses we hit repeatedly during development — `llm_service.py` retries up to three times with exponential backoff, then returns a fixed offline string that cannot be parsed as SQL. `answer_question()` catches that failure and silently falls back to the same fixed revenue/margin overview served by `GET /overview`, regardless of what was actually asked. In practice this means: **when Gemini is rate-limited or unreachable, every question on the analytics page returns the same overview answer**, with no error shown to the user. This is intentional graceful degradation rather than a crash, but it does mean the natural-language feature is only as available as the underlying Gemini quota.
- **`/forecast` is implemented but unused.** It is not currently called from the frontend, so its moving-average projection has only been exercised directly in tests, not through the UI.
- **Alert and briefing thresholds are fixed, not configurable.** Revenue and gross-margin warning/critical thresholds are hardcoded in `app/api/analytics.py` rather than driven by configuration or historical baselines.
- **A pre-existing chat-history ordering issue was previously tracked** (`test_chat_history_lists_loads_and_continues`, a message-ordering bug unrelated to the analytics work) and is no longer reproducing in the current test run; it has not been root-caused, so it may resurface.

## Tests

Run backend tests from `backend`:

```powershell
python -m pytest
```

Run frontend unit tests and a production build from `frontend`:

```powershell
npm run test
npm run build
```

Run browser tests after installing Playwright's browser binaries:

```powershell
npx playwright install
npm run test:browser
```

## Repository hygiene

Keep credentials in local `.env` files and commit only the supplied example. Uploaded business documents, local databases, generated vector data, test artifacts, virtual environments, package installations, and production builds should remain outside version control.
