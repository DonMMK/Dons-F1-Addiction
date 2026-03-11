"""
Don's F1 Addiction - Backend API
FastAPI server wrapping existing F1 analysis tools.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import prediction, ghost_car, best_car, common

app = FastAPI(
    title="Don's F1 Addiction API",
    description="Formula 1 data analysis, prediction, and telemetry comparison API",
    version="1.0.0",
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
)

app.include_router(common.router, prefix="/api", tags=["Common"])
app.include_router(prediction.router, prefix="/api/prediction", tags=["Prediction"])
app.include_router(ghost_car.router, prefix="/api/ghost-car", tags=["Ghost Car"])
app.include_router(best_car.router, prefix="/api/best-car", tags=["Best Car"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "f1-addiction-api"}
