def calculate_commission(volume: float, rate: float = 0.005) -> float:
    """
    Рассчитывает комиссию за сделку.
    :param volume: Объем сделки.
    :param rate: Ставка комиссии (по умолчанию 0.1%).
    :return: Сумма комиссии.
    """
    return volume * rate

def apply_commission(price, quantity, instrument_category, config):
    """
    Вычисляет чистую стоимость ордера после учета комиссии.
    price: цена за единицу.
    quantity: количество.
    instrument_category: категория инструмента ('stocks', 'precious_metals', 'currency').
    config: параметры комиссии из конфигурации.
    Returns: (net_value, commission)
    """
    order_value = price * quantity
    commission_config = config.get(instrument_category, config.get("default"))
    commission = calculate_commission(order_value, commission_config)
    net_value = order_value - commission
    return net_value, commission

