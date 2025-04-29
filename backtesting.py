import pandas as pd
import numpy as np
import logging
from strategy import calculate_rsi, calculate_macd, filter_candles_dynamic
from config import CONFIG
from sklearn.model_selection import GridSearchCV
import os

logger = logging.getLogger("backtesting")

def load_historical_data(filepath: str) -> pd.DataFrame:
    if not os.path.exists(filepath):
        logger.error(f"Файл {filepath} не найден.")
        return pd.DataFrame()
    try:
        df = pd.read_csv(filepath)
        if 'datetime' not in df.columns:
            first_col = df.columns[0]
            df.rename(columns={first_col: 'datetime'}, inplace=True)
        df['datetime'] = pd.to_datetime(df['datetime'])
        logger.info("Исторические данные успешно загружены")
        return df
    except Exception as e:
        logger.error(f"Ошибка загрузки исторических данных: {e}")
        return pd.DataFrame()

def simulate_strategy(df: pd.DataFrame, rsi_period: int, macd_fast: int, macd_slow: int, macd_signal: int) -> dict:
    logger.info("Симуляция стратегии начата")
    position = None
    profit = 0.0
    trades = 0
    wins = 0
    if df.empty:
        logger.warning("Нет исторических данных для симуляции")
        return {"profit": 0.0, "max_drawdown": 0.0, "win_rate": 0.0}
    df = df.sort_values("datetime").reset_index(drop=True)
    for index, row in df.iterrows():
        price = row["close"]
        if index < 50:
            continue
        window = df.iloc[index-50:index]
        prices = window["close"].values
        rsi = calculate_rsi(prices, rsi_period)
        macd_line, signal_line, histogram = calculate_macd(prices, macd_fast, macd_slow, macd_signal)
        signal = None
        if rsi < CONFIG["rsi_oversold"] and histogram > 0:
            signal = "BUY"
        elif rsi > CONFIG["rsi_overbought"] and histogram < 0:
            signal = "SELL"
        if signal == "BUY" and position is None:
            position = price
        elif signal == "SELL" and position is not None:
            trade_profit = (price - position) / position
            profit += trade_profit
            trades += 1
            if trade_profit > 0:
                wins += 1
            position = None
    win_rate = (wins / trades) if trades > 0 else 0.0
    results = {"profit": profit, "max_drawdown": 0.0, "win_rate": win_rate}
    logger.info("Симуляция стратегии завершена")
    return results

def optimize_parameters(filepath: str, optimization_params: dict) -> dict:
    df = load_historical_data(filepath)
    best_result = {"profit": -np.inf, "params": {}}
    param_grid = {
        "rsi_period": optimization_params.get("rsi_periods", [10, 14, 20]),
        "macd_fast": optimization_params.get("macd_fast", [10, 12, 15]),
        "macd_slow": optimization_params.get("macd_slow", [20, 26, 30]),
        "macd_signal": optimization_params.get("macd_signal", [9])
    }
    for rsi_period in param_grid["rsi_period"]:
        for macd_fast in param_grid["macd_fast"]:
            for macd_slow in param_grid["macd_slow"]:
                for macd_signal in param_grid["macd_signal"]:
                    result = simulate_strategy(df, rsi_period, macd_fast, macd_slow, macd_signal)
                    logger.info(f"Параметры: RSI={rsi_period}, MACD_fast={macd_fast}, MACD_slow={macd_slow}, MACD_signal={macd_signal} => Profit={result['profit']}")
                    if result["profit"] > best_result["profit"]:
                        best_result["profit"] = result["profit"]
                        best_result["params"] = {
                            "rsi_period": rsi_period,
                            "macd_fast": macd_fast,
                            "macd_slow": macd_slow,
                            "macd_signal": macd_signal
                        }
    return best_result

def backtest_strategy(filepath: str, strategy_func) -> dict:
    optimization_params = CONFIG.get("optimization", {})
    best = optimize_parameters(filepath, optimization_params)
    logger.info(f"Лучшие параметры: {best['params']} с прибылью {best['profit']}")
    df = load_historical_data(filepath)
    results = simulate_strategy(df, **best['params'])
    return results
