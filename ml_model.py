import numpy as np
import pandas as pd
import logging
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

logger = logging.getLogger("ml_model")

MODEL_FILENAME = "ml_model.pkl"

def prepare_dataset(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath, parse_dates=["datetime"])
    df["price_change"] = df["close"] - df["open"]
    df["volatility"] = df["high"] - df["low"]
    df["prev_close"] = df["close"].shift(1)
    df["true_range"] = df.apply(lambda row: max(
        row["high"] - row["low"],
        abs(row["high"] - row["prev_close"]) if pd.notnull(row["prev_close"]) else 0,
        abs(row["low"] - row["prev_close"]) if pd.notnull(row["prev_close"]) else 0
    ), axis=1)
    df["atr"] = df["true_range"].rolling(window=14, min_periods=1).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14, min_periods=1).mean()
    avg_loss = loss.rolling(window=14, min_periods=1).mean()
    rs = avg_gain / (avg_loss + 1e-6)
    df["rsi"] = 100 - (100 / (1 + rs))
    df["ema_fast"] = df["close"].ewm(span=12, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = df["ema_fast"] - df["ema_slow"]
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["avg_spread"] = df["high"] - df["low"]
    df["target"] = (df["close"] > df["open"]).astype(int)
    df.dropna(inplace=True)
    df.drop(columns=["prev_close", "true_range", "ema_fast", "ema_slow"], inplace=True)
    return df

def train_model(dataset_filepath: str):
    df = prepare_dataset(dataset_filepath)
    feature_cols = ["price_change", "volatility", "volume", "atr", "rsi", "macd_hist", "avg_spread"]
    X = df[feature_cols].values
    y = df["target"].values
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = LogisticRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    logger.info(f"ML модель обучена, точность: {acc:.2f}")
    joblib.dump(model, MODEL_FILENAME)
    return model

def load_model():
    try:
        model = joblib.load(MODEL_FILENAME)
        if model is None:
            raise ValueError("Модель не загружена.")
        return model
    except FileNotFoundError:
        logger.error(f"Файл модели {MODEL_FILENAME} не найден.")
    except Exception as e:
        logger.error(f"Ошибка загрузки модели: {e}")
    return None

def predict_signal(model, features: np.ndarray) -> str:
    prediction = model.predict(features.reshape(1, -1))[0]
    return "BUY" if prediction == 1 else "SELL"

# Новый функционал:

def analyze_trading_history(trades_file="trades_history.csv"):
    """
    Анализирует историю сделок и выдает рекомендации для улучшения торговой стратегии.
    Например, рассчитывает win rate, среднюю прибыль, просадки и т.д.
    """
    try:
        df = pd.read_csv(trades_file, header=None, names=["datetime", "action", "ticker", "direction", "price", "quantity", "reason"], parse_dates=["datetime"])
        total_trades = len(df)
        wins = df[df["action"].str.contains("BUY") & (df["price"].astype(float) > 0)].shape[0]
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        avg_profit = df["price"].astype(float).mean() if total_trades > 0 else 0.0
        recommendation = f"Всего сделок: {total_trades}, Win rate: {win_rate*100:.1f}%, средняя цена сделки: {avg_profit:.2f}."
        logger.info("Анализ торговой истории завершен. " + recommendation)
        return recommendation
    except Exception as e:
        logger.error(f"Ошибка анализа торговой истории: {e}")
        return "Анализ не выполнен."
