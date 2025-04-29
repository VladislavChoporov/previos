import csv
import os
from datetime import datetime

CANDLES_FOLDER = "candles"


def load_candles_from_csv(ticker):
    filepath = os.path.join(CANDLES_FOLDER, f"{ticker}_candles.csv")
    candles = []
    if os.path.exists(filepath):
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                candles.append({
                    "time": datetime.fromisoformat(row["time"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"])
                })
    return candles


def save_candles_to_csv(ticker, candles):
    filepath = os.path.join(CANDLES_FOLDER, f"{ticker}_candles.csv")
    os.makedirs(CANDLES_FOLDER, exist_ok=True)
    with open(filepath, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        for candle in candles:
            writer.writerow({
                "time": candle["time"].isoformat(),
                "open": candle["open"],
                "high": candle["high"],
                "low": candle["low"],
                "close": candle["close"],
                "volume": candle["volume"]
            })
