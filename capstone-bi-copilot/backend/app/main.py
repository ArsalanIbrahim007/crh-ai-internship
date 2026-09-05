from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.seed import init_database
from app.api import auth,chat,analytics,documents,reports,integrations,health,voice
from app.middleware.request_context import request_context

configure_logging(); settings=get_settings()
@asynccontextmanager
async def lifespan(app:FastAPI): init_database(); yield
app=FastAPI(title=settings.app_name,version="1.0.0",lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,

    # Allow Vite development origins without weakening production CORS.
    allow_origin_regex=(
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        if settings.environment == "development"
        else None
    ),

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_context)
for r in [health.router,auth.router,chat.router,analytics.router,documents.router,reports.router,integrations.router,voice.router]: app.include_router(r,prefix=settings.api_prefix)
