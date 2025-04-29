import asyncio
import csv
import os
from datetime import datetime, timedelta
from tinkoff.invest import AsyncClient, CandleInterval
from tinkoff.invest.utils import quotation_to_decimal
from dotenv import load_dotenv

# Загружаем токен из .env
load_dotenv()
TINKOFF_TOKEN = os.getenv("TINKOFF_TOKEN")

# Список тикеров MOEXBMI
TICKERS = [
    "ABIO", "ABRD", "AFKS", "AFLT", "AKRN", "ALRS", "APTK", "AQUA", "ASTR", "BANE", "BANEP",
    "BELU", "BLNG", "BSPB", "CARM", "CBOM", "CHMF", "CHMK", "CNRU", "CNTL", "CNTLP", "DATA",
    "DELI", "DIAS", "DVEC", "ELFV", "ELMT", "ENPG", "ETLN", "EUTR", "FEES", "FESH", "FIXP",
    "FLOT", "GAZP", "GCHE", "GECO", "GEMC", "GTRK", "HEAD", "HNFG", "HYDR", "IRAO", "IRKT",
    "IVAT", "JETL", "KAZT", "KAZTP", "KLSB", "KLVZ", "KMAZ", "KRKNP", "KROT", "KZOS", "KZOSP",
    "LEAS", "LIFE", "LKOH", "LNZL", "LNZLP", "LSNG", "LSNGP", "LSRG", "MAGN", "MBNK", "MDMG",
    "MGKL", "MGNT", "MGTSP", "MOEX", "MRKC", "MRKP", "MRKS", "MRKU", "MRKV", "MRKZ", "MSNG",
    "MSRS", "MSTT", "MTLR", "MTLRP", "MTSS", "MVID", "NKHP", "NKNC", "NKNCP", "NLMK", "NMTP",
    "NSVZ", "NVTK", "OGKB", "OKEY", "OZON", "OZPH", "PHOR", "PIKK", "PLZL", "PMSB", "PMSBP",
    "POSI", "PRFN", "PRMD", "QIWI", "RAGR", "RASP", "RBCM", "RENI", "RKKE", "RNFT", "ROLO",
    "ROSN", "RTKM", "RTKMP", "RUAL", "SBER", "SBERP", "SFIN", "SGZH", "SIBN", "SMLT", "SNGS",
    "SNGSP", "SOFL", "SPBE", "SVAV", "SVCB", "T", "TATN", "TATNP", "TGKA", "TGKB", "TGKN",
    "TRMK", "TRNFP", "TTLK", "UGLD", "UNAC", "UNKL", "UPRO", "UWSN", "VEON-RX", "VKCO", "VRSB",
    "VSEH", "VSMO", "VTBR", "WUSH", "X5", "YAKG", "YDEX", "ZAYM"
]

async def get_figi_by_ticker(client, ticker: str):
    """
    Получение FIGI по тикеру.
    """
    try:
        response = await client.instruments.shares()
        for instrument in response.instruments:
            if instrument.ticker == ticker:
                return instrument.figi
        print(f"⚠️ FIGI не найден для тикера: {ticker}")
    except Exception as e:
        print(f"❌ Ошибка получения FIGI: {e}")
    return None

async def get_all_candles(client, figi: str, from_date: datetime, to_date: datetime, interval: str = '5min'):
    """
    Выгружает все свечи за указанный период.
    """
    interval_mapping = {
        '1min': CandleInterval.CANDLE_INTERVAL_1_MIN,
        '5min': CandleInterval.CANDLE_INTERVAL_5_MIN,
        '15min': CandleInterval.CANDLE_INTERVAL_15_MIN,
        'hour': CandleInterval.CANDLE_INTERVAL_HOUR,
        'day': CandleInterval.CANDLE_INTERVAL_DAY
    }

    interval_enum = interval_mapping.get(interval, CandleInterval.CANDLE_INTERVAL_5_MIN)
    delta_per_request = timedelta(days=7)

    candles_data = []
    current_from = from_date

    while current_from < to_date:
        current_to = min(current_from + delta_per_request, to_date)
        try:
            response = await client.market_data.get_candles(
                figi=figi,
                from_=current_from,
                to=current_to,
                interval=interval_enum
            )
            if response.candles:
                for candle in response.candles:
                    candles_data.append({
                        "time": candle.time.isoformat(),
                        "open": float(quotation_to_decimal(candle.open)),
                        "high": float(quotation_to_decimal(candle.high)),
                        "low": float(quotation_to_decimal(candle.low)),
                        "close": float(quotation_to_decimal(candle.close)),
                        "volume": candle.volume
                    })
            else:
                print(f"⚠️ Нет данных по {figi} с {current_from} по {current_to}")
        except Exception as e:
            print(f"❌ Ошибка загрузки свечей: {e}")

        current_from = current_to

    return candles_data

async def save_candles_to_csv(ticker: str, candles: list):
    """
    Сохраняет свечи в CSV файл.
    """
    filename = f"candles/{ticker}_candles.csv"
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["time", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(candles)

    print(f"✅ Свечи для {ticker} сохранены в {filename}")

async def main():
    from_date = datetime(2023, 1, 1)
    to_date = datetime(2025, 1, 1)

    async with AsyncClient(TINKOFF_TOKEN) as client:
        for ticker in TICKERS:
            figi = await get_figi_by_ticker(client, ticker)
            if not figi:
                continue

            candles = await get_all_candles(client, figi, from_date, to_date)
            if candles:
                await save_candles_to_csv(ticker, candles)
            else:
                print(f"⚠️ Нет данных по {ticker}, пропущено.")

if __name__ == "__main__":
    asyncio.run(main())
