"""
Don's F1 Addiction - Backend API
FastAPI server wrapping existing F1 analysis tools.
"""

import os
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    data_status,
    prediction,
    ghost_car,
    best_car,
    common,
    standings,
    weekend,
    calendar,
    engineering,
    documents,
)


@asynccontextmanager
async def lifespan(app):
    from .services.fia_documents import get_indexer

    indexer = get_indexer()
    indexer.start()
    try:
        yield
    finally:
        await asyncio.to_thread(indexer.stop)


app = FastAPI(
    title="Don's F1 Addiction API",
    description="Formula 1 data analysis, prediction, and telemetry comparison API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-F1-Data-Error", "Retry-After"],
)

app.include_router(common.router, prefix="/api", tags=["Common"])
app.include_router(prediction.router, prefix="/api/prediction", tags=["Prediction"])
app.include_router(ghost_car.router, prefix="/api/ghost-car", tags=["Ghost Car"])
app.include_router(best_car.router, prefix="/api/best-car", tags=["Best Car"])


app.include_router(standings.router, prefix="/api/standings", tags=["Standings"])
app.include_router(weekend.router, prefix="/api/weekend", tags=["Weekend"])
app.include_router(calendar.router, prefix="/api/calendar", tags=["Calendar"])
app.include_router(engineering.router, prefix="/api/engineering", tags=["Engineering"])


app.include_router(data_status.router, prefix="/api/data", tags=["Data access"])
app.include_router(documents.router, prefix="/api/documents", tags=["FIA documents"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "f1-addiction-api"}
