import asyncio
import os
import logging
import json
from datetime import datetime, timedelta
import numpy as np
from tinkoff.invest import CandleInterval
from tinkoff.invest.schemas import CandleInterval
from tinkoff.invest.utils import now
from config import CONFIG, ACCOUNT_ID

RETRY_ATTEMPTS = CONFIG["retry_attempts"]
RETRY_INITIAL_DELAY = CONFIG["retry_initial_delay"]
ATR_PERIOD = CONFIG["atr_period"]

logger = logging.getLogger("market_data")

async def get_last_price(client, figi: str) -> float:
    attempts = 0
    delay_time = RETRY_INITIAL_DELAY
    while attempts < RETRY_ATTEMPTS:
        try:
            response = await client.market_data.get_last_prices(figi=[figi])
            if not response.last_prices:
                return 0.0
            price = response.last_prices[0].price
            return price.units + price.nano / 1e9
        except Exception as e:
            attempts += 1
            logger.error(f"Попытка {attempts} получения цены для FIGI {figi}: {e}")
            if attempts >= RETRY_ATTEMPTS:
                return 0.0
            await asyncio.sleep(delay_time)
            delay_time *= 2

async def get_orderbook(client, figi: str, depth: int = 10):
    attempts = 0
    delay_time = RETRY_INITIAL_DELAY
    while attempts < RETRY_ATTEMPTS:
        try:
            orderbook = await client.market_data.get_order_book(figi=figi, depth=depth)
            return orderbook
        except Exception as e:
            attempts += 1
            logger.error(f"Попытка {attempts} получения стакана для FIGI {figi}: {e}")
            if attempts >= RETRY_ATTEMPTS:
                return None
            await asyncio.sleep(delay_time)
            delay_time *= 2

async def get_atr(client, figi: str) -> float:
    attempts = 0
    delay_time = RETRY_INITIAL_DELAY
    while attempts < RETRY_ATTEMPTS:
        try:
            candles = await client.market_data.get_candles(
                figi=figi,
                from_=now() - timedelta(hours=1),
                to=now(),
                interval=CandleInterval.CANDLE_INTERVAL_5_MIN
            )
            if candles and candles.candles:
                return calculate_atr(candles.candles, ATR_PERIOD)
            else:
                return 0.0
        except Exception as e:
            attempts += 1
            logger.error(f"Попытка {attempts} получения ATR для FIGI {figi}: {e}")
            if attempts >= RETRY_ATTEMPTS:
                return 0.0
            await asyncio.sleep(delay_time)
            delay_time *= 2

def calculate_atr(candles: list, period: int) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i].high.units + candles[i].high.nano / 1e9
        low = candles[i].low.units + candles[i].low.nano / 1e9
        prev_close = candles[i-1].close.units + candles[i-1].close.nano / 1e9
        true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(true_range)
    return np.mean(true_ranges[-period:]) if len(true_ranges) >= period else np.mean(true_ranges)

def money_value_to_float(value) -> float:
    try:
        return value.units + value.nano / 1e9
    except Exception as e:
        logger.error(f"Ошибка преобразования денежного значения: {e}")
        return 0.0

async def get_balance(client) -> float:
    try:
        # Сначала пробуем получить withdraw_limits
        response = await client.operations.get_withdraw_limits(account_id=ACCOUNT_ID)
        logger.info(f"Ответ get_withdraw_limits: {response}")
        balance = 0.0
        if hasattr(response, "money") and response.money:
            balance = sum(money_value_to_float(money) for money in response.money)
        
        # Далее пробуем получить портфель, чтобы извлечь данные по марже
        portfolio = await client.operations.get_portfolio(account_id=ACCOUNT_ID)
        logger.info(f"Ответ get_portfolio: {portfolio}")
        # Если в портфеле есть поле available_margin, то используем его
        if hasattr(portfolio, "available_margin"):
            margin = money_value_to_float(portfolio.available_margin)
            # Используем всю сумму: средства + маржа
            return balance + margin
        elif hasattr(portfolio, "money") and portfolio.money:
            portfolio_balance = sum(money_value_to_float(money) for money in portfolio.money)
            # Если данные из портфеля больше, чем из withdraw_limits, используем их
            return max(balance, portfolio_balance)
        else:
            return balance
    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        return 0.0

# Новый функционал:

async def get_market_makers(client, figi: str):
    """
    Анализирует данные стакана и возвращает информацию о крупных игроках (market makers).
    """
    orderbook = await client.market_data.get_order_book(figi=figi, depth=20)
    if orderbook is None:
        return {}
    bid_sizes = sum(bid.quantity for bid in orderbook.bids) if orderbook.bids else 0
    ask_sizes = sum(ask.quantity for ask in orderbook.asks) if orderbook.asks else 0
    makers = {"bid_total": bid_sizes, "ask_total": ask_sizes}
    logger.info(f"Данные market makers для FIGI {figi}: {makers}")
    return makers

def find_high_potential_assets(market_data: dict) -> list:
    """
    Ищет российские акции второго эшелона с аномальными движениями.
    market_data: словарь с данными по активам.
    Возвращает список тикеров с высоким потенциалом.
    """
    potential = []
    for ticker, data in market_data.items():
        # Пример: если изменение цены за день более 5% и объем больше порогового значения
        if abs(data.get("daily_change", 0)) > 0.05 and data.get("volume", 0) > CONFIG["min_avg_volume"]:
            potential.append(ticker)
    logger.info(f"Найденные высокопотенциальные активы: {potential}")
    return potential

async def get_trade_candidates(client, top_n=None):
    instruments = await client.instruments.shares()
    candidates = []

    logger.info("🔍 Вызов get_trade_candidates начат")

    for instrument in instruments.instruments:
        if not instrument.api_trade_available_flag:
            continue
        if not instrument.for_qual_investor_flag:
            candidates.append({
                "figi": instrument.figi,
                "ticker": instrument.ticker,
                "lot": instrument.lot,
                "min_price_increment": instrument.min_price_increment.units + instrument.min_price_increment.nano / 1e9
            })

    logger.info(f"📦 Отобрано {len(candidates)} акций")
    return candidates

async def save_candles_to_file(figi: str, filename: str, interval='1hour', years=2, client=None):
    if not client:
        raise ValueError("Клиент Tinkoff API не передан в функцию save_candles_to_file.")

    to_date = datetime.now()
    from_date = to_date - timedelta(days=365 * years)

    candles = await get_candles(figi, from_date=from_date, to_date=to_date, interval=interval, client=client)
    if not candles:
        logger.warning(f"❌ Нет данных по {figi}")
        return

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(candles, f, ensure_ascii=False, indent=2)
    logger.info(f"✅ Сохранили {len(candles)} свечей по {figi} в файл {filename}")

async def get_candles(client, figi, from_date=None, to_date=None, interval='5min'):
    try:
        now = datetime.utcnow()
        if not to_date:
            to_date = now
        if not from_date:
            from_date = now - timedelta(days=5)

        # Подбор интервала
        interval_mapping = {
            '1min': CandleInterval.CANDLE_INTERVAL_1_MIN,
            '5min': CandleInterval.CANDLE_INTERVAL_5_MIN,
            '15min': CandleInterval.CANDLE_INTERVAL_15_MIN,
            'hour': CandleInterval.CANDLE_INTERVAL_HOUR,
            '1hour': CandleInterval.CANDLE_INTERVAL_HOUR,
            'day': CandleInterval.CANDLE_INTERVAL_DAY
        }
        interval_enum = interval_mapping.get(interval, CandleInterval.CANDLE_INTERVAL_5_MIN)

        # Запрашиваем свечи
        candles_response = await client.market_data.get_candles(
            figi=figi,
            from_=from_date,
            to=to_date,
            interval=interval_enum
        )

        if not candles_response.candles:
            raise ValueError(f"Нет данных по свечам для {figi}")

        formatted_candles = []

        # Функция для безопасного парсинга цен
        def parse_price(price):
            try:
                if hasattr(price, 'units') and hasattr(price, 'nano'):
                    return price.units + price.nano / 1e9
                elif isinstance(price, (int, float)):
                    return float(price)
                else:
                    return 0.0
            except Exception as e:
                print(f"Ошибка парсинга цены: {e}")
                return 0.0

        for candle in candles_response.candles:
            formatted_candles.append({
                "time": candle.time.isoformat(),
                "open": parse_price(candle.open),
                "high": parse_price(candle.high),
                "low": parse_price(candle.low),
                "close": parse_price(candle.close),
                "volume": candle.volume
            })

        return formatted_candles

    except Exception as e:
        print(f"Ошибка получения свечей по {figi}: {e}")
        return []


def filter_candles(candles):
    """
    Фильтрация свечей:
    - Убираем свечи с нулевыми объемами.
    - Убираем свечи с пустыми или нулевыми ценами закрытия.
    """
    filtered = []
    volumes = []

    for candle in candles:
        if (
            candle["close"] is not None
            and candle["volume"] is not None
            and candle["close"] > 0
            and candle["volume"] > 0
        ):
            filtered.append(candle)
            volumes.append(candle["volume"])

    return filtered, volumes


async def save_or_update_candles(figi: str, filename: str, interval='1hour', years=2, client=None):
    if not client:
        raise ValueError("Клиент Tinkoff API не передан в функцию save_or_update_candles.")

    to_date = datetime.now()
    from_date = to_date - timedelta(days=365 * years)

    existing_candles = []
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            existing_candles = json.load(f)
            if existing_candles:
                last_time = datetime.fromisoformat(existing_candles[-1]['time'])
                from_date = last_time + timedelta(hours=1)

    new_candles = await get_candles(figi, from_date=from_date, to_date=to_date, interval=interval, client=client)
    if not new_candles:
        logger.warning(f"⛔ Нет новых свечей по {figi}")
        return

    all_candles = existing_candles + new_candles
    all_candles = {c['time']: c for c in all_candles}  # remove duplicates
    sorted_candles = sorted(all_candles.values(), key=lambda x: x['time'])

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(sorted_candles, f, ensure_ascii=False, indent=2)

    logger.info(f"📊 Сохранили {len(new_candles)} новых свечей по {figi}")

async def get_market_instruments(client):
    instruments = await client.instruments.shares()
    shares = instruments.instruments
    filtered = []

    for share in shares:
        # Берём только российские акции в режиме TQBR (основной рынок)
        if share.currency == "rub" and share.exchange in ("MOEX", "SPBEX"):
            filtered.append({
                "figi": share.figi,
                "ticker": share.ticker,
                "class_code": share.class_code,
                "name": share.name
            })

    return filtered


