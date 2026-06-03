import logging
import logging.config
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import engine
from app.models import Base
from app.routers import analyst, chat, loader, parcels, analytics
from app.services.signals_service import compute_parcel_signals, signals_are_stale

# ── Logging configuration ─────────────────────────────────────────────────────
# Configure via dictConfig so it runs at import time AND survives uvicorn's
# own logging setup (uvicorn only calls basicConfig, not dictConfig).
logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "clean": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
            "datefmt": "%H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "clean",
        }
    },
    "loggers": {
        # Suppress SQLAlchemy engine SQL echo (BEGIN/COMMIT/SELECT spam)
        "sqlalchemy": {"level": "WARNING", "propagate": False},
        "sqlalchemy.engine": {"level": "WARNING", "propagate": False},
        "sqlalchemy.engine.Engine": {"level": "WARNING", "propagate": False},
        "sqlalchemy.pool": {"level": "WARNING", "propagate": False},
        # Suppress other noisy third-party loggers
        "httpx": {"level": "WARNING", "propagate": False},
        "httpcore": {"level": "WARNING", "propagate": False},
        "uvicorn.access": {"level": "WARNING", "propagate": False},
        "asyncio": {"level": "WARNING", "propagate": False},
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
})


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    # Compute signals if stale
    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        stale = await signals_are_stale(db)
        if stale:
            print("Computing parcel signals at startup...")
            count = await compute_parcel_signals(db)
            print(f"Signals computed: {count} parcels")

    yield

    await engine.dispose()


app = FastAPI(
    title="Property Tax Analyst",
    description="AI-powered property tax analysis for Davidson County, Nashville TN",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(parcels.router)
app.include_router(chat.router)
app.include_router(analyst.router)
app.include_router(loader.router)
app.include_router(analytics.router)

# Serve the frontend at /ui
_static_dir = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="static")


@app.get("/")
async def root():
    return FileResponse(_static_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
