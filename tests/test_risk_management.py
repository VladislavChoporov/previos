import pytest
import asyncio
import types
import numpy as np
from risk_management import calculate_position_size, update_trailing_stop
from market_data import get_last_price, get_atr

async def fake_get_last_price(client, figi):
    return 110.0


async def fake_get_atr(client, figi):
    return 5.0

class DummyUserState:
    def __init__(self):
        self.balance = 10000.0
        self.instrument_info = {"lot": 1}
        self.position = types.SimpleNamespace(stop_loss=90.0, take_profit=110.0, size=10, entry_price=95.0, steps=0)
        self.chat_id = 12345

class DummyClient:
    pass

@pytest.mark.asyncio
async def test_calculate_position_size(monkeypatch):
    monkeypatch.setattr("risk_management.get_last_price", fake_get_last_price)
    monkeypatch.setattr("risk_management.get_atr", fake_get_atr)
    dummy_state = DummyUserState()
    client = DummyClient()
    size = await calculate_position_size(client, dummy_state, "dummy")
    assert size == 1

@pytest.mark.asyncio
async def test_update_trailing_stop(monkeypatch):
    monkeypatch.setattr("risk_management.get_last_price", fake_get_last_price)
    monkeypatch.setattr("risk_management.get_atr", fake_get_atr)
    dummy_state = DummyUserState()
    client = DummyClient()
    current_sl = dummy_state.position.stop_loss
    await update_trailing_stop(client, dummy_state, "dummy")
    assert dummy_state.position.stop_loss > current_sl

#def test_diversification_check(caplog):
    #caplog.set_level("INFO")
    #class DummyUserStateForTest:
        #def __init__(self):
            #self.balance = 0
    #auto_states = {"AAPL": DummyUserStateForTest(), "GOOG": DummyUserStateForTest()}
    #diversification_check(auto_states)
    #messages = [record.message for record in caplog.records]
    #assert any("Диверсификация: обнаружено 2 активов" in message for message in messages)