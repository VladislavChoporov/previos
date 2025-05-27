import asyncio
import logging
from datetime import datetime, timedelta, timezone

from tinkoff.invest import CandleInterval

from market_data import get_candles, get_figi_by_ticker
from strategy import enhanced_strategy
from risk_management import calc_max_qty, pnl_with_fee
from portfolio_manager import rebalance_portfolio
from orders import open_position, close_position
from config import MOEXBMI_TICKERS

logger = logging.getLogger("trade_loop")
logger.setLevel(logging.INFO)


async def load_existing_portfolio(user_state):
    """
    Заполняем user_state.positions & entry_prices при старте.
    """
    portfolio = await user_state.client.operations.get_portfolio(account_id=user_state.account_id)
    user_state.positions = {}
    user_state.entry_prices = {}
    for p in portfolio.positions:
        if p.figi and p.quantity.units != 0:
            user_state.positions[p.figi] = p.quantity.units
            user_state.entry_prices[p.figi] = (
                p.average_position_price.units + p.average_position_price.nano / 1e9
            )
    logger.info(f"📂 Загрузили портфель: {user_state.positions}")


async def trading_loop(user_state, sleep_sec: int = 60):
    if not user_state:
        logger.error("❌ user_state не передан")
        return

    if not getattr(user_state, "positions", None):
        await load_existing_portfolio(user_state)

    user_state.active = True
    user_state.logger = logging.getLogger(f"UserState_{id(user_state)}")
    user_state.logger.setLevel(logging.INFO)

    while user_state.active:
        try:
            to_dt = datetime.now(timezone.utc)
            from_dt = to_dt - timedelta(days=7)

            for ticker in MOEXBMI_TICKERS:
                figi = await get_figi_by_ticker(user_state.client, ticker)
                if not figi:
                    continue

                candles = await get_candles(
                    user_state.client,
                    figi,
                    from_dt,
                    to_dt,
                    CandleInterval.CANDLE_INTERVAL_HOUR,
                )
                if len(candles) < 20:
                    continue

                signal, score = enhanced_strategy(candles, return_score=True)
                last_price = candles[-1]["close"]

                # --- P/L контроль & SL/TP ---
                if figi in user_state.positions:
                    pos_qty = user_state.positions[figi]
                    dir_ = "long" if pos_qty > 0 else "short"
                    pnl = pnl_with_fee(
                        user_state.entry_prices[figi], last_price, abs(pos_qty), "share", dir_
                    )
                    pnl_pct = pnl / (abs(pos_qty) * user_state.entry_prices[figi])

                    # реверс при убытке > 0.5 %
                    if pnl_pct <= -0.005:
                        await close_position(user_state.client, user_state, figi, reason="REVERSAL")
                        # открываем противоположно
                        qty = abs(pos_qty)
                        await open_position(
                            user_state.client,
                            user_state,
                            figi,
                            qty,
                            "sell" if dir_ == "long" else "buy",
                        )
                        continue

                # --- open / close по сигналу ---
                if signal == "buy":
                    if figi in user_state.positions and user_state.positions[figi] > 0:
                        continue  # уже лонг
                    qty = await calc_max_qty(
                        user_state.client,
                        user_state.account_id,
                        figi,
                        last_price,
                        score,
                    )
                    if qty == 0:
                        continue
                    # если не хватает кэша — ребаланс
                    freed = await rebalance_portfolio(user_state, last_price * qty)
                    if freed < last_price * qty * 0.9:  # всё равно мало
                        continue
                    await open_position(user_state.client, user_state, figi, qty, "buy")

                elif signal == "sell":
                    if figi in user_state.positions and user_state.positions[figi] < 0:
                        continue  # уже шорт
                    qty = await calc_max_qty(
                        user_state.client,
                        user_state.account_id,
                        figi,
                        last_price,
                        score,
                    )
                    if qty == 0:
                        continue
                    freed = await rebalance_portfolio(user_state, last_price * qty)
                    if freed < last_price * qty * 0.9:
                        continue
                    await open_position(user_state.client, user_state, figi, qty, "sell")

            await asyncio.sleep(sleep_sec)

        except Exception as exc:
            logger.exception(f"❌ Ошибка торгового цикла: {exc}")
            await asyncio.sleep(sleep_sec)