"""
reply_builder.py — Constructor de mensajes de respuesta con tono correcto.

Reglas de tono:
  - Locale.mx : español mexicano, cercano, "de barrio pero educado"
  - Locale.ca : inglés canadiense, amigable y directo

Ningún texto de usuario final se escribe fuera de este módulo.
"""
from __future__ import annotations

from app.models import CalendarSlot, Intent, Locale

# ─── Catálogo de servicios (personalizable) ───────────────────────────────────
SERVICES_MX = """
✂️ *Servicios disponibles:*
• Corte de cabello — $120
• Barba completa — $80
• Corte + barba — $180
• Tinte / decoloración — desde $250
• Tratamiento capilar — $200
"""

SERVICES_CA = """
✂️ *Available Services:*
• Haircut — $25 CAD
• Beard trim — $20 CAD
• Haircut + beard — $40 CAD
• Color / bleach — from $65 CAD
• Hair treatment — $50 CAD
"""


# ─── Builders por intención ───────────────────────────────────────────────────

def build_reply(
    intent: Intent,
    locale: Locale,
    slots: list[CalendarSlot] | None = None,
    service: str | None = None,
    requested_dt_label: str | None = None,
    event_id: str | None = None,
    extra: dict | None = None,
) -> str:
    """
    Devuelve el texto listo para enviar al cliente.

    Args:
        intent: Intención detectada.
        locale: Mercado (mx / ca).
        slots: Slots sugeridos (cuando no especificó hora).
        service: Servicio solicitado (si se detectó).
        requested_dt_label: Fecha/hora formateada en lenguaje natural.
        event_id: ID del evento (para mensajes de confirmación/cancelación).
        extra: Datos adicionales del contexto.
    """
    builder_map = {
        Intent.AGENDAR: _reply_agendar,
        Intent.CONSULTAR_DISPONIBILIDAD: _reply_disponibilidad,
        Intent.CANCELAR: _reply_cancelar,
        Intent.PRECIOS_SERVICIOS: _reply_precios,
        Intent.HABLAR_HUMANO: _reply_humano,
        Intent.DESCONOCIDA: _reply_desconocida,
    }
    builder = builder_map.get(intent, _reply_desconocida)
    return builder(
        locale=locale,
        slots=slots or [],
        service=service,
        requested_dt_label=requested_dt_label,
        event_id=event_id,
        extra=extra or {},
    )


# ─── Builders individuales ────────────────────────────────────────────────────

def _reply_agendar(
    locale: Locale,
    slots: list[CalendarSlot],
    service: str | None,
    requested_dt_label: str | None,
    event_id: str | None,
    extra: dict,
) -> str:
    svc = service or ("un servicio" if locale == Locale.mx else "a service")

    # Slot ya confirmado
    if event_id and requested_dt_label:
        if locale == Locale.mx:
            return (
                f"✅ ¡Listo! Ya quedaste agendad@ para *{svc}* el "
                f"*{requested_dt_label}*. 🙌\n\n"
                "Si necesitas cancelar o cambiar tu cita, solo avísame. "
                "¡Te esperamos!"
            )
        return (
            f"✅ All set! Your *{svc}* is booked for "
            f"*{requested_dt_label}*. 🙌\n\n"
            "Need to cancel or reschedule? Just let me know. See you then!"
        )

    # Pedir confirmación con slots sugeridos
    if slots:
        if locale == Locale.mx:
            opciones = "\n".join(
                f"  {i+1}️⃣ {s.label_mx}" for i, s in enumerate(slots)
            )
            return (
                f"¡Perfecto, con gusto te agendamos para *{svc}*! 😎\n\n"
                "Tenemos estos espacios libres ahorita:\n"
                f"{opciones}\n\n"
                "¿Cuál te late más? Responde con el número. 👇"
            )
        opciones = "\n".join(
            f"  {i+1}️⃣ {s.label_ca}" for i, s in enumerate(slots)
        )
        return (
            f"Great! I'd love to book you in for *{svc}*. 😎\n\n"
            "Here are the next available slots:\n"
            f"{opciones}\n\n"
            "Which one works for you? Reply with the number. 👇"
        )

    # Slot específico solicitado — pedir confirmación
    if locale == Locale.mx:
        return (
            f"Checando disponibilidad para *{svc}* el "
            f"*{requested_dt_label or 'la fecha que mencionas'}*... 🔍\n"
            "Dame un momento. 🙏"
        )
    return (
        f"Checking availability for *{svc}* on "
        f"*{requested_dt_label or 'the date you mentioned'}*... 🔍\n"
        "One moment please. 🙏"
    )


def _reply_disponibilidad(
    locale: Locale,
    slots: list[CalendarSlot],
    **_,
) -> str:
    if not slots:
        if locale == Locale.mx:
            return "Ahorita estamos llenos 😅 pero si me dices otro día lo checamos."
        return "We're fully booked right now 😅 but let me know another day and I'll check!"

    if locale == Locale.mx:
        opciones = "\n".join(f"  • {s.label_mx}" for s in slots)
        return (
            "¡Sí hay lugar! 🙌 Estos son los próximos espacios libres:\n"
            f"{opciones}\n\n"
            "¿Te acomoda alguno?"
        )
    opciones = "\n".join(f"  • {s.label_ca}" for s in slots)
    return (
        "We have availability! 🙌 Here are the next open slots:\n"
        f"{opciones}\n\n"
        "Does any of those work for you?"
    )


def _reply_cancelar(
    locale: Locale,
    event_id: str | None,
    extra: dict,
    **_,
) -> str:
    cancelled = extra.get("cancelled", False)

    if cancelled:
        if locale == Locale.mx:
            return (
                "✅ Tu cita quedó cancelada. Si en otro momento quieres "
                "agendar de nuevo, aquí estamos. 🙌"
            )
        return (
            "✅ Your appointment has been cancelled. "
            "Whenever you're ready to book again, we're here! 🙌"
        )

    if extra.get("no_appointment"):
        if locale == Locale.mx:
            return "Hmm, no encontré ninguna cita activa para ti. ¿Quieres agendar una nueva? 😊"
        return "Hmm, I couldn't find an active appointment for you. Would you like to book one? 😊"

    if locale == Locale.mx:
        return "Voy a cancelar tu cita, dame un segundo... ⏳"
    return "Let me cancel your appointment, one second... ⏳"


def _reply_precios(locale: Locale, **_) -> str:
    if locale == Locale.mx:
        return SERVICES_MX + "\n¿Te interesa agendar alguno? 😊"
    return SERVICES_CA + "\nWould you like to book any of these? 😊"


def _reply_humano(locale: Locale, **_) -> str:
    if locale == Locale.mx:
        return (
            "Claro, ahora mismo le aviso a alguien del equipo para que "
            "te atienda personalmente. 🙏 Un momento..."
        )
    return (
        "Of course! I'll connect you with a team member right away. "
        "One moment please... 🙏"
    )


def _reply_desconocida(locale: Locale, **_) -> str:
    if locale == Locale.mx:
        return (
            "Mmm, no entendí bien lo que necesitas 😅 "
            "¿Quieres *agendar* una cita, saber los *precios*, o algo más? "
            "Dime y con gusto te ayudo. 😊"
        )
    return (
        "Hmm, I'm not sure I caught that 😅 "
        "Are you looking to *book* an appointment, check *prices*, or something else? "
        "Let me know and I'll be happy to help! 😊"
    )
