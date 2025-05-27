import logging
from typing import Dict, List, Tuple

from market_data import get_last_price
from orders import close_position

logger = logging.getLogger("portfolio_manager")
logger.setLevel(logging.INFO)


async def get_portfolio_value(client, positions: Dict[str, int]) -> float:
    value = 0.0
    for figi, qty in positions.items():
        last = await get_last_price(client, figi)
        value += last * qty
    return value


async def rebalance_portfolio(user_state, cash_needed: float) -> float:
    """
    Освобождает cash_needed рублей, закрывая позиции с худшим P/L.
    Возвращает сколько реально освободили.
    """
    if not getattr(user_state, "positions", None):
        return 0.0

    pnl_list: List[Tuple[str, float]] = []  # [(figi, pnl), …]
    for figi, qty in user_state.positions.items():
        last = await get_last_price(user_state.client, figi)
        pnl = (last - user_state.entry_prices[figi]) * qty
        pnl_list.append((figi, pnl))

    # сортируем по прибыли (возрастающей), т.е. сначала закрываем убыточные
    pnl_list.sort(key=lambda x: x[1])

    freed = 0.0
    for figi, _ in pnl_list:
        if freed >= cash_needed:
            break
        logger.info(f"⚖️  Rebalance: закрываем {figi} для освобождения кэша")
        qty_current = user_state.positions.get(figi, 0)       # запоминаем ДО закрытия
        await close_position(
            user_state.client, user_state, figi,
            reason="REBALANCE", qty_override=abs(qty_current)
        )
        last = await get_last_price(user_state.client, figi)
        freed += last * abs(qty_current)
        user_state.positions.pop(figi, None)                  # удаляем один раз
        user_state.entry_prices.pop(figi, None)

    logger.info(f"💸 Освобождено {freed:,.2f} ₽ денег")
    return freed