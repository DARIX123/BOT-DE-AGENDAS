"""
whatsapp_adapter.py — Adaptador para Meta Cloud API (WhatsApp Business).

Responsabilidades:
  1. Verificar el webhook (GET) con el verify_token
  2. Parsear el payload entrante (POST) y convertirlo en IncomingMessage
  3. Enviar la respuesta usando la Cloud API de Meta

Uriel trabaja aquí. La lógica central (brain.py) no se toca.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from app.brain import process_message
from app.config import WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN
from app.db_service import get_context
from app.models import IncomingMessage, Platform

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/whatsapp", tags=["WhatsApp"])

GRAPH_API_URL = "https://graph.facebook.com/v19.0"


# ─── Verificación del Webhook ─────────────────────────────────────────────────

@router.get(
    "",
    summary="Verificación del webhook de WhatsApp (Meta)",
    description="Meta llama este endpoint con hub.challenge para verificar el webhook.",
)
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
):
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verificado ✅")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verify token inválido")


# ─── Recepción de Mensajes ────────────────────────────────────────────────────

@router.post(
    "",
    summary="Recibe mensajes entrantes de WhatsApp",
)
async def whatsapp_webhook(request: Request):
    body: dict[str, Any] = await request.json()
    logger.debug("WhatsApp payload: %s", body)

    try:
        entry = body["entry"][0]
        change = entry["changes"][0]["value"]

        # Ignorar notificaciones que no son mensajes (ej. status updates)
        if "messages" not in change:
            return {"status": "ignored"}

        message = change["messages"][0]
        user_id: str = message["from"]                          # Número E.164
        message_text: str = message.get("text", {}).get("body", "")

        if not message_text:
            logger.info("Mensaje sin texto (imagen/audio) de %s — ignorando", user_id)
            return {"status": "no_text"}

        # Recuperar historial de conversación
        context = get_context(user_id)

        # Crear mensaje normalizado para el cerebro
        incoming = IncomingMessage(
            user_id=user_id,
            platform=Platform.whatsapp,
            message_text=message_text,
            current_context=context,
        )

        # Procesar con el Cerebro Central
        output = process_message(incoming)

        # Enviar respuesta al cliente vía Meta Cloud API
        await _send_whatsapp_message(user_id, output.reply_text)

        return {
            "status": "processed",
            "action": output.action,
            "intent": output.metadata.intent,
        }

    except (KeyError, IndexError) as exc:
        logger.error("Error parseando payload de WhatsApp: %s", exc)
        raise HTTPException(status_code=400, detail="Payload inválido") from exc


# ─── Envío de Mensajes ────────────────────────────────────────────────────────

async def _send_whatsapp_message(to: str, text: str) -> None:
    """Envía un mensaje de texto usando la Meta Cloud API."""
    url = f"{GRAPH_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error("Error enviando mensaje WhatsApp: %s %s", resp.status_code, resp.text)
        else:
            logger.info("Mensaje enviado a %s ✅", to)
