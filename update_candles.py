import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from tinkoff.invest import AsyncClient, CandleInterval

from csv_loader import load_candles_from_csv, save_candles_to_csv

load_dotenv()
TINKOFF_TOKEN = os.getenv("TINKOFF_TOKEN")

# Папка для хранения свечей
CANDLES_FOLDER = "candles"

# Параметры запроса
INTERVAL = CandleInterval.CANDLE_INTERVAL_5_MIN
DAYS_BACK = 730  # 2 года назад

async def fetch_new_candles(client, figi, from_date, to_date):
    candles = await client.market_data.get_candles(
        figi=figi,
        from_=from_date,
        to=to_date,
        interval=INTERVAL
    )
    data = []
    for candle in candles.candles:
        o = candle.open.units + candle.open.nano / 1e9
        h = candle.high.units + candle.high.nano / 1e9
        l = candle.low.units + candle.low.nano / 1e9
        c = candle.close.units + candle.close.nano / 1e9
        v = candle.volume
        data.append({
            "time": candle.time.replace(tzinfo=None),
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v
        })
    return data

async def update_candles(ticker_figi_mapping):
    async with AsyncClient(TINKOFF_TOKEN) as client:
        for ticker, figi in ticker_figi_mapping.items():
            print(f"\n🔄 Обновление {ticker}")
            old_candles = load_candles_from_csv(ticker)
            if not old_candles:
                print(f"⚠️ Нет старых данных для {ticker}, пропускаем.")
                continue

            last_time = max(candle['time'] for candle in old_candles)
            now = datetime.utcnow()

            if (now - last_time).total_seconds() < 60:
                print(f"✅ Для {ticker} данные актуальны.")
                continue

            new_candles = await fetch_new_candles(client, figi, last_time + timedelta(minutes=5), now)
            if not new_candles:
                print(f"⚠️ Нет новых данных для {ticker}.")
                continue

            combined_candles = old_candles + new_candles
            combined_candles = {c['time']: c for c in combined_candles}  # Убираем дубликаты по времени
            combined_candles = sorted(combined_candles.values(), key=lambda x: x['time'])

            save_candles_to_csv(ticker, combined_candles)
            print(f"✅ Обновили {ticker}: {len(new_candles)} новых свечей сохранено.")

# Пример использования (будет в другом файле, например, update_all_candles.py)
# ticker_figi_mapping = {
#     "SBER": "FIGI_SBER",
#     "GAZP": "FIGI_GAZP",
# }
# asyncio.run(update_candles(ticker_figi_mapping))
