def calculate_commission(volume: float, rate: float = 0.005) -> float:
    """
    Рассчитывает комиссию за сделку.
    :param volume: Объем сделки.
    :param rate: Ставка комиссии (по умолчанию 0.1%).
    :return: Сумма комиссии.
    """
    return volume * rate

def apply_commission(price, quantity, category, commission_config) -> tuple:
    """
    Возвращает (чистая сумма, комиссия)
    """
    config = commission_config.get(category, commission_config["default"])
    gross = price * quantity
    commission = gross * config["rate"] + config["fixed"]
    net = gross - commission
    return net, commission

