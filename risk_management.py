import asyncio
import logging
import numpy as np
from datetime import datetime, timezone
from market_data import get_last_price, get_atr
from config import CONFIG

logger = logging.getLogger("risk_management")
RISK_PER_TRADE = CONFIG["risk_per_trade"]
ATR_MULTIPLIER = CONFIG["atr_multiplier"]
DAILY_LOSS_LIMIT = CONFIG.get("daily_loss_limit", 0.1)  # 10% дневной убыток

async def calculate_position_size(client, user_state, figi: str) -> int:
    try:
        last_price = await get_last_price(client, figi)
        atr = await get_atr(client, figi)
        if last_price <= 0 or atr <= 0:
            return 1
        leverage = CONFIG.get("leverage", 1)
        risk_amount = user_state.balance * leverage * RISK_PER_TRADE
        raw_size = risk_amount / (atr * last_price)
        lot_size = user_state.instrument_info.get("lot", 1)
        size = int(raw_size / lot_size)
        return max(size, 1)
    except Exception as e:
        logger.error(f"Ошибка расчета размера позиции: {e}")
        return 1

async def update_trailing_stop(client, user_state, figi: str):
    try:
        atr = await get_atr(client, figi)
        current_price = await get_last_price(client, figi)

        if user_state.position:
            steps = user_state.position.steps if hasattr(user_state.position, 'steps') else 0
            if user_state.position.size > 0:
                new_tp = user_state.position.entry_price + atr * (3 + min(steps * 0.5, 2))
                new_sl = max(user_state.position.stop_loss, current_price - atr * 2)
                if new_tp > user_state.position.take_profit:
                    logger.info(f"📈 Обновление тейк-профита (LONG): {user_state.position.take_profit} → {new_tp}")
                    user_state.position.take_profit = new_tp
                if new_sl > user_state.position.stop_loss:
                    logger.info(f"🔻 Обновление стоп-лосса (LONG): {user_state.position.stop_loss} → {new_sl}")
                    user_state.position.stop_loss = new_sl

            elif user_state.position.size < 0:
                new_tp = user_state.position.entry_price - atr * (3 + min(steps * 0.5, 2))
                new_sl = min(user_state.position.stop_loss, current_price + atr * 2)
                if new_tp < user_state.position.take_profit:
                    logger.info(f"📉 Обновление тейк-профита (SHORT): {user_state.position.take_profit} → {new_tp}")
                    user_state.position.take_profit = new_tp
                if new_sl < user_state.position.stop_loss:
                    logger.info(f"🔺 Обновление стоп-лосса (SHORT): {user_state.position.stop_loss} → {new_sl}")
                    user_state.position.stop_loss = new_sl

    except Exception as e:
        logger.error(f"Ошибка трейлинг-стопа: {e}")

async def set_dynamic_stop_loss(client, user_state, figi: str):
    """
    Устанавливает динамический стоп-лосс, адаптирующийся к волатильности.
    """
    try:
        atr = await get_atr(client, figi)
        if user_state.position:
            if user_state.position.size > 0:
                dynamic_sl = user_state.position.entry_price - atr * ATR_MULTIPLIER
                logger.info(f"Устанавливаем динамический стоп-лосс (LONG): {dynamic_sl}")
                user_state.position.stop_loss = dynamic_sl
            else:
                dynamic_sl = user_state.position.entry_price + atr * ATR_MULTIPLIER
                logger.info(f"Устанавливаем динамический стоп-лосс (SHORT): {dynamic_sl}")
                user_state.position.stop_loss = dynamic_sl
    except Exception as e:
        logger.error(f"Ошибка установки динамического стоп-лосса: {e}")

async def check_risk_management(client, user_state, figi: str, close_position_func, partial_close_func):
    try:
        current_price = await get_last_price(client, figi)
        await update_trailing_stop(client, user_state, figi)

        if user_state.position:
            if user_state.position.size > 0:
                profit_pct = (current_price - user_state.position.entry_price) / user_state.position.entry_price
            else:
                profit_pct = (user_state.position.entry_price - current_price) / user_state.position.entry_price

            now_dt = datetime.now(timezone.utc)
            duration_hours = (now_dt - user_state.position.open_time).total_seconds() / 3600.0 if user_state.position.open_time else 0
            
            if duration_hours >= CONFIG.get("max_position_duration_hours", 3) and profit_pct < 0.002:
                logger.info("Позиция неэффективна (меньше 0.2% прибыли за 3 часа), закрываем")
                await close_position_func(client, user_state, figi, "TIMEOUT_LOW_PROFIT")
                return

            current_balance = user_state.balance
            start_balance = user_state.start_of_day_balance
            loss_pct = (start_balance - current_balance) / start_balance

            if start_balance > 0 and loss_pct >= DAILY_LOSS_LIMIT:
                logger.warning(f"⚠️ Дневной лимит убытка {DAILY_LOSS_LIMIT*100:.1f}% достигнут! Закрываю все позиции.")
                await close_position_func(client, user_state, figi, "DAILY_LOSS_LIMIT")
                return
            
            if start_balance > 0 and loss_pct >= 0.3:
                await send_notification(user_state.chat_id, "❌ Критический убыток! Все позиции закрыты.", "ALERT")  
                logger.critical("❌ КРИТИЧЕСКИЙ УБЫТОК! Закрываю ВСЕ позиции и останавливаю торговлю.")
                await close_position_func(client, user_state, figi, "CRITICAL_STOP")
                user_state.active = False  
                return

            if user_state.position.size > 0 and current_price >= user_state.position.take_profit:
                logger.info("✅ Достигнут тейк-профит, закрываем позицию")
                await close_position_func(client, user_state, figi, "TAKE_PROFIT")
                if user_state.position is None:
                    await auto_reverse_position(client, user_state, figi)
                return
            elif user_state.position.size < 0 and current_price <= user_state.position.take_profit:
                logger.info("✅ Достигнут тейк-профит, закрываем позицию")
                await close_position_func(client, user_state, figi, "TAKE_PROFIT")
                if user_state.position is None:
                    await auto_reverse_position(client, user_state, figi)
                return
    except Exception as e:
        logger.error(f"Ошибка риск-менеджмента: {e}")

async def auto_reverse_position(client, user_state, figi: str):
    """Переворачивает позицию после закрытия, если тренд сменился."""
    try:
        new_direction = "BUY" if user_state.position and user_state.position.size < 0 else "SELL"
        new_size = await calculate_position_size(client, user_state, figi)
        
        if new_size > 0:
            logger.info(f"🔄 Автоматический переворот позиции: {new_direction} {new_size} лотов на {figi}")
            success = await place_order(client, figi, new_direction, new_size, user_state)
            if success:
                await send_notification(user_state.chat_id, f"🔄 Позиция перевернута: {new_direction} {new_size} лотов")
    except Exception as e:
        logger.error(f"Ошибка переворота позиции: {e}")
