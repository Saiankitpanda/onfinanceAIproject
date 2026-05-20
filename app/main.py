from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes_documents import router as documents_router, limiter as documents_limiter
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging
import json
try:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
except Exception:
    sentry_sdk = None
    LoggingIntegration = None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Content Security Policy: allow configuring via SECURITY_CSP env var.
        # Default is strict (no 'unsafe-inline'). For local development, set
        # APP_ENV=development or provide SECURITY_CSP to allow inline scripts/styles.
        default_csp = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "object-src 'none'; frame-ancestors 'none'; base-uri 'self';"
        )

        csp = os.getenv('SECURITY_CSP')
        app_env = os.getenv('APP_ENV', 'production')
        # CSP presets per environment (can be overridden by SECURITY_CSP)
        CSP_PRESETS = {
            'development': "default-src 'self' 'unsafe-inline' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' data:; style-src 'self' 'unsafe-inline'",
            'staging': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self';",
            'production': default_csp,
            'test': "default-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        }

        if not csp:
            csp = CSP_PRESETS.get(app_env, default_csp)

        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        return response

app = FastAPI(title="ClauseMark Backend")

# Apply request rate limiting middleware globally. The agent route is protected with a stricter endpoint-level limit.
app.state.limiter = documents_limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

# Configure structured logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("clausemark")

# Initialize Sentry if DSN is provided
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors as events
    )
    sentry_sdk.init(dsn=SENTRY_DSN, integrations=[sentry_logging], traces_sample_rate=0.1)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait and try again later."},
    )

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

app.include_router(documents_router)

@app.get("/")
def serve_frontend():
    return FileResponse(frontend_dir / "index.html")

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ClauseMark Backend"
    }
