"""
config.py — Configuración centralizada desde variables de entorno.
Todos los módulos importan desde aquí. Nunca se escriben secretos en código.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ─── Google Calendar ──────────────────────────────────────────────────────────
GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials/service_account.json"
)

# ─── WhatsApp ─────────────────────────────────────────────────────────────────
WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")

# ─── Instagram ────────────────────────────────────────────────────────────────
INSTAGRAM_VERIFY_TOKEN: str = os.getenv("INSTAGRAM_VERIFY_TOKEN", "")
INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

# ─── Horario de Negocio ───────────────────────────────────────────────────────
_open_days_raw = os.getenv("BUSINESS_OPEN_DAYS", "0,1,2,3,4,5")
BUSINESS_OPEN_DAYS: list[int] = [int(d) for d in _open_days_raw.split(",")]
BUSINESS_OPEN_HOUR: int = int(os.getenv("BUSINESS_OPEN_HOUR", "9"))
BUSINESS_CLOSE_HOUR: int = int(os.getenv("BUSINESS_CLOSE_HOUR", "20"))
DEFAULT_SLOT_MINUTES: int = int(os.getenv("DEFAULT_SLOT_MINUTES", "45"))

# ─── App ──────────────────────────────────────────────────────────────────────
APP_ENV: str = os.getenv("APP_ENV", "development")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
