"""
brain.py — Cerebro Central del Bot de Agendas.

Es el único módulo que orquesta: NLP → Validación → Acción → Respuesta.
Nunca sabe si el mensaje viene de WhatsApp o Instagram.
Nunca maneja HTTP, webhooks, ni formatos de plataforma.

Arquitectura de procesamiento:
  1. _detect_locale()      — detecta idioma/mercado
  2. _detect_intent()      — clasifica la intención del mensaje
  3. _extract_datetime()   — normaliza fecha/hora (con dateparser)
  4. _extract_service()    — detecta el servicio solicitado
  5. _orchestrate()        — aplica reglas de negocio y llama servicios
  6. Devuelve BrainOutput  — listo para cualquier plataforma
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import dateparser

import app.calendar_service as calendar_svc
import app.db_service as db_svc
from app.models import (
    Action,
    BrainOutput,
    ExtractedMetadata,
    IncomingMessage,
    Intent,
    Locale,
)
from app.reply_builder import build_reply

logger = logging.getLogger(__name__)

# ─── Tabla de palabras clave por intención ────────────────────────────────────
_INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.AGENDAR: [
        "agendar", "agenda", "cita", "reservar", "reserva", "quiero un",
        "quiero una", "necesito", "book", "appointment", "schedule",
        "puedo ir", "me puedo anotar", "me apunto", "anótame",
    ],
    Intent.CONSULTAR_DISPONIBILIDAD: [
        "disponible", "disponibilidad", "hay lugar", "tienen lugar",
        "hay espacio", "cuándo", "cuando puedo", "qué días", "que dias",
        "available", "availability", "open slots", "free", "when can",
    ],
    Intent.CANCELAR: [
        "cancelar", "cancela", "cancel", "ya no voy", "no voy a ir",
        "no puedo ir", "borrar cita", "quitar cita", "desagendar",
    ],
    Intent.PRECIOS_SERVICIOS: [
        "precio", "precios", "cuánto", "cuanto", "costo", "costos",
        "cuánto cobran", "cuánto sale", "servicios", "qué servicios",
        "price", "prices", "cost", "how much", "services", "what do you offer",
    ],
    Intent.HABLAR_HUMANO: [
        "hablar con", "quiero hablar", "persona", "humano", "human",
        "agent", "agente", "alguien", "staff", "speak to",
    ],
}

# ─── Tabla de servicios detectables ───────────────────────────────────────────
_SERVICE_KEYWORDS: dict[str, list[str]] = {
    "corte": ["corte", "pelo", "cabello", "haircut", "hair cut", "trim"],
    "barba": ["barba", "beard", "rasurar", "bigote"],
    "corte_barba": ["corte y barba", "todo", "full", "completo", "haircut and beard"],
    "tinte": ["tinte", "color", "decolorar", "decoloración", "bleach", "dye"],
    "tratamiento": ["tratamiento", "treatment", "keratina", "keratin", "hidratación"],
}

# ─── Detección de locale ──────────────────────────────────────────────────────
_CA_AREA_CODES = {"1"}  # Prefijos de teléfono de Canadá/EE.UU. (simplificado)


def _detect_locale(msg: IncomingMessage) -> Locale:
    """
    Detecta el locale del usuario.
    Prioridad: 1. Campo explícito  2. Código de área  3. Platform default (mx)
    """
    if msg.locale:
        return msg.locale

    # Si es WhatsApp, el user_id es el número E.164 (ej. +15141234567 = Canadá)
    if msg.platform.value == "whatsapp":
        user_id = msg.user_id.lstrip("+")
        if user_id.startswith("1") and len(user_id) == 11:
            return Locale.ca

    # Default: México
    return Locale.mx


# ─── Clasificación de intención ───────────────────────────────────────────────

def _detect_intent(text: str) -> tuple[Intent, float]:
    """
    Clasifica la intención del texto mediante keyword matching.

    Returns:
        (Intent, confidence) donde confidence ∈ [0, 1].

    Hook LLM: Si quieres usar GPT-4o / Gemini, sustituye este método.
    El contrato de retorno no cambia.
    """
    text_lower = text.lower()
    scores: dict[Intent, int] = {intent: 0 for intent in Intent}

    for intent, keywords in _INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[intent] += 1

    best_intent = max(scores, key=lambda i: scores[i])
    best_score = scores[best_intent]

    if best_score == 0:
        return Intent.DESCONOCIDA, 0.3

    confidence = min(0.5 + (best_score * 0.15), 1.0)
    logger.debug("Intent scores: %s | best=%s conf=%.2f", scores, best_intent, confidence)
    return best_intent, confidence


# ─── Extracción de fecha/hora ─────────────────────────────────────────────────

# Regex para capturar expresiones de fecha/hora antes de pasarlas a dateparser
_DT_PATTERN = re.compile(
    r"""
    (?:
        (?:el\s+)?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)
        |mañana|pasado\s+mañana|hoy|tomorrow|today|next\s+\w+
        |(?:en\s+)?\d+\s+d[ií]as?
        |\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?
        |\d{1,2}\s+de\s+\w+
    )
    (?:\s+(?:a\s+las?\s+)?\d{1,2}(?::\d{2})?(?:\s*(?:am|pm|hrs?))?)?
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _extract_datetime(
    text: str,
    locale: Locale,
    reference_dt: Optional[datetime] = None,
) -> tuple[Optional[datetime], Optional[str]]:
    """
    Extrae y normaliza fecha/hora del texto.

    Returns:
        (datetime normalizado, texto original capturado) o (None, None)
    """
    match = _DT_PATTERN.search(text)
    raw_text = match.group(0).strip() if match else text

    languages = ["es"] if locale == Locale.mx else ["en"]
    settings: dict = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    if reference_dt:
        settings["RELATIVE_BASE"] = reference_dt

    parsed = dateparser.parse(raw_text, languages=languages, settings=settings)

    if parsed:
        logger.debug("Parsed datetime: '%s' -> %s", raw_text, parsed)
        return parsed, raw_text

    logger.debug("dateparser could not parse: '%s'", raw_text)
    return None, None


# ─── Extracción de servicio ───────────────────────────────────────────────────

def _extract_service(text: str) -> Optional[str]:
    """Detecta el servicio solicitado por keyword matching."""
    text_lower = text.lower()
    for service_id, keywords in _SERVICE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return service_id
    return None


# ─── Orquestación principal ───────────────────────────────────────────────────

def _orchestrate(
    intent: Intent,
    confidence: float,
    locale: Locale,
    msg: IncomingMessage,
    requested_dt: Optional[datetime],
    raw_date_text: Optional[str],
    service: Optional[str],
) -> BrainOutput:
    """
    Aplica las reglas de negocio según la intención detectada.
    Llama a calendar_service y db_service según corresponda.
    """

    # ── Baja confianza → escalar ──────────────────────────────────────────────
    if confidence < 0.4 and intent == Intent.DESCONOCIDA:
        reply = build_reply(Intent.DESCONOCIDA, locale)
        return BrainOutput(
            reply_text=reply,
            action=Action.none,
            metadata=ExtractedMetadata(
                intent=intent, confidence=confidence,
                service=service, requested_datetime=requested_dt,
            ),
            needs_human_review=True,
        )

    # ── AGENDAR ───────────────────────────────────────────────────────────────
    if intent == Intent.AGENDAR:
        # REGLA: No confirmar sin verificar disponibilidad
        if requested_dt:
            is_available = calendar_svc.check_availability(requested_dt)
            if is_available:
                # Crear el evento
                slots = [
                    calendar_svc.CalendarSlot(
                        start_dt=requested_dt,
                        end_dt=requested_dt.replace(
                            minute=requested_dt.minute
                            + __import__("app.config", fromlist=["DEFAULT_SLOT_MINUTES"])
                            .DEFAULT_SLOT_MINUTES % 60
                        ),
                    )
                ]
                slot = slots[0]
                from app.config import DEFAULT_SLOT_MINUTES
                from datetime import timedelta
                slot = calendar_svc.CalendarSlot(
                    start_dt=requested_dt,
                    end_dt=requested_dt + timedelta(minutes=DEFAULT_SLOT_MINUTES),
                )
                event_id = calendar_svc.create_event(
                    slot=slot,
                    service=service or "servicio",
                    user_id=msg.user_id,
                )
                db_svc.save_appointment(
                    user_id=msg.user_id,
                    event_id=event_id,
                    service=service or "servicio",
                    start_dt=requested_dt,
                    platform=msg.platform.value,
                )
                label = slot.label_mx if locale == Locale.mx else slot.label_ca
                reply = build_reply(
                    intent=Intent.AGENDAR,
                    locale=locale,
                    service=service,
                    requested_dt_label=label,
                    event_id=event_id,
                )
                return BrainOutput(
                    reply_text=reply,
                    action=Action.calendar_add,
                    metadata=ExtractedMetadata(
                        intent=intent,
                        service=service,
                        requested_datetime=requested_dt,
                        event_id=event_id,
                        confidence=confidence,
                        raw_date_text=raw_date_text,
                    ),
                )
            else:
                # Slot ocupado → sugerir alternativos (Fricción Cero)
                slots = calendar_svc.get_next_slots(2, from_dt=requested_dt)
                reply = build_reply(
                    intent=Intent.AGENDAR,
                    locale=locale,
                    slots=slots,
                    service=service,
                )
                return BrainOutput(
                    reply_text=reply,
                    action=Action.calendar_check,
                    metadata=ExtractedMetadata(
                        intent=intent,
                        service=service,
                        requested_datetime=requested_dt,
                        confidence=confidence,
                        raw_date_text=raw_date_text,
                    ),
                    suggested_slots=slots,
                )
        else:
            # REGLA: Sin hora → sugerir 2 slots (Fricción Cero)
            slots = calendar_svc.get_next_slots(2)
            reply = build_reply(
                intent=Intent.AGENDAR,
                locale=locale,
                slots=slots,
                service=service,
            )
            return BrainOutput(
                reply_text=reply,
                action=Action.calendar_check,
                metadata=ExtractedMetadata(
                    intent=intent,
                    service=service,
                    confidence=confidence,
                ),
                suggested_slots=slots,
            )

    # ── CONSULTAR DISPONIBILIDAD ──────────────────────────────────────────────
    if intent == Intent.CONSULTAR_DISPONIBILIDAD:
        slots = calendar_svc.get_next_slots(3, from_dt=requested_dt)
        reply = build_reply(Intent.CONSULTAR_DISPONIBILIDAD, locale, slots=slots)
        return BrainOutput(
            reply_text=reply,
            action=Action.calendar_check,
            metadata=ExtractedMetadata(
                intent=intent,
                requested_datetime=requested_dt,
                confidence=confidence,
            ),
            suggested_slots=slots,
        )

    # ── CANCELAR ──────────────────────────────────────────────────────────────
    if intent == Intent.CANCELAR:
        appointment = db_svc.get_appointment(msg.user_id)
        if not appointment:
            reply = build_reply(
                Intent.CANCELAR, locale, extra={"no_appointment": True}
            )
            return BrainOutput(
                reply_text=reply,
                action=Action.none,
                metadata=ExtractedMetadata(intent=intent, confidence=confidence),
            )

        event_id = appointment["event_id"]
        cancelled = calendar_svc.cancel_event(event_id)
        if cancelled:
            db_svc.delete_appointment(msg.user_id)
        reply = build_reply(
            Intent.CANCELAR,
            locale,
            event_id=event_id,
            extra={"cancelled": cancelled},
        )
        return BrainOutput(
            reply_text=reply,
            action=Action.calendar_cancel if cancelled else Action.none,
            metadata=ExtractedMetadata(
                intent=intent,
                event_id=event_id,
                confidence=confidence,
                extra={"cancelled": cancelled},
            ),
        )

    # ── PRECIOS / SERVICIOS ───────────────────────────────────────────────────
    if intent == Intent.PRECIOS_SERVICIOS:
        reply = build_reply(Intent.PRECIOS_SERVICIOS, locale)
        return BrainOutput(
            reply_text=reply,
            action=Action.none,
            metadata=ExtractedMetadata(intent=intent, confidence=confidence),
        )

    # ── HABLAR CON HUMANO ─────────────────────────────────────────────────────
    if intent == Intent.HABLAR_HUMANO:
        reply = build_reply(Intent.HABLAR_HUMANO, locale)
        return BrainOutput(
            reply_text=reply,
            action=Action.escalate_human,
            metadata=ExtractedMetadata(intent=intent, confidence=confidence),
            needs_human_review=True,
        )

    # ── DESCONOCIDA ───────────────────────────────────────────────────────────
    reply = build_reply(Intent.DESCONOCIDA, locale)
    return BrainOutput(
        reply_text=reply,
        action=Action.none,
        metadata=ExtractedMetadata(intent=intent, confidence=confidence),
    )


# ─── Punto de entrada público ─────────────────────────────────────────────────

def process_message(msg: IncomingMessage) -> BrainOutput:
    """
    Punto de entrada único del Cerebro Central.

    Recibe un IncomingMessage (normalizado por cualquier adaptador de plataforma)
    y devuelve un BrainOutput listo para enviar al cliente.

    Args:
        msg: Mensaje normalizado (WhatsApp / Instagram / cualquier plataforma futura)

    Returns:
        BrainOutput con reply_text, action y metadata.
    """
    logger.info(
        "process_message | user=%s platform=%s text='%s'",
        msg.user_id, msg.platform, msg.message_text[:80],
    )

    # 1. Guardar turno del usuario en historial
    db_svc.save_turn(msg.user_id, role="user", content=msg.message_text)

    # 2. Detectar locale
    locale = _detect_locale(msg)

    # 3. Detectar intención
    intent, confidence = _detect_intent(msg.message_text)

    # 4. Extraer fecha/hora
    reference_dt = msg.reference_datetime or datetime.now()
    requested_dt, raw_date_text = _extract_datetime(
        msg.message_text, locale, reference_dt
    )

    # 5. Extraer servicio
    service = _extract_service(msg.message_text)

    # 6. Orquestar respuesta
    output = _orchestrate(
        intent=intent,
        confidence=confidence,
        locale=locale,
        msg=msg,
        requested_dt=requested_dt,
        raw_date_text=raw_date_text,
        service=service,
    )

    # 7. Guardar respuesta del asistente en historial
    db_svc.save_turn(msg.user_id, role="assistant", content=output.reply_text)

    logger.info(
        "process_message | intent=%s action=%s confidence=%.2f",
        output.metadata.intent, output.action, output.metadata.confidence,
    )
    return output
