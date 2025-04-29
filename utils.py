import numpy as np

def calculate_rsi(prices: np.ndarray, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50  # нейтральное значение
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed > 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = 100. - (100. / (1. + rs))
    return rsi

def calculate_macd(prices: np.ndarray, fast=12, slow=26, signal=9):
    exp1 = np.exp(np.linspace(-1., 0., fast))
    exp1 /= exp1.sum()
    exp2 = np.exp(np.linspace(-1., 0., slow))
    exp2 /= exp2.sum()

    ema_fast = np.convolve(prices, exp1, mode='valid')
    ema_slow = np.convolve(prices, exp2, mode='valid')
    macd_line = ema_fast[-1] - ema_slow[-1]

    signal_line = np.mean([macd_line] * signal)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram
