"""
models.py — Esquemas Pydantic para toda la aplicación.

Regla: NINGÚN otro módulo define sus propios modelos de datos.
Todo fluye a través de estas clases para garantizar consistencia.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────

class Platform(str, Enum):
    whatsapp = "whatsapp"
    instagram = "instagram"


class Locale(str, Enum):
    mx = "mx"   # México  — español, tono "de barrio pero educado"
    ca = "ca"   # Canadá  — inglés, tono amigable y directo


class Intent(str, Enum):
    AGENDAR = "AGENDAR"
    CONSULTAR_DISPONIBILIDAD = "CONSULTAR_DISPONIBILIDAD"
    CANCELAR = "CANCELAR"
    PRECIOS_SERVICIOS = "PRECIOS_SERVICIOS"
    HABLAR_HUMANO = "HABLAR_HUMANO"
    DESCONOCIDA = "DESCONOCIDA"


class Action(str, Enum):
    calendar_add = "calendar_add"           # Crear evento en Calendar
    calendar_check = "calendar_check"       # Sólo consultar disponibilidad
    calendar_cancel = "calendar_cancel"     # Cancelar evento existente
    db_save = "db_save"                     # Guardar datos en BD
    escalate_human = "escalate_human"       # Escalar a agente humano
    none = "none"                           # Sin acción de backend


# ─── Input ────────────────────────────────────────────────────────────────────

class ConversationTurn(BaseModel):
    """Un turno del historial de conversación."""
    role: str = Field(..., description="'user' o 'assistant'")
    content: str = Field(..., description="Texto del turno")
    timestamp: Optional[datetime] = None


class IncomingMessage(BaseModel):
    """
    Schema de entrada normalizado.
    Los adaptadores de WhatsApp e Instagram transforman sus payloads a este objeto.
    El cerebro SÓLO trabaja con IncomingMessage — nunca con payloads crudos.
    """
    user_id: str = Field(
        ...,
        description="Teléfono E.164 (WhatsApp) o IGSID/username (Instagram)"
    )
    platform: Platform
    message_text: str = Field(..., description="Texto crudo enviado por el cliente")
    current_context: list[ConversationTurn] = Field(
        default_factory=list,
        description="Historial reciente (máximo 10 turnos)"
    )
    locale: Optional[Locale] = Field(
        default=None,
        description="Si None, se autodetecta desde platform + user_id"
    )
    reference_datetime: Optional[datetime] = Field(
        default=None,
        description="Fecha/hora de referencia para parsear expresiones relativas. "
                    "Si None, se usa datetime.now() al momento del proceso."
    )


# ─── Calendar ─────────────────────────────────────────────────────────────────

class CalendarSlot(BaseModel):
    """Representa un espacio disponible en el calendario."""
    start_dt: datetime
    end_dt: datetime
    available: bool = True

    @property
    def label_mx(self) -> str:
        """Formato legible en español."""
        days = ["lunes", "martes", "miércoles", "jueves",
                "viernes", "sábado", "domingo"]
        day_name = days[self.start_dt.weekday()]
        return self.start_dt.strftime(f"{day_name} %d/%m a las %H:%M hrs")

    @property
    def label_ca(self) -> str:
        """Human-readable format in English."""
        return self.start_dt.strftime("%A %B %d at %I:%M %p")


# ─── Output ───────────────────────────────────────────────────────────────────

class ExtractedMetadata(BaseModel):
    """Datos estructurados extraídos del mensaje del cliente."""
    intent: Intent
    service: Optional[str] = Field(
        default=None,
        description="Servicio solicitado (corte, barba, consulta, etc.)"
    )
    requested_datetime: Optional[datetime] = Field(
        default=None,
        description="Fecha y hora normalizada solicitada por el cliente"
    )
    event_id: Optional[str] = Field(
        default=None,
        description="ID del evento de Calendar (para cancelaciones)"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confianza de la detección de intención (0-1)"
    )
    raw_date_text: Optional[str] = Field(
        default=None,
        description="Texto original de fecha/hora antes de normalizar"
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Datos adicionales libres para el backend"
    )


class BrainOutput(BaseModel):
    """
    Respuesta estándar del Cerebro Central.
    El router de cada plataforma toma este objeto y lo formatea
    para enviar al canal correcto (WhatsApp API, Instagram API).
    """
    reply_text: str = Field(..., description="Texto que se enviará al cliente")
    action: Action = Field(default=Action.none)
    metadata: ExtractedMetadata
    suggested_slots: list[CalendarSlot] = Field(
        default_factory=list,
        description="Slots sugeridos cuando el cliente no especificó hora"
    )
    needs_human_review: bool = Field(
        default=False,
        description="True si el cerebro no pudo resolver con confianza suficiente"
    )
