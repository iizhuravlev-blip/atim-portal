"""Настройки центральной страницы из переменных окружения."""
import os
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


DATA_DIR = Path(_env("DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))
DB_PATH = Path(_env("DB_PATH", str(DATA_DIR / "portal.db")))
BASE_URL = _env("BASE_URL", "https://upr.atimlab.ru").rstrip("/")

# Вход: sed — единый вход через СЭД (/sso?client=portal); dev — выбор сотрудника без пароля, только для разработки
AUTH_MODE = _env("AUTH_MODE", "dev")
SECRET_KEY = _env("SECRET_KEY", "dev-secret-change-me")
SSO_SECRET = _env("SSO_SECRET")
COOKIE_SECURE = _env("COOKIE_SECURE", "0") == "1"

# СЭД: справочник сотрудников и виджеты docs.mail / docs.tasks (токен модуля portal в DIRECTORY_TOKENS СЭД)
SED_URL = _env("SED_URL", "https://docs.atimlab.ru").rstrip("/")          # адрес для браузера
SED_API_URL = _env("SED_API_URL", SED_URL).rstrip("/")                    # адрес для сервера (внутри Docker)
SED_TOKEN = _env("SED_TOKEN")

# CRM: виджет crm.tasks (PORTAL_TOKEN в .env CRM)
CRM_URL = _env("CRM_URL", "https://crm.atimlab.ru").rstrip("/")
CRM_API_URL = _env("CRM_API_URL", CRM_URL).rstrip("/")
CRM_TOKEN = _env("CRM_TOKEN")

# Групповой бот: виджеты bot.today / bot.tasks — пусто, пока у бота нет /api/v1/widget
BOT_API_URL = _env("BOT_API_URL").rstrip("/")
BOT_TOKEN = _env("BOT_TOKEN")

TENDER_URL = _env("TENDER_URL", "https://tender.atimlab.ru").rstrip("/")

TIMEOUT = float(_env("WIDGET_TIMEOUT", "3"))
CACHE_SECONDS = int(_env("WIDGET_CACHE", "60"))
