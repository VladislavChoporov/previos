import asyncio
import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

from tinkoff.invest import AsyncClient  # Нужно для работы с API
from market_data import get_candles
from trade_loop import start_trading_loop

# Загрузка переменных окружения
load_dotenv()

# Путь к папке для свечей
CANDLES_DIR = "candles"

# Список нужных тикеров
MOEXBMI_TICKERS = [
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

async def get_figi_mapping(client):
    """
    Автоматически создаём маппинг {тикер: figi} через запрос к API
    """
    figi_mapping = {}
    shares = await client.instruments.shares()

    for share in shares.instruments:
        ticker = share.ticker
        if ticker in MOEXBMI_TICKERS:
            figi_mapping[ticker] = share.figi

    return figi_mapping

async def update_candles(figi_mapping):
    os.makedirs(CANDLES_DIR, exist_ok=True)

    async with AsyncClient(os.getenv("TINKOFF_TOKEN")) as client:
        for ticker, figi in figi_mapping.items():
            file_path = os.path.join(CANDLES_DIR, f"{ticker}_candles.csv")

            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                df['time'] = pd.to_datetime(df['time'])
                last_time = df['time'].max()
                from_date = last_time + timedelta(minutes=5)
            else:
                df = pd.DataFrame()
                from_date = datetime.utcnow() - timedelta(days=730)  # 2 года назад

            to_date = datetime.utcnow()

            # Получить новые свечи
            new_candles = await get_candles(client, figi, from_date, to_date)
            if new_candles:
                new_df = pd.DataFrame(new_candles)
                full_df = pd.concat([df, new_df]).drop_duplicates(subset='time').sort_values('time')
                full_df.to_csv(file_path, index=False)
                print(f"✅ Обновлены свечи для {ticker}")
            else:
                print(f"⚠️ Нет новых свечей для {ticker}")

async def main():
    async with AsyncClient(os.getenv("TINKOFF_TOKEN")) as client:
        figi_mapping = await get_figi_mapping(client)
        if not figi_mapping:
            print("❌ Не удалось найти FIGI для тикеров MOEXBMI. Проверь список.")
            return
    await update_candles(figi_mapping)
    await start_trading_loop()

if __name__ == "__main__":
    asyncio.run(main())
