import pytest
from commission_manager import calculate_commission, apply_commission

def test_calculate_commission():
    # Для order_value=100000, rate=0.001, fixed=5 -> комиссия должна быть 100+5=105
    commission = calculate_commission(100000, {"rate": 0.001, "fixed": 5})
    assert abs(commission - 105) < 1e-6

def test_apply_commission():
    net_value, commission = apply_commission(100, 10, "stocks", {"stocks": {"rate": 0.001, "fixed": 5}})
    # order_value = 1000, комиссия = 1+5=6, net_value = 994
    assert abs(net_value - 994) < 1e-6
    assert abs(commission - 6) < 1e-6
