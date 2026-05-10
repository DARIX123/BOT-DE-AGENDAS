"""
instagram_adapter.py — Adaptador para Instagram Messaging API (Meta).

Responsabilidades:
  1. Verificar el webhook (GET) con el verify_token
  2. Parsear mensajes de Instagram y convertirlos en IncomingMessage
  3. Enviar la respuesta usando la Instagram Messaging API

Misael trabaja aquí. La lógica central (brain.py) no se toca.

Diferencias con WhatsApp:
  - user_id es un IGSID (Instagram-Scoped ID), NO un número de teléfono
  - El locale se infiere por idioma detectado (defecto: mx)
  - El endpoint de envío es diferente (me/messages)
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request 

from app.brain import process_message
from app.config import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_VERIFY_TOKEN
from app.db_service import get_context
from app.models import IncomingMessage, Platform

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook/instagram", tags=["Instagram"])

GRAPH_API_URL = "https://graph.facebook.com/v19.0"


# ─── Verificación del Webhook ─────────────────────────────────────────────────

@router.get(
    "",
    summary="Verificación del webhook de Instagram (Meta)",
)
async def instagram_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
):
    if hub_mode == "subscribe" and hub_verify_token == INSTAGRAM_VERIFY_TOKEN:
        logger.info("Instagram webhook verificado ✅")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verify token inválido")


# ─── Recepción de Mensajes ────────────────────────────────────────────────────

@router.post(
    "",
    summary="Recibe mensajes entrantes de Instagram",
)
async def instagram_webhook(request: Request):
    body: dict[str, Any] = await request.json()
    logger.debug("Instagram payload: %s", body)

    try:
        entry = body["entry"][0]
        messaging = entry["messaging"][0]

        sender_id: str = messaging["sender"]["id"]      # IGSID del usuario
        message_obj: dict = messaging.get("message", {})
        message_text: str = message_obj.get("text", "")

        if not message_text:
            logger.info("Mensaje sin texto de IG %s — ignorando", sender_id)
            return {"status": "no_text"}

        # Recuperar historial
        context = get_context(sender_id)

        # Normalizar a IncomingMessage
        incoming = IncomingMessage(
            user_id=sender_id,
            platform=Platform.instagram,
            message_text=message_text,
            current_context=context,
        )

        # Procesar con el Cerebro Central
        output = process_message(incoming)

        # Enviar respuesta vía Instagram Messaging API
        await _send_instagram_message(sender_id, output.reply_text)

        return {
            "status": "processed",
            "action": output.action,
            "intent": output.metadata.intent,
        }

    except (KeyError, IndexError) as exc:
        logger.error("Error parseando payload de Instagram: %s", exc)
        raise HTTPException(status_code=400, detail="Payload inválido") from exc


# ─── Envío de Mensajes ────────────────────────────────────────────────────────

async def _send_instagram_message(recipient_id: str, text: str) -> None:
    """Envía un mensaje de texto al usuario usando la Instagram Messaging API."""
    url = f"{GRAPH_API_URL}/me/messages"
    headers = {
        "Authorization": f"Bearer {INSTAGRAM_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error(
                "Error enviando mensaje Instagram: %s %s", resp.status_code, resp.text
            )
        else:
            logger.info("Mensaje enviado a IGSID=%s ✅", recipient_id)
