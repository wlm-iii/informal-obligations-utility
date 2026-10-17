"""IOU API foundation. Domain features belong in subsequent feature PRs."""

import random
from typing import Annotated

from fastapi import FastAPI, Query

from iou.config import get_settings

app = FastAPI(title="Informal Obligations Utility", version="0.1.0")

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
