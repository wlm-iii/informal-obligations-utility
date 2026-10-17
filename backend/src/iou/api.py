"""IOU API: owner-private profiles, lending, audited corrections, and proof images."""

import random
from typing import Annotated

from fastapi import FastAPI, Query

from iou.config import get_settings
from iou.evidence.router import router as evidence_router
from iou.ledger.correction_router import router as correction_router
from iou.ledger.router import router as ledger_router
from iou.profiles import router as profiles_router

app = FastAPI(title="Informal Obligations Utility", version="0.4.0")
app.include_router(profiles_router)
app.include_router(ledger_router)
app.include_router(correction_router)
app.include_router(evidence_router)

# Validate configuration early, without connecting to PostgreSQL or sending email.
get_settings()


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness only; this does not claim database readiness."""
    return {"status": "ok", "service": "informal-obligations-utility"}


@app.get("/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from IOU"}


@app.get("/random", deprecated=True)
async def get_random_item(maximum: Annotated[int, Query(ge=0, le=1_000_000)]) -> dict[str, int]:
    """Retained starter demo, not a product feature."""
    return {"itemId": random.randint(0, maximum)}
