import pytest
import asyncio
import types
from market_data import get_last_price, money_value_to_float, get_balance

class DummyPrice:
    def __init__(self, units, nano):
        self.units = units
        self.nano = nano

class DummyLastPrice:
    def __init__(self, price):
        self.price = price

class DummyMarketData:
    async def get_last_prices(self, figi):
        dummy_price = DummyPrice(100, 500000000)
        last_price_obj = DummyLastPrice(dummy_price)
        return types.SimpleNamespace(last_prices=[last_price_obj])

class DummyOperations:
    async def get_withdraw_limits(self, account_id):
        MoneyValue = types.SimpleNamespace(units=1000, nano=0)
        return types.SimpleNamespace(money=[MoneyValue], blocked=[], blocked_guarantee=[])
    async def get_portfolio(self, account_id):
        MoneyValue = types.SimpleNamespace(units=1000, nano=0)
        return types.SimpleNamespace(money=[MoneyValue], positions=[])

class DummyClient:
    def __init__(self):
        self.market_data = DummyMarketData()
        self.operations = DummyOperations()

@pytest.mark.asyncio
async def test_get_last_price():
    client = DummyClient()
    price = await get_last_price(client, "dummy_figi")
    assert abs(price - 100.5) < 0.001

def test_money_value_to_float():
    dummy_value = types.SimpleNamespace(units=123, nano=450000000)
    result = money_value_to_float(dummy_value)
    assert abs(result - (123 + 0.45)) < 0.001

@pytest.mark.asyncio
async def test_get_balance():
    client = DummyClient()
    balance = await get_balance(client)
    assert abs(balance - 1000) < 0.001
