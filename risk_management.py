from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple

from tinkoff.invest import CandleInterval

from config import CONFIG
from market_data import get_last_price, get_candles

from notifications import send_notification     


logger = logging.getLogger("risk_management")
logger.setLevel(logging.INFO)

# ─────────────────────────── параметры из config ────────────────────────────
RISK_PER_TRADE: float   = CONFIG.get("risk_per_trade", 0.02)
DAILY_LOSS_LIMIT: float = CONFIG.get("daily_loss_limit", 0.10)

FREE_CASH_MIN_PCT: float = 0.05            # кэш‑подушка
COMMISSION_PCT: Dict[str, float] = {"share": 0.0005, "future": 0.0004}

ATR_PERIOD: int       = 14
SL_ATR_MULT: float    = 1.5
TP_ATR_MULT: float    = 3.0
TRAILING_STEP_ATR: float = 0.5
# ─────────────────────────────────────────────────────────────────────────────


# ──────────── утилиты капитала / комиссии ────────────
async def available_cash_rub(client, account_id: str) -> float:
    attrs = await client.users.get_margin_attributes(account_id=account_id)
    return attrs.available_liquidity.units + attrs.available_liquidity.nano / 1e9


def commission(value_rub: float, instrument_type: str = "share") -> float:
    return value_rub * COMMISSION_PCT.get(instrument_type, 0.0005)


def pnl_with_fee(entry: float, exit_: float, qty: int,
                 instrument_type: str, direction: str) -> float:
    gross = (exit_ - entry) * qty if direction == "long" else (entry - exit_) * qty
    fee = commission(entry * qty, instrument_type) + commission(exit_ * qty, instrument_type)
    return gross - fee


async def calc_max_qty(
    client, account_id: str, figi: str, price: float, score: float
) -> int:
    """Сколько лотов можем открыть под сигнал «score ∈ [0;1]»."""
    free_cash = await available_cash_rub(client, account_id)
    alloc_cash = free_cash * (1 - FREE_CASH_MIN_PCT) * score
    return max(int(math.floor(alloc_cash / price)), 0) if alloc_cash > 0 else 0


# ──────────── ATR, SL‑/‑TP и трейлинг‑стоп ────────────
async def _atr(client, figi: str, period: int = ATR_PERIOD) -> float:
    to_dt = datetime.now(timezone.utc)
    from_dt = to_dt - timedelta(hours=period + 5)
    candles = await get_candles(client, figi, from_dt, to_dt,
                                CandleInterval.CANDLE_INTERVAL_HOUR)
    if len(candles) < period + 1:
        return 0.0

    true_ranges = [
        max(c["high"] - c["low"],
            abs(c["high"] - candles[i - 1]["close"]),
            abs(c["low"]  - candles[i - 1]["close"]))
        for i, c in enumerate(candles[1:], start=1)
    ]
    return sum(true_ranges[-period:]) / period


async def dynamic_sl_tp(
    client, figi: str, entry_price: float, direction: str
) -> Tuple[float, float]:
    atr_val = await _atr(client, figi)
    if atr_val == 0:
        return entry_price * 0.995, entry_price * 1.005  # fallback ±0.5 %
    sign = 1 if direction == "long" else -1
    sl = entry_price - sign * SL_ATR_MULT * atr_val
    tp = entry_price + sign * TP_ATR_MULT * atr_val
    return sl, tp


async def update_trailing_stop(
    client,
    figi: str,
    current_ts: float,
    direction: str,
    step_atr: float = TRAILING_STEP_ATR,
) -> float:
    """Подтягивает стоп в сторону прибыли (не «ослабляя» его)."""
    last = await get_last_price(client, figi)
    atr_val = await _atr(client, figi)
    if last is None or atr_val == 0:
        return current_ts

    if direction == "long":
        return max(current_ts, last - step_atr * atr_val)
    else:
        return min(current_ts, last + step_atr * atr_val)


# ──────────── главный хаус‑кипер позиции ────────────
async def check_risk_management(
    client,
    user_state,
    figi: str,
    close_position_func,
) -> None:
    """
    Проверяется на каждом тике для уже открытой позиции.
    Закрывает / реверсирует, если выполнены условия.
    """
    try:
        last_price = await get_last_price(client, figi)
        if user_state.position:                                # позиция ещё жива
            # 1) подтягиваем трейлинг‑стоп
            ts_old = getattr(user_state.position, "trailing_stop", 0.0)
            side = "long" if user_state.position.size > 0 else "short"
            user_state.position.trailing_stop = await update_trailing_stop(
                client, figi, ts_old, side
            )

            # 2) проверяем низкую эффективность
            entry = user_state.position.entry_price
            profit_pct = (last_price - entry) / entry if side == "long" \
                         else (entry - last_price) / entry

            alive_h = (
                (datetime.now(timezone.utc) - user_state.position.open_time
                 ).total_seconds() / 3600
                if user_state.position.open_time else 0
            )
            if alive_h >= CONFIG.get("max_position_duration_hours", 3) and profit_pct < 0.002:
                logger.info("⏰ >3 ч и <0.2 % прибыли → закрываем позицию.")
                await close_position_func(client, user_state, figi, "TIMEOUT_LOW_PROFIT")
                return

            # 3) дневной лимит убытка
            if user_state.start_of_day_balance > 0:
                loss_pct = (user_state.start_of_day_balance - user_state.balance) / \
                           user_state.start_of_day_balance
                if loss_pct >= DAILY_LOSS_LIMIT:
                    logger.warning("🚨 Дневной лимит убытка достигнут!")
                    await close_position_func(client, user_state, figi, "DAILY_LOSS_LIMIT")
                    return
                if loss_pct >= 0.30:                             # 30 % — стоп‑машина
                    await send_notification(
                        user_state.chat_id,
                        "❌ Критический убыток! Торговля остановлена.",
                        "ALERT",
                    )
                    user_state.active = False
                    await close_position_func(client, user_state, figi, "CRITICAL_STOP")
                    return

            # 4) тейк‑профит
            tp_price = user_state.position.take_profit
            if (side == "long" and last_price >= tp_price) or \
               (side == "short" and last_price <= tp_price):
                logger.info("🏆 TP достигнут — закрываем позицию.")
                await close_position_func(client, user_state, figi, "TAKE_PROFIT")
                if user_state.position is None:                  # позицию закрыли
                    await auto_reverse_position(client, user_state, figi)
                return
    except Exception as exc:
        logger.exception(f"❌ Ошибка risk_management: {exc}")