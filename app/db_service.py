"""
db_service.py — Persistencia de contexto, historial y citas.

En esta iteración usa almacenamiento en memoria (dict).
Para producción: sustituir por SQLite / PostgreSQL / Firestore.
El contrato de funciones NO cambia.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.models import ConversationTurn

logger = logging.getLogger(__name__)

# ─── Almacenamiento en memoria ────────────────────────────────────────────────
_CONTEXT_STORE: dict[str, list[ConversationTurn]] = {}   # user_id -> historial
_APPOINTMENTS: dict[str, dict] = {}                       # user_id -> cita activa


# ─── Historial / Contexto ─────────────────────────────────────────────────────

def get_context(user_id: str, max_turns: int = 10) -> list[ConversationTurn]:
    """Recupera los últimos N turnos de conversación de un usuario."""
    turns = _CONTEXT_STORE.get(user_id, [])
    result = turns[-max_turns:] if len(turns) > max_turns else turns
    logger.debug("[DB] get_context user=%s turns=%d", user_id, len(result))
    return result


def save_turn(user_id: str, role: str, content: str) -> None:
    """Guarda un nuevo turno en el historial."""
    if user_id not in _CONTEXT_STORE:
        _CONTEXT_STORE[user_id] = []
    _CONTEXT_STORE[user_id].append(
        ConversationTurn(role=role, content=content, timestamp=datetime.now())
    )
    # Limitar a 50 turnos por usuario para no crecer indefinidamente
    if len(_CONTEXT_STORE[user_id]) > 50:
        _CONTEXT_STORE[user_id] = _CONTEXT_STORE[user_id][-50:]


def clear_context(user_id: str) -> None:
    """Borra el historial de un usuario (ej. después de cancelar)."""
    _CONTEXT_STORE.pop(user_id, None)


# ─── Citas ────────────────────────────────────────────────────────────────────

def save_appointment(
    user_id: str,
    event_id: str,
    service: str,
    start_dt: datetime,
    platform: str,
) -> None:
    """Persiste los datos de una cita confirmada."""
    _APPOINTMENTS[user_id] = {
        "event_id": event_id,
        "service": service,
        "start_dt": start_dt,
        "platform": platform,
        "created_at": datetime.now(),
    }
    logger.info("[DB] save_appointment user=%s event_id=%s", user_id, event_id)


def get_appointment(user_id: str) -> Optional[dict]:
    """Recupera la cita activa de un usuario, o None si no tiene."""
    appt = _APPOINTMENTS.get(user_id)
    logger.debug("[DB] get_appointment user=%s -> %s", user_id, appt)
    return appt


def delete_appointment(user_id: str) -> bool:
    """Elimina la cita activa de un usuario. Retorna True si existía."""
    existed = user_id in _APPOINTMENTS
    _APPOINTMENTS.pop(user_id, None)
    logger.info("[DB] delete_appointment user=%s existed=%s", user_id, existed)
    return existed
