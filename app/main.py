"""
main.py — FastAPI entry-point del Bot de Agendas.

Registra todos los routers (adaptadores de plataforma + endpoints de control).
Configura logging, CORS y el healthcheck.
"""
from __future__ import annotations

import logging
import logging.config
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters import instagram_adapter, whatsapp_adapter
from app.brain import process_message
from app.config import APP_ENV, LOG_LEVEL
from app.models import BrainOutput, IncomingMessage

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Bot de Agendas — Cerebro Central",
    description=(
        "API de agendamiento inteligente multi-plataforma. "
        "Procesa mensajes de WhatsApp e Instagram y coordina citas via Google Calendar."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS (ajustar origins en producción) ─────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers de plataforma ────────────────────────────────────────────────────
app.include_router(whatsapp_adapter.router)
app.include_router(instagram_adapter.router)


# ─── Endpoint de prueba directa del cerebro ───────────────────────────────────
@app.post(
    "/brain/process",
    response_model=BrainOutput,
    tags=["Brain"],
    summary="Procesa un mensaje directamente (para testing/integración)",
    description=(
        "Endpoint de uso interno / testing. Recibe un IncomingMessage normalizado "
        "y devuelve el BrainOutput completo sin pasar por ningún adaptador de plataforma."
    ),
)
async def brain_process(msg: IncomingMessage) -> BrainOutput:
    return process_message(msg)


# ─── Healthcheck ──────────────────────────────────────────────────────────────
@app.get(
    "/health",
    tags=["Health"],
    summary="Healthcheck del servicio",
)
async def health():
    return {
        "status": "ok",
        "env": APP_ENV,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": app.version,
    }


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "name": "Bot de Agendas — Cerebro Central",
        "docs": "/docs",
        "health": "/health",
    }
