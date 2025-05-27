from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import logging

from tinkoff.invest import Client, CandleInterval
from tinkoff.invest.services import Services

from config import (TOKEN, CANDLE_INTERVAL,
                    MAX_CANDLES_PER_REQ, DATA_DIR, LOG_LEVEL)

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
#   Контекстный менеджер
# ──────────────────────────────────────────────────────────────────────────────
class MarketData:
    def __enter__(self) -> Services:
        self._client = Client(TOKEN)
        return self._client
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._client.__exit__(exc_type, exc_val, exc_tb)

# ──────────────────────────────────────────────────────────────────────────────
#   Генератор свечей c обходом лимита 1000
# ──────────────────────────────────────────────────────────────────────────────
_INTERVAL_MAP = {
    "1m":  CandleInterval.CANDLE_INTERVAL_1_MIN,
    "5m":  CandleInterval.CANDLE_INTERVAL_5_MIN,
    "15m": CandleInterval.CANDLE_INTERVAL_15_MIN,
    "1h":  CandleInterval.CANDLE_INTERVAL_HOUR,
    "1d":  CandleInterval.CANDLE_INTERVAL_DAY,
}

def iter_candles_paged(
    md: Services,
    figi: str,
    dt_from: datetime,
    dt_to: datetime,
    interval: str = CANDLE_INTERVAL,
):
    """Yield-ит свечи подряд, пока не дойдём до dt_to (не включительно)."""
    ivl = _INTERVAL_MAP[interval]
    while dt_from < dt_to:
        resp = md.market_data.get_candles(
            figi=figi,
            from_=dt_from,
            to=dt_to,
            interval=ivl,
        )
        candles = resp.candles
        if not candles:
            break
        yield from candles
        dt_from = candles[-1].time + timedelta(seconds=1)
        if len(candles) < MAX_CANDLES_PER_REQ:
            break

# ──────────────────────────────────────────────────────────────────────────────
#   CSV-хранилище
# ──────────────────────────────────────────────────────────────────────────────
def csv_path(figi: str) -> Path:
    return DATA_DIR / f"{figi}_5m.csv"

def last_ts_in_csv(path: Path):
    """Читаем последнюю строку, возвращаем datetime или None."""
    try:
        *_, last = path.read_text().splitlines()
        return datetime.fromisoformat(last.split(",")[0])
    except Exception:
        return None

def save_append_csv(figi: str, candles_iter):
    """Создаёт csv или добавляет новые строки без дублирования."""
    path = csv_path(figi)
    mode = "a" if path.exists() else "w"
    wrote = 0

    with open(path, mode, newline="") as f:
        w = csv.writer(f)
        if mode == "w":
            w.writerow(["time", "open", "high", "low", "close", "vol"])
        for c in candles_iter:
            w.writerow([
                c.time.isoformat(),
                c.open.units + c.open.nano / 1e9,
                c.high.units + c.high.nano / 1e9,
                c.low.units + c.low.nano / 1e9,
                c.close.units + c.close.nano / 1e9,
                c.volume,
            ])
            wrote += 1
    return wrote

__all__ = [
    "MarketData",
    "iter_candles_paged",
    "csv_path",          # ← экспортируем
    "last_ts_in_csv",
    "save_append_csv",
]