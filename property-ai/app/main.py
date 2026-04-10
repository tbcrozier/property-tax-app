from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import engine
from app.models import Base
from app.routers import analyst, chat, loader, parcels
from app.services.signals_service import compute_parcel_signals, signals_are_stale


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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


@app.get("/health")
async def health():
    return {"status": "ok"}
