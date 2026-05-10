"""
calendar_service.py — Interfaz con Google Calendar.

En esta iteración, todas las funciones están SIMULADAS (mock).
Para activar Google Calendar real:
  1. Crea una cuenta de servicio en Google Cloud Console
  2. Descarga el JSON y colócalo en ./credentials/service_account.json
  3. Comparte el calendario con el email de la cuenta de servicio
  4. Descomenta el bloque "REAL IMPLEMENTATION" en cada función

El contrato de las funciones NO cambia — brain.py seguirá funcionando.
"""
from __future__ import annotations

import logging
import random
import string
from datetime import datetime, timedelta
from typing import Optional

from app.config import (
    BUSINESS_CLOSE_HOUR,
    BUSINESS_OPEN_DAYS,
    BUSINESS_OPEN_HOUR,
    DEFAULT_SLOT_MINUTES,
)
from app.models import CalendarSlot

logger = logging.getLogger(__name__)

# ─── Datos simulados ──────────────────────────────────────────────────────────
# Simula citas ya reservadas para probar conflictos
_MOCK_BOOKED: set[str] = set()  # Guarda "YYYY-MM-DDTHH:MM" de slots ocupados

_MOCK_EVENTS: dict[str, dict] = {}  # event_id -> {user_id, service, slot}


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _is_business_hours(dt: datetime) -> bool:
    """Verifica si un datetime cae en horario de negocio."""
    return (
        dt.weekday() in BUSINESS_OPEN_DAYS
        and BUSINESS_OPEN_HOUR <= dt.hour < BUSINESS_CLOSE_HOUR
    )


def _next_business_slot(from_dt: datetime) -> datetime:
    """
    Dado un datetime de referencia, devuelve el próximo slot de negocio
    redondeado al múltiplo de DEFAULT_SLOT_MINUTES más cercano.
    """
    # Redondear hacia arriba al próximo bloque
    minutes = DEFAULT_SLOT_MINUTES
    remainder = from_dt.minute % minutes
    if remainder != 0:
        from_dt = from_dt + timedelta(minutes=minutes - remainder)
    from_dt = from_dt.replace(second=0, microsecond=0)

    # Avanzar hasta encontrar horario hábil
    for _ in range(14 * 24 * 4):  # máximo 2 semanas
        if _is_business_hours(from_dt):
            return from_dt
        from_dt += timedelta(minutes=minutes)

    raise RuntimeError("No se encontró un slot disponible en los próximos 14 días.")


def _generate_event_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=16))


# ─── API Pública ──────────────────────────────────────────────────────────────

def check_availability(dt: datetime) -> bool:
    """
    Verifica si un slot específico está disponible.

    Args:
        dt: Datetime exacto que el cliente solicitó.

    Returns:
        True si el slot está libre, False si está ocupado.

    --- REAL IMPLEMENTATION ---
    service = _get_calendar_service()
    time_min = dt.isoformat() + "Z"
    time_max = (dt + timedelta(minutes=DEFAULT_SLOT_MINUTES)).isoformat() + "Z"
    events = service.events().list(
        calendarId=GOOGLE_CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
    ).execute()
    return len(events.get("items", [])) == 0
    """
    slot_key = dt.strftime("%Y-%m-%dT%H:%M")
    is_available = slot_key not in _MOCK_BOOKED and _is_business_hours(dt)
    logger.info("[CALENDAR MOCK] check_availability(%s) -> %s", slot_key, is_available)
    return is_available


def get_next_slots(n: int = 2, from_dt: Optional[datetime] = None) -> list[CalendarSlot]:
    """
    Devuelve los próximos N slots libres a partir de from_dt.

    Args:
        n: Número de slots a devolver.
        from_dt: Punto de partida. Si None, usa datetime.now().

    Returns:
        Lista de CalendarSlot disponibles.

    --- REAL IMPLEMENTATION ---
    Iterar sobre los próximos slots y filtrar con check_availability().
    """
    base = from_dt or datetime.now()
    slots: list[CalendarSlot] = []
    current = _next_business_slot(base + timedelta(hours=1))  # al menos 1h de margen

    while len(slots) < n:
        slot_key = current.strftime("%Y-%m-%dT%H:%M")
        if slot_key not in _MOCK_BOOKED:
            end = current + timedelta(minutes=DEFAULT_SLOT_MINUTES)
            slots.append(CalendarSlot(start_dt=current, end_dt=end, available=True))
        current = _next_business_slot(current + timedelta(minutes=DEFAULT_SLOT_MINUTES))

    logger.info("[CALENDAR MOCK] get_next_slots(%d) -> %s", n, [s.start_dt for s in slots])
    return slots


def create_event(
    slot: CalendarSlot,
    service: str,
    user_id: str,
    notes: str = "",
) -> str:
    """
    Crea un evento en Google Calendar y devuelve el event_id.

    Returns:
        event_id (str) — guardar en BD para futuras cancelaciones.

    --- REAL IMPLEMENTATION ---
    service_obj = _get_calendar_service()
    event = {
        "summary": f"{service} — {user_id}",
        "description": notes,
        "start": {"dateTime": slot.start_dt.isoformat(), "timeZone": "America/Mexico_City"},
        "end":   {"dateTime": slot.end_dt.isoformat(),   "timeZone": "America/Mexico_City"},
    }
    created = service_obj.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event).execute()
    return created["id"]
    """
    event_id = _generate_event_id()
    slot_key = slot.start_dt.strftime("%Y-%m-%dT%H:%M")
    _MOCK_BOOKED.add(slot_key)
    _MOCK_EVENTS[event_id] = {
        "user_id": user_id,
        "service": service,
        "slot": slot,
        "notes": notes,
    }
    logger.info(
        "[CALENDAR MOCK] create_event -> id=%s user=%s service=%s slot=%s",
        event_id, user_id, service, slot_key,
    )
    return event_id


def cancel_event(event_id: str) -> bool:
    """
    Cancela un evento existente.

    Returns:
        True si se canceló correctamente, False si no se encontró.

    --- REAL IMPLEMENTATION ---
    service = _get_calendar_service()
    try:
        service.events().delete(calendarId=GOOGLE_CALENDAR_ID, eventId=event_id).execute()
        return True
    except Exception:
        return False
    """
    if event_id not in _MOCK_EVENTS:
        logger.warning("[CALENDAR MOCK] cancel_event -> event_id '%s' NOT FOUND", event_id)
        return False

    event = _MOCK_EVENTS.pop(event_id)
    slot_key = event["slot"].start_dt.strftime("%Y-%m-%dT%H:%M")
    _MOCK_BOOKED.discard(slot_key)
    logger.info("[CALENDAR MOCK] cancel_event -> id=%s CANCELLED", event_id)
    return True


# ─── Google Auth helper (desactivado en modo mock) ────────────────────────────
# def _get_calendar_service():
#     from google.oauth2 import service_account
#     from googleapiclient.discovery import build
#     creds = service_account.Credentials.from_service_account_file(
#         GOOGLE_SERVICE_ACCOUNT_JSON,
#         scopes=["https://www.googleapis.com/auth/calendar"],
#     )
#     return build("calendar", "v3", credentials=creds)
