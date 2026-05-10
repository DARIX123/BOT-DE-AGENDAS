# BOT DE AGENDAS — Cerebro Central con IA

> Bot multi-plataforma (WhatsApp + Instagram) para agendamiento inteligente con NLP y Google Calendar.

---

## 🚀 Instalación Rápida

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env
# Edita .env con tus credenciales

# 4. Levantar el servidor
uvicorn app.main:app --reload --port 8000
```

Abre http://localhost:8000/docs para ver la documentación interactiva.

---

## 🧠 Arquitectura

```
[WhatsApp]  [Instagram]
     │            │
     ▼            ▼
[whatsapp_adapter.py]  [instagram_adapter.py]
           │
           ▼
       [brain.py]  ← CEREBRO CENTRAL
           │
    ┌──────┴──────┐
    ▼             ▼
[calendar_service.py]  [db_service.py]
           │
           ▼
    [reply_builder.py]
```

---

## 📁 Estructura del Proyecto

```
BOT-DE-AGENDAS/
├── app/
│   ├── main.py               # FastAPI — punto de entrada
│   ├── brain.py              # 🧠 Cerebro Central (NLP + orquestación)
│   ├── models.py             # Schemas Pydantic (Input/Output)
│   ├── reply_builder.py      # Textos de respuesta (bilingüe)
│   ├── calendar_service.py   # Google Calendar (mock → real)
│   ├── db_service.py         # Historial y citas (memoria → BD)
│   ├── config.py             # Variables de entorno
│   └── adapters/
│       ├── whatsapp_adapter.py   # 📱 Uriel trabaja aquí
│       └── instagram_adapter.py  # 📸 Misael trabaja aquí
├── tests/
│   └── test_brain.py         # Pruebas unitarias (14 tests)
├── .env.example
└── requirements.txt
```

---

## 🎯 Intenciones Detectadas

| Intent | Ejemplos MX | Ejemplos CA |
|---|---|---|
| `AGENDAR` | "quiero una cita", "agéndame" | "book an appointment", "I want a haircut" |
| `CONSULTAR_DISPONIBILIDAD` | "¿hay lugar?", "¿cuándo pueden?" | "do you have availability?" |
| `CANCELAR` | "ya no voy", "cancela mi cita" | "cancel my appointment" |
| `PRECIOS_SERVICIOS` | "¿cuánto cobran?" | "how much is a haircut?" |
| `HABLAR_HUMANO` | "quiero hablar con alguien" | "speak to an agent" |
| `DESCONOCIDA` | (cualquier otra cosa) | — |

---

## 🔌 Endpoints API

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/brain/process` | Test directo del cerebro |
| `GET/POST` | `/webhook/whatsapp` | Webhook de Meta (WhatsApp) |
| `GET/POST` | `/webhook/instagram` | Webhook de Instagram |
| `GET` | `/health` | Healthcheck |

### Ejemplo de llamada directa

```bash
curl -X POST http://localhost:8000/brain/process \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "+5215512345678",
    "platform": "whatsapp",
    "message_text": "Quiero agendar un corte mañana a las 4",
    "current_context": []
  }'
```

### Ejemplo de respuesta

```json
{
  "reply_text": "¡Listo! Ya quedaste agendad@ para *corte* el *lunes 11/05 a las 10:00 hrs*. 🙌",
  "action": "calendar_add",
  "metadata": {
    "intent": "AGENDAR",
    "service": "corte",
    "requested_datetime": "2026-05-11T10:00:00",
    "event_id": "abc123xyz",
    "confidence": 0.8,
    "raw_date_text": "mañana a las 4"
  },
  "suggested_slots": [],
  "needs_human_review": false
}
```

---

## 🧪 Pruebas

```bash
pip install pytest
pytest tests/ -v
```

---

## 🛠️ División de Trabajo

| Módulo | Responsable | Toca brain.py |
|---|---|---|
| `whatsapp_adapter.py` | **Uriel** | ❌ Nunca |
| `instagram_adapter.py` | **Misael** | ❌ Nunca |
| `brain.py` | Arquitecto IA | ✅ Cerebro |
| `calendar_service.py` | Backend | ✅ Swap mock→real |
| `reply_builder.py` | Copywriting | Sólo textos |

---

## 🔄 Roadmap

- [ ] Conectar Google Calendar real (descomentar en `calendar_service.py`)
- [ ] Integrar LLM (GPT-4o / Gemini) en `brain._llm_classify()`
- [ ] Agregar soporte para mensajes de audio (WhatsApp → Whisper STT)
- [ ] Base de datos persistente (SQLite / Firestore)
- [ ] Panel de administración para ver citas del día
