import os
import pandas as pd
from ml_model import train_model, prepare_dataset

# Путь к папке с историей свечей
CANDLES_DIR = r"C:\Users\User\Desktop\TradeBot\candles"

# Создаём временный общий CSV
merged_csv = "all_candles_combined.csv"

all_dfs = []

for filename in os.listdir(CANDLES_DIR):
    if filename.endswith("_candles.csv"):
        filepath = os.path.join(CANDLES_DIR, filename)
        try:
            df = pd.read_csv(filepath, parse_dates=["time"])
            df["ticker"] = filename.replace("_candles.csv", "")  # сохраняем тикер
            df = df.rename(columns={"time": "datetime"})
            all_dfs.append(df)
        except Exception as e:
            print(f"⚠️ Проблема с {filename}: {e}")

if all_dfs:
    merged_df = pd.concat(all_dfs)
    merged_df.to_csv(merged_csv, index=False)
    print(f"✅ Объединено {len(all_dfs)} файлов. Обучение начинается...")
    train_model(merged_csv)
else:
    print("❌ Не найдено подходящих файлов.")