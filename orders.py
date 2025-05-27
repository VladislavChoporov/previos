import logging
from typing import Optional

from tinkoff.invest import OrderDirection, OrderType

from market_data import get_last_price
from risk_management import dynamic_sl_tp

logger = logging.getLogger("orders")
logger.setLevel(logging.INFO)


async def open_position(
    client,
    user_state,
    figi: str,
    qty: int,
    signal: str,
    instrument_type: str = "share",
):
    """
    Открывает long (BUY) или short (SELL) в зависимости от `signal`.
    Проверка маржинальных лимитов — в calling‑code (risk_management).
    """
    if qty <= 0:
        logger.warning("⚠️ qty == 0 → ордер не отправляем.")
        return

    direction = (
        OrderDirection.ORDER_DIRECTION_BUY if signal == "buy" else OrderDirection.ORDER_DIRECTION_SELL
    )

    order = await client.orders.post_order(
        figi=figi,
        quantity=qty,
        direction=direction,
        order_type=OrderType.ORDER_TYPE_MARKET,
        account_id=user_state.account_id,
    )
    logger.info(f"✅ Открыт ордер {signal.upper()} {figi} ×{qty}, id={order.order_id}")

    # --- обновляем user_state ---
    last_price = await get_last_price(client, figi)
    entry_prices = getattr(user_state, "entry_prices", {})
    entry_prices[figi] = last_price
    user_state.entry_prices = entry_prices

    positions = getattr(user_state, "positions", {})
    positions[figi] = positions.get(figi, 0) + (qty if signal == "buy" else -qty)
    user_state.positions = positions

    # --- вычисляем SL/TP ---
    sl, tp = await dynamic_sl_tp(client, figi, last_price, "long" if signal == "buy" else "short")
    logger.info(f"🎯 SL={sl:.2f}, TP={tp:.2f} установлены для {figi}")

    # TODO: здесь можно разместить стоп‑ордера через sandboxStopOrders (если нужно).


async def close_position(
    client,
    user_state,
    figi: str,
    reason: str = "",
    qty_override: Optional[int] = None,
):
    """
    Закрывает позицию целиком (или qty_override) противоположным ордером.
    """
    qty_current = user_state.positions.get(figi, 0)
    if qty_current == 0:
        logger.warning(f"⚠️ Нет позиции по {figi} для закрытия.")
        return

    qty = abs(qty_current) if qty_override is None else qty_override
    direction = (
        OrderDirection.ORDER_DIRECTION_SELL if qty_current > 0 else OrderDirection.ORDER_DIRECTION_BUY
    )

    await client.orders.post_order(
        figi=figi,
        quantity=qty,
        direction=direction,
        order_type=OrderType.ORDER_TYPE_MARKET,
        account_id=user_state.account_id,
    )
    logger.info(f"🚪 Позиция по {figi} ×{qty} закрыта ({reason})")

    # чистим стейт
    user_state.positions.pop(figi, None)
    user_state.entry_prices.pop(figi, None)