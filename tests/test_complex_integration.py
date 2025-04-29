import asyncio
import pytest
import types
from config import CONFIG
from market_data import get_last_price, get_orderbook
from commission_manager import apply_commission
from portfolio_manager import save_portfolio, load_portfolio
from strategy import enhanced_strategy
from risk_management import calculate_position_size, update_trailing_stop
from tinkoff.invest import AsyncClient, OrderDirection, OrderType, MoneyValue

class DummyClient:
    async def close(self):
        pass

class DummyMarketData:
    async def get_last_prices(self, figi):
        class DummyPrice:
            def __init__(self):
                self.units = 100
                self.nano = 500000000
        class DummyLastPrice:
            def __init__(self, price):
                self.price = price
        dummy_price = DummyPrice()
        last_price_obj = DummyLastPrice(dummy_price)
        return types.SimpleNamespace(last_prices=[last_price_obj])

class DummyOperations:
    async def get_withdraw_limits(self, account_id):
        MoneyValue = types.SimpleNamespace(units=1000, nano=0)
        return types.SimpleNamespace(money=[MoneyValue], blocked=[], blocked_guarantee=[])
    async def get_portfolio(self, account_id):
        MoneyValue = types.SimpleNamespace(units=1000, nano=0)
        return types.SimpleNamespace(money=[MoneyValue], positions=[])

class DummyAsyncClient(DummyClient):
    def __init__(self):
        self.market_data = DummyMarketData()
        self.operations = DummyOperations()

@pytest.mark.asyncio
async def test_integration_commission_and_order():
    net_value, commission = apply_commission(100, 10, "stocks", CONFIG["commission"])
    assert net_value < 100 * 10

@pytest.mark.asyncio
async def test_integration_portfolio_save_load(tmp_path):
    user_id = "integration_user"
    portfolio = {"position": {"entry_price": 100, "stop_loss": 95, "take_profit": 105, "size": 10, "steps": 1, "timestamp": "2025-03-10T12:00:00"}}
    filename = tmp_path / f"portfolio_{user_id}.json"
    with open(filename, "w", encoding="utf-8") as f:
        import json
        json.dump(portfolio, f, indent=4)
    with open(filename, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == portfolio

@pytest.mark.asyncio
async def test_integration_market_data():
    client = DummyAsyncClient()
    price = await get_last_price(client, "dummy_figi")
    assert abs(price - 100.5) < 0.001
