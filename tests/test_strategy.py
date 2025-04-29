import numpy as np
import pytest
from strategy import calculate_rsi, calculate_macd, filter_candles

def test_calculate_rsi_range():
    prices = np.array([10, 11, 12, 13, 14, 15, 16])
    rsi = calculate_rsi(prices, 5)
    assert 0 <= rsi <= 100

def test_calculate_macd_types():
    prices = np.linspace(10, 20, 50)
    macd_line, signal_line, histogram = calculate_macd(prices, 12, 26, 9)
    assert isinstance(macd_line, float)
    assert isinstance(signal_line, float)
    assert isinstance(histogram, float)

class DummyCandle:
    def __init__(self, open_val, close_val, volume):
        self.open = type("Price", (), {"units": open_val, "nano": 0})
        self.close = type("Price", (), {"units": close_val, "nano": 0})
        self.volume = volume

def test_filter_candles():
    candles = [DummyCandle(10, 10.5, 1000), DummyCandle(10, 10.2, 800), DummyCandle(10, 10.8, 1200)]
    filtered, volumes = filter_candles(candles)
    assert len(filtered) > 0
