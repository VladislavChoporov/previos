from datetime import datetime, timezone

from config import FIGI_LIST, HIST_START
from market_data import (
    MarketData,
    iter_candles_paged,
    last_ts_in_csv,
    save_append_csv,
    csv_path,          # ← новый импорт
)

def update_all():
    now = datetime.now(timezone.utc)

    with MarketData() as md:
        for figi in FIGI_LIST:
            path = csv_path(figi)                     # ← путь к CSV
            from_dt = last_ts_in_csv(path) or HIST_START
            if from_dt >= now:
                continue

            gen   = iter_candles_paged(md, figi, from_dt, now)
            added = save_append_csv(figi, gen)
            print(f"{figi}: +{added} свечей (до {now:%Y-%m-%d %H:%M})")

if __name__ == "__main__":
    update_all()