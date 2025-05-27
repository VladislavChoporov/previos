import numpy as np
from ml_model import load_model, predict_signal
import pandas as pd
import logging
from config import CONFIG
from tinkoff.invest.utils import now
from datetime import timedelta
from utils import calculate_rsi, calculate_macd
from loguru import logger

logger = logging.getLogger("strategy")

def calculate_rsi(prices: np.ndarray, period: int) -> float:
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))

def calculate_macd(prices: np.ndarray, fast_period: int, slow_period: int, signal_period: int):
    if len(prices) < slow_period:
        return 0.0, 0.0, 0.0
    ema_fast = pd.Series(prices).ewm(span=fast_period, adjust=False).mean()
    ema_slow = pd.Series(prices).ewm(span=slow_period, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

def filter_candles(candles: list) -> tuple:
    # ⛳ Временно ничего не фильтруем вообще
    return candles, [c.volume for c in candles]


def filter_candles_dynamic(candles: list) -> tuple:
    # ⛳ Временно отключаем фильтрацию, пропускаем всё
    return filter_candles(candles)


def enhanced_strategy(candles):
    if len(candles) < 30:
        logger.debug("❌ Мало свечей для анализа (<30)")
        return None

    close_prices = np.array([c['close'] for c in candles])

    # === RSI
    rsi = calculate_rsi(close_prices, CONFIG["rsi_period"])
    rsi_signal = None
    if rsi < CONFIG["rsi_oversold"]:
        rsi_signal = 'buy'
    elif rsi > CONFIG["rsi_overbought"]:
        rsi_signal = 'sell'

    # === MACD
    macd_line, signal_line, _ = calculate_macd(
        close_prices,
        CONFIG["macd_fast"],
        CONFIG["macd_slow"],
        CONFIG["macd_signal"]
    )
    macd_signal = None
    if macd_line > signal_line:
        macd_signal = 'buy'
    elif macd_line < signal_line:
        macd_signal = 'sell'

    if not rsi_signal and not macd_signal:
        logger.debug("❌ Нет сигналов от RSI и MACD")
        return None

    # === AI-подтверждение
    ai_decision = None  # Объявляем заранее
    try:
        model = load_model()
        if model is not None:
            last_candle = candles[-1]
            try:
                print("🔍 last_candle =", last_candle)
                print("🔍 types:", type(last_candle["close"]), type(last_candle["open"]), type(last_candle["volume"]))
                print("🔍 rsi:", rsi, type(rsi))
                print("🔍 macd_line:", macd_line, "signal_line:", signal_line)

                features = np.array([
                    float(last_candle["close"]) - float(last_candle["open"]),
                    float(last_candle["high"]) - float(last_candle["low"]),
                    float(last_candle["volume"]),
                    float(np.mean([float(c["high"]) - float(c["low"]) for c in candles[-14:]])),
                    float(rsi),
                    float(macd_line - signal_line),
                    float(last_candle["high"]) - float(last_candle["low"])
                ])
            except Exception as fe:
                logger.error(f"❌ Ошибка подготовки признаков для AI модели: {fe}")
                return None

            ai_decision = predict_signal(model, features)
            print(f"✅ ai_decision = {ai_decision}, type = {type(ai_decision)}")
            logger.debug(f"🤖 AI модель прогнозирует: {ai_decision}")
        else:
            logger.warning("⚠️ Модель не загружена, AI-прогноз пропущен")
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка при AI-прогнозе: {e}")
        return None

    # === Совпадение сигналов
    if isinstance(ai_decision, str) and ai_decision.upper() == 'BUY' and ('buy' in [rsi_signal, macd_signal]):
        return 'buy'
    elif isinstance(ai_decision, str) and ai_decision.upper() == 'SELL' and ('sell' in [rsi_signal, macd_signal]):
        return 'sell'
    else:
        logger.info("🧠 AI и индикаторы не сошлись → сигнал пропущен")
        return None

# Новый функционал:

def get_market_condition(client, figi: str, raw_candles: list) -> str:
    """
    Определяет состояние рынка:
    - "TREND" если наблюдается явное направление,
    - "FLAT" если рынок в боковике,
    - "VOLATILITY" если высокая волатильность.
    """
    if not raw_candles or len(raw_candles) < 20:
        return "FLAT"
    filtered, _ = filter_candles_dynamic(raw_candles)
    prices = np.array([candle.close.units + candle.close.nano / 1e9 for candle in filtered])
    volatility = np.std(prices) / np.mean(prices)
    macd_line, _, _ = calculate_macd(prices, CONFIG["macd_fast"], CONFIG["macd_slow"], CONFIG["macd_signal"])
    if volatility > 0.02:
        return "VOLATILITY"
    if abs(macd_line) > 0.05:
        return "TREND"
    return "FLAT"

def detect_trend_reversal(client, figi: str, raw_candles: list) -> bool:
    """
    Анализирует изменение тренда с использованием скользящих средних, MACD и данных из стакана.
    Возвращает True, если обнаружен разворот тренда.
    """
    if not raw_candles or len(raw_candles) < 30:
        return False
    filtered, _ = filter_candles_dynamic(raw_candles)
    prices = np.array([candle.close.units + candle.close.nano / 1e9 for candle in filtered])
    macd_line, signal_line, _ = calculate_macd(prices, CONFIG["macd_fast"], CONFIG["macd_slow"], CONFIG["macd_signal"])
    # Если MACD пересекает сигнальную линию с противоположной стороны – сигнал разворота
    if macd_line * signal_line < 0:
        logger.info("Обнаружен разворот тренда по MACD.")
        return True
    # Дополнительно можно анализировать данные из стакана (orderbook) – здесь оставляем заглушку
    return False

def detect_short_opportunity(client, figi: str, raw_candles: list) -> bool:
    """
    Определяет возможность открытия короткой позиции (short).
    Например, если индикаторы сигнализируют о снижении цены и формируется разворот.
    """
    if detect_trend_reversal(client, figi, raw_candles):
        # Дополнительная логика для подтверждения короткой возможности
        return True
    return False

def optimal_take_profit(prices: np.ndarray, market_condition: str) -> float:
    """
    Рассчитывает оптимальный уровень тейк-профита в зависимости от рыночных условий.
    Для тренда – более агрессивное значение, для флетовых рынков – более консервативное.
    """
    current_price = prices[-1]
    if market_condition == "TREND":
        return current_price * 1.015  # +1.5%
    elif market_condition == "VOLATILITY":
        return current_price * 1.01   # +1%
    else:
        return current_price * 1.005  # +0.5%

# Для корректной работы функции get_market_condition и optimal_take_profit
# предполагается, что функция get_atr импортирована из модуля market_data.
