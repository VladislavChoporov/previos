import asyncio
import logging
from datetime import datetime, timedelta

from market_data import get_candles
from strategy import enhanced_strategy
from orders import open_position, close_position
from instruments import get_market_instruments
from user_state import user_states

async def trading_loop(message):
    """
    Основной торговый цикл.
    """
    user_id = message.from_user.id
    user_state = user_states.get(user_id)

    if not user_state:
        logger.error(f"Пользователь {user_id} не найден в user_states.")
        return

    if not hasattr(user_state, "logger"):
        user_state.logger = logging.getLogger(f"UserState_{user_id}")
        user_state.logger.setLevel(logging.INFO)

    user_state.logger.info("🔄 Цикл торговли начался")

    while user_state.active:
        try:
            instruments = await get_market_instruments(user_state)
            if not instruments:
                user_state.logger.warning("⚠️ Нет доступных инструментов для торговли.")
                await asyncio.sleep(60)
                continue

            for instrument in instruments:
                figi = instrument["figi"]
                ticker = instrument["ticker"]
                lot = instrument["lot"]

                user_state.logger.info(f"🔎 Проверка актива: {ticker} ({figi})")

                from_date = datetime.utcnow() - timedelta(days=30)
                to_date = datetime.utcnow()
                interval = "1hour"

                candles = await get_candles(user_state.client, figi, from_date, to_date, interval)

                if not isinstance(candles, list) or not candles or len(candles) < 10:
                    user_state.logger.warning(f"⚠️ Некорректные или недостаточные данные по {ticker}, пропускаем.")
                    continue

                signal = enhanced_strategy(candles)
                last_price = candles[-1]["close"]

                if user_state.position and user_state.entry_price:
                    change = (last_price - user_state.entry_price) / user_state.entry_price
                    user_state.logger.info(f"📈 Текущая прибыль/убыток: {change:.2%}")

                    if change >= 0.05:
                        await close_position(user_state.client, user_state, figi, "PROFIT")
                        user_state.logger.info(f"✅ Позиция по {ticker} закрыта с прибылью.")
                        continue
                    elif change <= -0.02:
                        await close_position(user_state.client, user_state, figi, "LOSS")
                        user_state.logger.info(f"❌ Позиция по {ticker} закрыта с убытком.")
                        continue

                if signal == "buy" and not user_state.position:
                    await open_position(user_state.client, user_state, figi, lot, "BUY")
                    user_state.logger.info(f"📥 Открыта позиция 'buy' по {ticker}.")

                elif signal == "sell" and not user_state.position:
                    await open_position(user_state.client, user_state, figi, lot, "SELL")
                    user_state.logger.info(f"📥 Открыта позиция 'sell' по {ticker}.")

            await asyncio.sleep(60)

        except Exception as e:
            user_state.logger.error(f"Ошибка в торговом цикле: {e}")
            await asyncio.sleep(60)

__all__ = ["trading_loop"]
