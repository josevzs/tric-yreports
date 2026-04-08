import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import upload, fetch, expenses, categorize, settings_router, report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("tricountreport")

# Allow-list: override with ALLOWED_ORIGINS env var (comma-separated) for production
_env_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    or ["http://localhost:5173", "http://localhost:4173"]
)

app = FastAPI(title="TricountReport API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(upload.router, prefix="/api")
app.include_router(fetch.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(categorize.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(report.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
