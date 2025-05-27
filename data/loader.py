from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from tinkoff.invest import CandleInterval, Client, HistoricCandle  # type: ignore

_CSV_DIR = Path(__file__).resolve().parent.parent / "candles"
logger = logging.getLogger("tradebot.data.loader")


async def _fetch_api(
    client: Client,
    figi: str,
    start: datetime,
    end: datetime,
    interval: CandleInterval = CandleInterval.CANDLE_INTERVAL_5_MIN,
) -> list[HistoricCandle]:
    """Asynchronous wrapper around blocking SDK call using `asyncio.to_thread`."""

    def _blocking_call() -> list[HistoricCandle]:
        return list(
            client.get_all_candles(
                figi=figi,
                from_=start,
                to=end,
                interval=interval,
            )
        )

    candles: list[HistoricCandle] = await asyncio.to_thread(_blocking_call)
    return candles


def _candles_to_df(candles: list[HistoricCandle]) -> pd.DataFrame:
    data = [
        {
            "time": c.time,
            "open": c.open.units + c.open.nano / 1e9,
            "high": c.high.units + c.high.nano / 1e9,
            "low": c.low.units + c.low.nano / 1e9,
            "close": c.close.units + c.close.nano / 1e9,
            "volume": c.volume,
        }
        for c in candles
    ]
    return pd.DataFrame(data).set_index("time")


async def load_candles(
    ticker: str,
    start: datetime,
    end: datetime,
    source: Literal["local", "api"] = "local",
    api_client: Optional[Client] = None,
) -> pd.DataFrame:
    """Return candle DataFrame for a ticker within the given period.

    *Local* ‑‑ reads from CSV (fast, offline).  If the CSV is missing ‑ falls
    back to *api* automatically.
    """
    if source == "local":
        csv_path = _CSV_DIR / f"{ticker}.csv"
        try:
            df = pd.read_csv(csv_path, parse_dates=["time"], index_col="time")
            mask = (df.index >= start) & (df.index <= end)
            return df.loc[mask]
        except FileNotFoundError:
            logger.warning("CSV for %s not found → switching to API", ticker)
            source = "api"  # fallthrough

    if source == "api":
        if api_client is None:
            raise ValueError("api_client is required when source='api'")
        candles = await _fetch_api(api_client, ticker, start, end)
        return _candles_to_df(candles)

    raise ValueError(f"Unknown source: {source}")