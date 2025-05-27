import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
#   Основные переменные окружения
# ──────────────────────────────────────────────────────────────────────────────
TOKEN:       str  = os.getenv("TINKOFF_TOKEN")
ACCOUNT_ID:  str  = os.getenv("TINKOFF_ACCOUNT_ID")      # как было в исходном коде
WATCHLIST:   Path = Path("figis_watchlist.txt")          # список FIGI по одной строке
DATA_DIR:    Path = Path("data")                         # папка для CSV-свечей
LOG_LEVEL:   str  = os.getenv("LOG_LEVEL", "INFO").upper()

# проверяем
if not TOKEN:
    raise EnvironmentError("В .env нет TINKOFF_TOKEN")
if not WATCHLIST.exists():
    raise FileNotFoundError(f"{WATCHLIST} not найден")

# список FIGI, готовый к использованию в любых модулях
FIGI_LIST = [l.strip() for l in WATCHLIST.read_text().splitlines() if l.strip()]

# даты и интервалы, которые используют сразу несколько модулей
HIST_START = datetime(2023, 1, 1, tzinfo=timezone.utc)
# Берём «сейчас» каждый раз динамически в коде
CANDLE_INTERVAL = "5m"          # человекочитаемый, а в коде маппим
MAX_CANDLES_PER_REQ = 1000      # лимит Tinkoff API
DATA_DIR.mkdir(exist_ok=True)