import os
import json
import pytest
from portfolio_manager import save_portfolio, load_portfolio

TEST_USER_ID = "testuser123"

@pytest.fixture(autouse=True)
def cleanup():
    filename = f"portfolio_{TEST_USER_ID}.json"
    if os.path.exists(filename):
        os.remove(filename)
    yield
    if os.path.exists(filename):
        os.remove(filename)

def test_save_and_load_portfolio():
    portfolio = {"position": {"entry_price": 100.0, "stop_loss": 95.0, "take_profit": 105.0, "size": 10, "steps": 1, "timestamp": "2025-03-10T12:00:00"}}
    save_portfolio(TEST_USER_ID, portfolio)
    loaded = load_portfolio(TEST_USER_ID)
    assert loaded == portfolio
