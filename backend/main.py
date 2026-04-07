from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import upload, fetch, expenses, categorize, settings_router, report

app = FastAPI(title="TricountReport API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
