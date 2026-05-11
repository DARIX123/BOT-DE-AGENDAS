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

import os

from app.brain import process_message
from app.config import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_VERIFY_TOKEN

INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "me")
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
        # 1. Obtener la entrada (entry)
        entries = body.get("entry", [])
        if not entries:
            return {"status": "no_entry"}
        
        entry = entries[0]
        
        # 2. Buscar el evento de mensaje (Meta puede enviarlo en 'messaging' o en 'changes')
        messaging_list = entry.get("messaging")
        
        if messaging_list:
            event = messaging_list[0]
        else:
            # Si no hay 'messaging', intentamos buscar en 'changes'
            changes = entry.get("changes", [])
            if changes:
                event = changes[0].get("value", {})
            else:
                logger.info("Webhook recibido sin datos de mensaje reconocibles")
                return {"status": "unknown_format"}

        # 3. Extraer datos del remitente y el texto
        sender_id: str = event.get("sender", {}).get("id")
        message_obj: dict = event.get("message", {})
        message_text: str = message_obj.get("text", "")

        if not sender_id or not message_text:
            logger.info("Evento incompleto de IG — ignorando")
            return {"status": "incomplete_event"}

        # Recuperar historial
        context = get_context(sender_id)

        # Normalizar a IncomingMessage
        incoming = IncomingMessage(
            user_id=sender_id,
            platform=Platform.instagram,
            message_text=message_text,
            current_context=context,
        )

        # Procesar con el Cerebro Central (brain.py)
        output = process_message(incoming)

        # Enviar respuesta vía Instagram Messaging API
        await _send_instagram_message(sender_id, output.reply_text)

        return {
            "status": "processed",
            "action": output.action,
            "intent": output.metadata.intent,
        }

    except Exception as exc:
        logger.error("Error procesando webhook de Instagram: %s", exc)
        # Cambiamos a 200 para que Meta no marque error de servidor mientras pruebas
        return {"status": "error", "detail": str(exc)}

# ─── Envío de Mensajes ────────────────────────────────────────────────────────

async def _send_instagram_message(recipient_id: str, text: str) -> None:
    """Envía un mensaje de texto al usuario usando la Instagram Messaging API."""
    url = f"{GRAPH_API_URL}/{INSTAGRAM_ACCOUNT_ID}/messages"
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