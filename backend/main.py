"""
Fraud Detection System — FastAPI entry point.

Run with:
    uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.auth import router as auth_router
from api.transactions import router as transactions_router
from api.admin import router as admin_router
from models.db_models import init_db


# ── Lifespan: run once on startup / shutdown ────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if they don't exist
    init_db()
    yield
    # Shutdown: cleanup if needed


# ── App instance ────────────────────────────────────────────────
app = FastAPI(
    title="Fraud Detection System",
    description="Real-time UPI / bank-transfer fraud detection API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS (allow React dev server) ───────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(admin_router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "fraud-detection-api"}
