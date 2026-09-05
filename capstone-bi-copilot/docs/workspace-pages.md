# Workspace pages: Documents, Calendar and Connections

## Run

From `backend` (restart after pulling this change so the two new tables are created):

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

From `frontend`:

```powershell
npm install
npm run dev
```

The existing pathname router now serves `/documents`, `/calendar`, and `/connections`. Calendar and Connections use additional entries in the existing navigation rail. Existing navigation controls retain their positions; the orb and Copilot components, global stylesheet, and Spline asset are unchanged.

Workspace reads, folders, and connection status use the existing authenticated user dependency. The current frontend has no sign-in screen, so local development may set `DEVELOPMENT_AUTH_EMAIL=admin@example.com` to use that seeded account without a cookie. This fallback only runs when `ENVIRONMENT=development`; production and unconfigured environments still require the existing `/api/auth/login` session or bearer token. Use the same hostname for the frontend and backend (for example `localhost` for both) so the existing SameSite session cookie works. Set `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env` when using `localhost`.

## Documents

- Upload opens the native chooser, then calls the existing ingestion pipeline with Uploading / Processing / Uploaded feedback.
- Supported formats: PDF, DOCX, CSV, XLSX, XLSM, TXT, MD and HTML. Images and legacy binary XLS are not supported by the existing extractor and are not advertised.
- Folder creation, renaming, uploads, document moves and deletion persist in the backend. Folders belong to the authenticated user.
- Non-empty folders cannot be deleted. Users must first move or individually delete documents; deleting a document requires explicit UI confirmation.
- Only populated categories display counts. An empty workspace contains no seeded folders or example documents.
- Search and Grid/List switch locally over backend results. There is no Last modified sorting dropdown.
- Folder navigation and results each scroll independently. Headers and toolbar remain fixed.
- Existing document response fields and upload/search URLs are preserved. New uploads include size and folder metadata. Older files can show “Size unavailable.”
- `document_folders` and `document_details` are additive tables created by the existing `Base.metadata.create_all` startup. Existing document tables and extraction code do not change. `DocumentDetails` stores optional folder/size/update metadata alongside the existing `Document` record, avoiding a destructive database migration.
- Old browser-local folder names/assignments are not imported automatically. They never represented server folders; recreate wanted folders and move files using Details / move.

Document API:

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/documents` | Role-filtered metadata |
| POST | `/api/documents/upload` | Existing root ingestion contract |
| GET / POST | `/api/documents/folders` | List / create user folders |
| PATCH / DELETE | `/api/documents/folders/{folder_id}` | Rename / delete empty folder |
| POST | `/api/documents/folders/{folder_id}/upload` | Upload into a user-owned folder |
| PATCH | `/api/documents/{document_id}` | Move document using `folder_id` |
| DELETE | `/api/documents/{document_id}` | Delete file, chunks and metadata |

## Calendar and Connections

Connection state comes from the backend, with refresh on navigation, window focus, connection actions, and periodic revalidation. It is never persisted as a fake connected flag in browser storage.

The current `LocalIntegrationProvider` always reports Google Calendar and Gmail as not connected. Connect returns an explicit setup error; disconnect is idempotent. No Google data is read, no OAuth token is fabricated, and no provider token or secret is sent to the frontend.

The connected UI is implemented and tested through dependency-injected providers and browser API fixtures. It has Day/Week views, a mini month navigator, Today/previous/next navigation, a primary-calendar checkbox, overlapping appointment columns, current-time positioning, and event details. The 08:00–20:00 time grid uses fractional rows. All-day and outside-hours events remain accessible through a separate event list. On narrow screens the local sidebar collapses and the calendar uses Day view.

Connections presents Calendar and Gmail, including connect/reconnect, setup errors, account/status display, management details, and confirmed disconnect. Write requests cannot execute through the new direct API routes: they return an approval-required error. The existing supervisor still proposes external actions with `requires_approval=true`; its execution architecture is unchanged.

Integration API:

- `GET /api/integrations`
- `GET /api/integrations/{google-calendar|gmail}/status`
- `POST /api/integrations/{google-calendar|gmail}/connect`
- `POST /api/integrations/{google-calendar|gmail}/disconnect`
- `GET /api/integrations/calendar/events?start_iso=...&end_iso=...`

### Google OAuth setup

A live Google web-server OAuth flow is implemented for Google Calendar and Gmail. Each provider requests its own least-privilege read scope. The backend creates a one-time, ten-minute OAuth state, exchanges the callback code server-side, reads the account email, encrypts access and refresh tokens at rest, refreshes expired access tokens, and revokes the Google grant when disconnected. Calendar events come from the connected account's primary calendar. Gmail connection and status are available; Gmail message search/read UI is not part of this page yet.

`backend/.env.example` includes the required server-only settings:

```dotenv
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/google/callback
OAUTH_TOKEN_ENCRYPTION_KEY=
FRONTEND_URL=http://localhost:5173
```

Create a Google Cloud OAuth 2.0 **Web application** client, enable Google Calendar API and Gmail API, and add the redirect URI exactly as shown. Put its client ID and secret in `backend/.env`, retain the generated encryption key, and restart the backend. Changing that encryption key makes existing stored tokens unreadable and requires reconnection. Provider secrets and refresh tokens never enter frontend code or localStorage. Calendar/event writes and email sends remain blocked unless they execute through the existing approval architecture.

## Validation

From `frontend`:

```powershell
npm run test
npm run build
npx playwright install chromium
npm run test:browser
```

On a Windows machine with Edge already installed, use `$env:PLAYWRIGHT_CHANNEL='msedge'` instead of installing Chromium. Browser tests launch an isolated Vite server on port 5180 and use test-only API interception. Production components contain no demo events or files.

From `backend`, the regular suite is `.venv\Scripts\python.exe -m pytest -q`. For deterministic offline checks without contacting Gemini, with an isolated database and temporary directory:

```powershell
.venv\Scripts\python.exe -c "import os,uuid; os.environ['GEMINI_API_KEY']=''; os.environ['DATABASE_URL']='sqlite:///./test-'+uuid.uuid4().hex+'.db'; import pytest; raise SystemExit(pytest.main(['-q','--basetemp=./test_runtime/pytest-'+uuid.uuid4().hex]))"
```

The existing backend suite resets its configured test database, so never run it against a production database. The offline command changes only the test process environment. No lint script is configured. The production bundle retains the existing large Spline-related chunks.

## Change inventory

Modified in this revision:

- Frontend: `src/App.tsx`, `src/components/layout/Sidebar.tsx`, `src/pages/DocumentsPage.tsx`, `src/pages/CalendarPage.tsx`, `src/pages/workspace.css`, `src/lib/workspace.ts`, `package.json`, `package-lock.json`.
- Backend: `app/api/documents.py`, `app/api/integrations.py`, `app/db/models.py`, `.env.example`.
- Repository: `.gitignore` (browser output exclusions and explicit inclusion of the placeholder `.env.example`).

Created in this revision:

- Frontend: `src/pages/ConnectionsPage.tsx`, `src/components/workspace/WorkspaceControls.tsx` (`WorkspaceDialog`, `ActionMenu`), `src/lib/useIntegrations.ts`, `src/lib/calendarLayout.ts`, `playwright.config.ts`, `tests/workspace.spec.ts`.
- Backend: `app/services/document_workspace.py`, `app/integrations/provider.py`, `tests/test_document_folders.py`, `tests/test_integrations.py`.
- Documentation: `docs/workspace-pages.md`.

Verification: production build/type checking passed; 10 browser cases passed, with a subsequent short-laptop event-label regression check; 25 backend cases passed in the full offline run and 3 subsequently added binary-format cases passed separately. Protected-file hashes were compared against the start of this revision and remained unchanged. Browser checks confirmed the same orb canvas DOM instance across navigation and unchanged original navigation-control coordinates.
