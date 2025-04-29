def calculate_commission(order_value, config):
    """
    Рассчитывает комиссию для ордера.
    order_value: суммарная стоимость ордера.
    config: словарь с параметрами комиссии (например, rate и fixed).
    """
    rate = config.get("rate", 0.0)
    fixed = config.get("fixed", 0.0)
    commission = order_value * rate + fixed
    commission = round(commission, 2)
    return max(commission, 0.01)

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
