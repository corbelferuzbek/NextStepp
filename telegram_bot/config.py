import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_IDS = tuple(
    int(value.strip())
    for value in os.getenv("OWNER_ID", "0").split(",")
    if value.strip().isdigit() and int(value.strip()) > 0
)
OWNER_ID = OWNER_IDS[0] if OWNER_IDS else 0
DB_PATH = os.getenv("DB_PATH", "bot.db")


TZ_OFFSET_HOURS = int(os.getenv("TZ_OFFSET_HOURS", "5"))


AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_MODEL = os.getenv("AI_MODEL", "llama-3.1-8b-instant")

AI_REASONING_EFFORT = os.getenv("AI_REASONING_EFFORT", "").strip()


SITE_API_KEY = os.getenv("SITE_API_KEY", "")
NEXTSTEP_API_URL = os.getenv("NEXTSTEP_API_URL", "").rstrip("/")
NEXTSTEP_API_KEY = os.getenv("NEXTSTEP_API_KEY", "")
BOT_PORT = int(os.getenv("BOT_PORT", "8080"))
PORT = BOT_PORT  # backwards compatibility


REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "").strip()

CHANNEL_LINK = os.getenv("CHANNEL_LINK", "").strip()

ANNOUNCE_CHANNEL = os.getenv("ANNOUNCE_CHANNEL", "").strip()
