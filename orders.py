from tinkoff.invest import OrderDirection, OrderType

async def open_position(client, user_state, figi, size, signal):
    direction = OrderDirection.ORDER_DIRECTION_BUY if signal == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
    order = await client.orders.post_order(
        figi=figi,
        quantity=size,
        direction=direction,
        order_type=OrderType.ORDER_TYPE_MARKET,
        account_id=user_state.account_id
    )
    user_state.logger.info(f"✅ Ордер {signal} размещён по {figi}, OrderID: {order.order_id}")
    user_state.position = size
    user_state.entry_price = None  # можно потом обновлять по последней цене

async def close_position(client, user_state, figi, reason):
    if not user_state.position:
        return

    close_direction = OrderDirection.ORDER_DIRECTION_SELL if user_state.position > 0 else OrderDirection.ORDER_DIRECTION_BUY
    await client.orders.post_order(
        figi=figi,
        quantity=abs(user_state.position),
        direction=close_direction,
        order_type=OrderType.ORDER_TYPE_MARKET,
        account_id=user_state.account_id
    )
    user_state.logger.info(f"🚪 Позиция по {figi} закрыта ({reason})")
    user_state.position = None
    user_state.entry_price = None
