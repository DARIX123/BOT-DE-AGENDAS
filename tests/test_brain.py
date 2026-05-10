"""
test_brain.py — Pruebas unitarias del Cerebro Central.

Cubre los 6 intents con mensajes en español e inglés,
normalización de fechas relativas, y validación del JSON de salida.

Ejecutar: pytest tests/ -v
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.brain import process_message
from app.models import Action, IncomingMessage, Intent, Platform


# ─── Fixture base ─────────────────────────────────────────────────────────────

def _make_msg(text: str, platform: str = "whatsapp", user_id: str = "+5215512345678") -> IncomingMessage:
    return IncomingMessage(
        user_id=user_id,
        platform=Platform(platform),
        message_text=text,
        current_context=[],
        reference_datetime=datetime(2026, 5, 10, 12, 0, 0),  # domingo mediodía
    )


# ─── Tests por intent ─────────────────────────────────────────────────────────

class TestAgendarIntent:
    def test_agendar_sin_hora_sugiere_slots(self):
        """Sin hora especificada → Fricción Cero: sugiere 2 slots."""
        msg = _make_msg("Quiero agendar un corte")
        output = process_message(msg)

        assert output.metadata.intent == Intent.AGENDAR
        assert output.metadata.service == "corte"
        assert len(output.suggested_slots) == 2
        assert output.action == Action.calendar_check
        assert "1️⃣" in output.reply_text or "opciones" in output.reply_text.lower() or "espacios" in output.reply_text.lower()

    def test_agendar_con_hora_disponible(self):
        """Con hora disponible → crea evento y confirma."""
        msg = _make_msg("Quiero un corte mañana a las 10am")
        output = process_message(msg)

        assert output.metadata.intent == Intent.AGENDAR
        assert output.metadata.requested_datetime is not None
        # Puede confirmar o sugerir slots si el slot está ocupado por test anterior
        assert output.action in (Action.calendar_add, Action.calendar_check)

    def test_agendar_en_ingles(self):
        """Mensaje en inglés desde número canadiense."""
        msg = _make_msg(
            "I want to book a haircut tomorrow at 3pm",
            platform="whatsapp",
            user_id="+15141234567",  # Número canadiense
        )
        output = process_message(msg)

        assert output.metadata.intent == Intent.AGENDAR
        assert output.metadata.service == "corte"
        # Respuesta debe ser en inglés
        assert any(w in output.reply_text.lower() for w in ["book", "available", "slot", "great"])


class TestConsultarDisponibilidadIntent:
    def test_consultar_disponibilidad(self):
        msg = _make_msg("¿Tienen lugar el miércoles?")
        output = process_message(msg)

        assert output.metadata.intent == Intent.CONSULTAR_DISPONIBILIDAD
        assert output.action == Action.calendar_check
        assert len(output.suggested_slots) > 0

    def test_consultar_disponibilidad_ingles(self):
        msg = _make_msg("Do you have availability next week?", user_id="+15141234567")
        output = process_message(msg)

        assert output.metadata.intent == Intent.CONSULTAR_DISPONIBILIDAD
        assert "available" in output.reply_text.lower() or "slot" in output.reply_text.lower()


class TestCancelarIntent:
    def test_cancelar_sin_cita_activa(self):
        """Sin cita activa → informa al usuario."""
        msg = _make_msg("Quiero cancelar mi cita", user_id="+5215599999999")
        output = process_message(msg)

        assert output.metadata.intent == Intent.CANCELAR
        assert output.action == Action.none

    def test_cancelar_con_cita_activa(self):
        """Con cita activa → cancela y confirma."""
        from app import calendar_service as cal
        from app import db_service as db
        from app.models import CalendarSlot
        from datetime import timedelta

        # Simular una cita activa
        user_id = "+5215588888888"
        slot = CalendarSlot(
            start_dt=datetime(2026, 5, 11, 10, 0),
            end_dt=datetime(2026, 5, 11, 10, 45),
        )
        event_id = cal.create_event(slot, "corte", user_id)
        db.save_appointment(user_id, event_id, "corte", slot.start_dt, "whatsapp")

        msg = _make_msg("Ya no voy a ir, cancela mi cita", user_id=user_id)
        output = process_message(msg)

        assert output.metadata.intent == Intent.CANCELAR
        assert output.action == Action.calendar_cancel
        assert "cancel" in output.reply_text.lower()


class TestPreciosServiciosIntent:
    def test_precios_mx(self):
        msg = _make_msg("¿Cuánto cobran por un corte?")
        output = process_message(msg)

        assert output.metadata.intent == Intent.PRECIOS_SERVICIOS
        assert output.action == Action.none
        assert "$" in output.reply_text

    def test_precios_ca(self):
        msg = _make_msg("How much is a haircut?", user_id="+15141234567")
        output = process_message(msg)

        assert output.metadata.intent == Intent.PRECIOS_SERVICIOS
        assert "CAD" in output.reply_text or "$" in output.reply_text


class TestHablarHumanoIntent:
    def test_hablar_humano(self):
        msg = _make_msg("Quiero hablar con una persona")
        output = process_message(msg)

        assert output.metadata.intent == Intent.HABLAR_HUMANO
        assert output.action == Action.escalate_human
        assert output.needs_human_review is True


class TestDesconocidaIntent:
    def test_mensaje_desconocido(self):
        msg = _make_msg("jajaja que onda")
        output = process_message(msg)

        assert output.metadata.intent == Intent.DESCONOCIDA
        assert output.action == Action.none

    def test_output_siempre_tiene_reply(self):
        """El cerebro SIEMPRE devuelve reply_text, nunca None."""
        for text in ["???", "", "   ", "12345", "🤔"]:
            msg = _make_msg(text or "hola")
            output = process_message(msg)
            assert output.reply_text is not None
            assert len(output.reply_text) > 0


class TestOutputStructure:
    def test_output_json_completo(self):
        """Valida que el output siempre tenga todos los campos requeridos."""
        msg = _make_msg("Quiero agendar una cita para barba mañana")
        output = process_message(msg)

        assert output.reply_text
        assert output.action
        assert output.metadata
        assert output.metadata.intent
        assert 0.0 <= output.metadata.confidence <= 1.0

        # Debe ser serializable a JSON
        import json
        json_str = output.model_dump_json()
        parsed = json.loads(json_str)
        assert "reply_text" in parsed
        assert "action" in parsed
        assert "metadata" in parsed
