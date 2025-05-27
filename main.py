import sys
import os
import asyncio
import logging
import signal
import csv
from datetime import datetime, timedelta, timezone
from market_data import save_or_update_candles
from tinkoff.invest import AsyncClient
from tinkoff.invest.schemas import OrderDirection, OrderType
from market_data import get_candles
from strategy import enhanced_strategy
from risk_management import calculate_position_size
from config import CONFIG
from types import SimpleNamespace
from aiogram.utils import executor
from aiogram.dispatcher import Dispatcher
from aiogram import executor
from user_state import UserState
from trade_loop import trading_loop
from user_state import set_user_state, get_user_state

# Импорт модулей для работы с Telegram
from aiogram import Bot, Dispatcher, types, exceptions
from aiogram.dispatcher.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from bot_ui import get_main_keyboard

# Импорт конфигурации и токенов
from config import TELEGRAM_TOKEN, TINKOFF_TOKEN, ACCOUNT_ID, CONFIG

# Импорт функций работы с данными рынка
from market_data import (
    get_last_price, get_orderbook, get_atr,
    get_balance as original_get_balance, get_market_makers, find_high_potential_assets
)

# Импорт функций стратегий
from strategy import (
    enhanced_strategy, filter_candles_dynamic, get_market_condition,
    detect_trend_reversal, detect_short_opportunity, optimal_take_profit
)

# Импорт функций риск-менеджмента (без close_position)
from risk_management import (
    calculate_position_size, update_trailing_stop, check_risk_management, set_dynamic_stop_loss
)

# Импорт из API Тинькофф
from tinkoff.invest import (
    AsyncClient, InstrumentStatus, InstrumentIdType, OrderDirection,
    OrderType, MoneyValue, CandleInterval
)
from tinkoff.invest.utils import now

from tinkoff.invest.schemas import InstrumentIdType, OrderDirection, OrderType

# Импорт модулей мониторинга, портфеля, комиссий, backtesting и ML
from ai_monitor import monitor_logs_and_collect_news
from portfolio_manager import save_portfolio, load_portfolio, generate_report, rebalance_portfolio
from commission_manager import apply_commission
import backtesting
from ml_model import analyze_trading_history



# Настройка логирования
logger = logging.getLogger("main")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
file_handler = logging.FileHandler("trades.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Инициализация бота Telegram и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)


# Глобальный объект состояния пользователя (для простоты, предполагается один пользователь)
USER_STATE = None
AUTO_TRADE_TASK = None

# Обёртка для получения актуального баланса из API.
# Если API возвращает список, пробуем обработать каждый элемент – если элемент имеет атрибуты "units" и "nano", то используем их, иначе приводим к float.
async def get_balance(client) -> float:
    try:
        raw_balance = await original_get_balance(client)
        if isinstance(raw_balance, list):
            balance = 0.0
            for m in raw_balance:
                if hasattr(m, "units") and hasattr(m, "nano"):
                    balance += m.units + m.nano / 1e9
                else:
                    balance += float(m)
        else:
            balance = raw_balance
        return balance
    except Exception as e:
        logger.error(f"Ошибка получения баланса через обёртку: {e}")
        return 0.0

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

async def get_market_instruments(user_state):
    """
    Получает список доступных инструментов для торговли (ТОЛЬКО MOEXBMI).
    """
    try:
        logger.info("Получение списка инструментов...")
        async with AsyncClient(TINKOFF_TOKEN) as client:
            response = await client.instruments.shares()
            logger.info(f"Получено {len(response.instruments)} инструментов.")
            filtered_instruments = [
                {"figi": i.figi, "ticker": i.ticker, "lot": i.lot}
                for i in response.instruments
                if i.ticker in MOEXBMI_TICKERS
            ]
            logger.info(f"Отфильтровано {len(filtered_instruments)} инструментов по MOEXBMI.")
            return filtered_instruments
    except Exception as e:
        logger.error(f"Ошибка получения инструментов: {e}")
        raise RuntimeError(f"Ошибка получения инструментов: {e}")


async def open_position(client, user_state, figi, size, signal):
    direction = OrderDirection.ORDER_DIRECTION_BUY if signal == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
    order = await client.orders.post_order(
        figi=figi,
        quantity=size,
        direction=direction,
        order_type=OrderType.ORDER_TYPE_MARKET,
        account_id=user_state.account_id
    )
    logger.info(f"✅ Открыта позиция {signal} {size} лотов по {figi}, OrderID: {order.order_id}")
    await bot.send_message(user_state.chat_id, f"✅ Ордер {signal} размещён: {figi} ({size} лотов)")
    user_state.position = SimpleNamespace(size=size, figi=figi, entry_price=0)


# async def trading_loop(message):
#     """
#     Основной торговый цикл.
#     """
#     user_id = message.from_user.id
#     user_state = user_states.get(user_id)

#     # Проверяем, существует ли состояние пользователя
#     if not user_state:
#         logger.error(f"Пользователь {user_id} не найден в user_states.")
#         return

#     # Логируем начало торгового цикла
#     if not hasattr(user_state, "logger"):
#         user_state.logger = logging.getLogger(f"UserState_{user_id}")
#         user_state.logger.setLevel(logging.INFO)

#     user_state.logger.info("🔄 Цикл торговли начался")

#     while user_state.active:
#         try:
#             # Получаем список инструментов
#             instruments = await get_market_instruments(user_state)
#             if not instruments:
#                 user_state.logger.warning("⚠️ Нет доступных инструментов для торговли.")
#                 await asyncio.sleep(60)  # Ждём минуту перед повторной попыткой
#                 continue

#             # Перебираем инструменты
#             for instrument in instruments:
#                 figi = instrument["figi"]
#                 ticker = instrument["ticker"]
#                 lot = instrument["lot"]

#                 user_state.logger.info(f"🔎 Проверка актива: {ticker} ({figi})")

#                 # Получаем свечи для анализа
#                 from_date = datetime.utcnow() - timedelta(days=30)
#                 to_date = datetime.utcnow()
#                 interval = "1hour"

#                 candles = await get_candles(user_state.client, figi, from_date, to_date, interval)

#                 if not isinstance(candles, list) or not candles or len(candles) < 10:
#                     user_state.logger.warning(f"⚠️ Некорректные или недостаточные данные по {ticker}, пропускаем.")
#                     continue


#                 # Анализируем сигнал
#                 signal = enhanced_strategy(candles)
#                 last_price = candles[-1]["close"]

#                 # Проверяем текущую позицию
#                 if user_state.position and user_state.entry_price:
#                     change = (last_price - user_state.entry_price) / user_state.entry_price
#                     user_state.logger.info(f"📈 Текущая прибыль/убыток: {change:.2%}")

#                     # Закрываем позицию, если достигнуты условия
#                     if change >= 0.05:  # Пример: фиксируем прибыль при росте на 5%
#                         await close_position(user_state.client, user_state, figi, "PROFIT")
#                         user_state.logger.info(f"✅ Позиция по {ticker} закрыта с прибылью.")
#                         continue
#                     elif change <= -0.02:  # Пример: фиксируем убыток при падении на 2%
#                         await close_position(user_state.client, user_state, figi, "LOSS")
#                         user_state.logger.info(f"❌ Позиция по {ticker} закрыта с убытком.")
#                         continue

#                 # Открываем новую позицию
#                 if signal == "buy" and not user_state.position:
#                     await open_position(user_state.client, user_state, figi, lot, "BUY")
#                     user_state.logger.info(f"📥 Открыта позиция 'buy' по {ticker}.")

#                 elif signal == "sell" and not user_state.position:
#                     await open_position(user_state.client, user_state, figi, lot, "SELL")
#                     user_state.logger.info(f"📥 Открыта позиция 'sell' по {ticker}.")

#             # Ждём перед следующим циклом
#             await asyncio.sleep(60)

#         except Exception as e:
#             user_state.logger.error(f"Ошибка в торговом цикле: {e}")
#             await asyncio.sleep(60)  # Ждём минуту перед повторной попыткой


# Локальная реализация функции закрытия позиции
async def close_position(client, user_state, figi: str, reason: str):
    if not user_state.position:
        logger.warning("Нет открытой позиции для закрытия.")
        return
    direction = "SELL" if user_state.position.size > 0 else "BUY"
    quantity = abs(user_state.position.size)
    if await place_order(client, figi, direction, quantity, user_state):
        price = await get_last_price(client, figi)
        log_trade("CLOSE", user_state.ticker, direction, price, quantity, reason)
        await send_notification(user_state.chat_id, f"Позиция закрыта: {direction} {quantity} лотов по {price:.2f}", "INFO")
        user_state.position = None
        update_portfolio_state(user_state)

# Обработчик команды /start – вывод кликабельного меню
@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    keyboard = get_main_keyboard()
    await message.answer("Бот запущен! Добро пожаловать!\nВыберите команду из меню ниже:", reply_markup=keyboard)

# Обработчик команды /autotrade – запуск автоторговли
@dp.message_handler(commands=["autotrade"])
async def autotrade_handler(message: types.Message):
    user_id = message.from_user.id

    # Проверяем, есть ли пользователь в user_states, если нет — добавляем
    if not get_user_state(user_id):
        user_state = UserState()
        user_state.chat_id = message.chat.id
        set_user_state(user_id, user_state)

    user_state = get_user_state(user_id)


    # Инициализируем клиент Tinkoff API
    if not user_state.client:
        user_state.client = await AsyncClient(TINKOFF_TOKEN).__aenter__()

    user_state.active = True
    asyncio.create_task(trading_loop(user_state))
    await message.answer("🚀 Авто-трейдинг запущен!")

# Обработчик команды /balance – вывод актуального баланса
@dp.message_handler(commands=["balance"])
async def balance_cmd(message: types.Message):
    async with AsyncClient(TINKOFF_TOKEN) as client:
        balance = await get_balance(client)
        await send_notification(message.chat.id, f"Баланс: {balance:.2f}₽", "INFO")

# Обработчик команды /stop_auto – остановка автоторговли
@dp.message_handler(commands=["stop_auto"])
async def stop_auto_handler(message: types.Message):
    global USER_STATE, AUTO_TRADE_TASK

    if USER_STATE:
        USER_STATE.active = False

    if AUTO_TRADE_TASK and not AUTO_TRADE_TASK.done():
        AUTO_TRADE_TASK.cancel()
        await message.answer("⛔️ Авто-трейдинг остановлен (задача отменена).")
    else:
        await message.answer("ℹ️ Авто-трейдинг не был активен.")


# Обработчик команды /report – краткий отчёт
@dp.message_handler(commands=["report"])
async def report_handler(message: types.Message):
    global USER_STATE
    if USER_STATE is None:
        await message.answer("Состояние не инициализировано.")
        return
    report = generate_report(message.from_user.id)
    await message.answer(f"Отчёт за день:\nПрибыль: {report['day']:.2f}\nОтчёт за неделю:\nПрибыль: {report['week']:.2f}\nОтчёт за месяц:\nПрибыль: {report['month']:.2f}")

# Обработчик команды /full_report – подробный отчёт
@dp.message_handler(commands=["full_report"])
async def full_report_handler(message: types.Message):
    global USER_STATE
    if USER_STATE is None:
        await message.answer("Состояние не инициализировано.")
        return
    report = generate_report(message.from_user.id)
    await message.answer(f"Полный отчёт:\nДневная прибыль: {report['day']:.2f}\nНедельная прибыль: {report['week']:.2f}\nМесячная прибыль: {report['month']:.2f}")

# Обработчик команды /settings – вывод текущих настроек
@dp.message_handler(commands=["settings"])
async def settings_handler(message: types.Message):
    settings_text = f"Настройки бота:\nРиск на сделку: {CONFIG['risk_per_trade']*100:.1f}%\nДневной лимит убытка: {CONFIG['daily_loss_limit']*100:.1f}%\nПериод ATR: {CONFIG['atr_period']}\nПлечо: {CONFIG['leverage']}\nКомиссии: {CONFIG['commission']}"
    await message.answer(settings_text)

# Обработчик команды /help – вывод справки
@dp.message_handler(commands=["help"])
async def help_handler(message: types.Message):
    help_text = ("Доступные команды:\n"
                 "/start – Запуск бота\n"
                 "/autotrade – Запустить авто-трейдинг\n"
                 "/balance – Показать баланс\n"
                 "/stop_auto – Остановить авто-трейдинг\n"
                 "/report – Краткий отчёт по доходности\n"
                 "/full_report – Подробный отчёт\n"
                 "/settings – Просмотр настроек\n"
                 "/help – Справка\n"
                 "/stop_all – Полная остановка\n"
                 "/close_all_positions – Закрыть все позиции")
    await message.answer(help_text)

# Обработчик команды /stop_all – полная остановка торговли
@dp.message_handler(commands=["stop_all"])
async def stop_all_handler(message: types.Message):
    global USER_STATE
    if USER_STATE:
        USER_STATE.active = False
        await message.answer("Полная остановка торговли выполнена. Все задачи завершены.")

# Обработчик команды /close_all_positions – закрытие всех позиций
@dp.message_handler(commands=["close_all_positions"])
async def close_all_positions_handler(message: types.Message):
    global USER_STATE
    if USER_STATE and USER_STATE.position:
        await close_position(USER_STATE.client, USER_STATE, USER_STATE.figi, "MANUAL_CLOSE_ALL")
        await message.answer("Все позиции закрыты.")
    else:
        await message.answer("Нет открытых позиций.")

def is_moscow_trading_hours() -> bool:
    moscow_time = datetime.now(timezone(timedelta(hours=3)))
    start_hour, start_minute = map(int, CONFIG["trading_hours"]["start"].split(":"))
    end_hour, end_minute = map(int, CONFIG["trading_hours"]["end"].split(":"))
    start_time = moscow_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end_time = moscow_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    return start_time <= moscow_time <= end_time

async def send_notification(chat_id: int, message: str, level: str = "INFO"):
    icons = {"INFO": "ℹ️", "WARNING": "⚠️", "ALERT": "🚨", "SUCCESS": "✅", "ERROR": "❌"}
    try:
        await asyncio.sleep(0.5)
        await bot.send_message(chat_id, f"{icons.get(level, '')} {message}")
    except exceptions.TelegramRetryAfter as e:
        logger.error(f"Превышен лимит запросов. Ожидание {e.retry_after} сек...")
        await asyncio.sleep(e.retry_after)
        await bot.send_message(chat_id, f"{icons.get(level, '')} {message}")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")

def is_orderbook_active(client, figi: str, min_total_volume: float = 1000) -> asyncio.Future:
    async def check():
        orderbook = await get_orderbook(client, figi)
        if not orderbook:
            return False
        bid_volume = sum(bid.quantity for bid in orderbook.bids) if orderbook.bids else 0
        ask_volume = sum(ask.quantity for bid in orderbook.asks) if orderbook.asks else 0
        total_volume = bid_volume + ask_volume
        return total_volume >= min_total_volume
    return asyncio.create_task(check())

async def place_order(client, figi: str, direction: str, quantity: int, user_state) -> bool:
    try:
        current_price = await get_last_price(client, figi)
        if current_price is None or current_price <= 0:
            logger.error("Цена должна быть положительной!")
            return False
        # Обновляем баланс через обёртку
        balance = await get_balance(client)
        user_state.balance = balance
        order_value = current_price * quantity
        if order_value > balance:
            logger.error(f"Недостаточно средств для ордера: {order_value} > {balance}")
            return False

        instrument = await client.market_data.get_instrument_by(figi=figi)
        if instrument.trading_status != "NORMAL_TRADING":
            logger.error(f"Инструмент {figi} запрещен для торговли")
            return False

        order_direction = OrderDirection.ORDER_DIRECTION_BUY if direction.upper() == "BUY" else OrderDirection.ORDER_DIRECTION_SELL
        price_value = MoneyValue(units=int(current_price), nano=int(round((current_price - int(current_price)) * 1e9)))
        response = await client.orders.post_order(
            figi=figi,
            quantity=quantity,
            account_id=ACCOUNT_ID,
            direction=order_direction,
            order_type=OrderType.ORDER_TYPE_LIMIT if CONFIG["limit_order"]["enabled"] else OrderType.ORDER_TYPE_MARKET,
            price=price_value
        )
        net_value, commission = apply_commission(current_price, quantity, user_state.instrument_info.get("category", "stocks"), CONFIG["commission"])
        logger.info(f"Лимитный ордер {direction} {quantity} по FIGI {figi} размещён, Цена: {current_price:.2f}, Комиссия: {commission:.2f}, Net: {net_value:.2f}. Ответ: {response}")
        logger.info(f"📊 Открыта позиция {figi}: {direction} {quantity} лотов по цене {current_price}")
        return True
    except Exception as e:
        logger.error(f"Ошибка размещения ордера: {e}")
        return False

async def manage_pyramiding(client, user_state, figi: str):
    try:
        current_price = await get_last_price(client, figi)
        if user_state.position:
            if user_state.position.size > 0 and current_price >= user_state.position.entry_price * 1.005:
                additional_size = await calculate_position_size(client, user_state, figi)
                if additional_size >= user_state.instrument_info.get('min_lot', 1):
                    if await place_order(client, figi, "BUY", additional_size, user_state):
                        logger.info(f"Пирамида: добавлено {additional_size} лотов на {figi} по цене {current_price}")
            elif user_state.position.size < 0 and current_price <= user_state.position.entry_price * 0.995:
                additional_size = await calculate_position_size(client, user_state, figi)
                if additional_size >= user_state.instrument_info.get('min_lot', 1):
                    if await place_order(client, figi, "SELL", additional_size, user_state):
                        logger.info(f"Пирамида: добавлено {additional_size} лотов на {figi} по цене {current_price}")
    except Exception as e:
        logger.error(f"Ошибка управления пирамидами: {e}")

def log_trade(action: str, ticker: str, direction: str, price: float, quantity: int, reason: str):
    log_file = "trades_history.csv"
    try:
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().isoformat(), action, ticker, direction, price, quantity, reason])
        logger.info(f"Торговая сделка: {action} {direction} {quantity} на {ticker} по {price:.2f} - {reason}")
    except Exception as e:
        logger.error(f"Ошибка записи сделки: {e}")

def update_portfolio_state(user_state):
    portfolio = {}
    if user_state.position:
        portfolio["position"] = {
            "ticker": user_state.ticker,
            "entry_price": user_state.position.entry_price,
            "stop_loss": user_state.position.stop_loss,
            "take_profit": user_state.position.take_profit,
            "size": user_state.position.size,
            "steps": user_state.position.steps,
            "open_time": user_state.position.open_time.isoformat() if user_state.position.open_time else None,
            "last_profit_take_time": user_state.position.last_profit_take_time.isoformat() if user_state.position.last_profit_take_time else None,
            "timestamp": datetime.now().isoformat()
        }
    else:
        portfolio["position"] = None
    save_portfolio(user_state.user_id, portfolio)

def load_portfolio_state(user_state):
    data = load_portfolio(user_state.user_id)
    if data:
        user_state.portfolio_data = data
    else:
        user_state.portfolio_data = {}

# Новый функционал:

def switch_strategy(client, figi: str, raw_candles: list):
    """
    Анализирует рыночные условия и переключает стратегию.
    """
    market_condition = get_market_condition(client, figi, raw_candles)
    logger.info(f"Рыночное состояние: {market_condition}")
    if market_condition == "TREND":
        return "trend_strategy"
    elif market_condition == "VOLATILITY":
        return "volatility_strategy"
    else:
        return "flat_strategy"

async def reverse_position(client, user_state, figi: str):
    """
    Переворачивает текущую позицию при смене тренда.
    """
    if user_state.position:
        current_direction = "BUY" if user_state.position.size > 0 else "SELL"
        new_direction = "SELL" if current_direction == "BUY" else "BUY"
        new_size = await calculate_position_size(client, user_state, figi)
        logger.info(f"Переворот позиции: {current_direction} → {new_direction}, размер: {new_size}")
        success = await place_order(client, figi, new_direction, new_size, user_state)
        if success:
            await send_notification(user_state.chat_id, f"Позиция перевёрнута: {new_direction} {new_size} лотов")
    else:
        logger.info("Нет открытой позиции для переворота.")

def daily_loss_limit(user_state):
    start_balance = user_state.start_of_day_balance
    current_balance = user_state.balance
    if start_balance <= 0:
        logger.warning("Начальный баланс равен 0, пропускаем проверку дневного лимита убытка.")
        return False
    loss_pct = (start_balance - current_balance) / start_balance
    if loss_pct >= CONFIG["daily_loss_limit"]:
        logger.warning(f"Дневной лимит убытка достигнут: {loss_pct*100:.1f}%")
        return True
    return False

async def partial_take_profit(client, user_state, figi: str):
    """
    Фиксирует прибыль частями: закрывает 50% позиции при достижении +0.5%
    и оставшуюся часть при достижении 1-1.5% прибыли.
    """
    if not hasattr(user_state.position, "partial_taken"):
        user_state.position.partial_taken = False

    if not hasattr(user_state, "position") or user_state.position is None:
        return
    current_price = await get_last_price(client, figi)
    entry_price = user_state.position.entry_price
    if user_state.position.size > 0:
        profit_pct = (current_price - entry_price) / entry_price
    else:
        profit_pct = (entry_price - current_price) / entry_price

    if profit_pct >= 0.005 and not getattr(user_state.position, "partial_taken", False):
        partial_size = int(user_state.position.size * CONFIG["profit_take"]["partial_close_ratio"])
        if partial_size > 0:
            logger.info(f"Фиксируем частичную прибыль: закрываем {partial_size} лотов по FIGI {figi}")
            await place_order(client, figi, "SELL" if user_state.position.size > 0 else "BUY", partial_size, user_state)
            user_state.position.partial_taken = True
    elif profit_pct >= 0.01:
        logger.info("Фиксируем остаток прибыли при достижении 1-1.5%")
        await place_order(client, figi, "SELL" if user_state.position.size > 0 else "BUY", abs(user_state.position.size), user_state)

async def adjust_strategy(client, user_state, figi: str):
    recommendation = analyze_trading_history()
    await send_notification(user_state.chat_id, f"Рекомендация по стратегии: {recommendation}")

async def use_limit_orders(client, user_state, figi: str):
    """
    Применяет лимитные ордера для улучшения входа.
    """
    CONFIG["limit_order"]["enabled"] = True
    logger.info("Лимитные ордера включены.")

async def trade_high_risk_stocks(client, user_state, market_data):
    """
    Торговля высокорискованными акциями (2-3 эшелона) с контролем риска.
    """
    potential_assets = find_high_potential_assets(market_data)
    for ticker in potential_assets:
        logger.info(f"Торговля высокорискованным активом: {ticker}")
        await send_notification(user_state.chat_id, f"Торговля высокорискованным активом: {ticker}")

# Обработчик текстовых сообщений из меню (кнопки)
@dp.message_handler()
async def menu_handler(message: types.Message):
    if not message.text:
        return
    text = message.text.strip().lower()
    if text in ["авто-трейдинг", "авто трейдинг"]:
        await autotrade_handler(message)
    elif text == "баланс":
        await balance_cmd(message)
    elif text in ["стоп авто", "стоп"]:
        await stop_auto_handler(message)
    elif text in ["отчёт", "отчет"]:
        await report_handler(message)
    elif text == "настройки":
        await settings_handler(message)
    elif text == "помощь":
        await help_handler(message)
    elif text in ["полная остановка", "стоп_all"]:
        await stop_all_handler(message)
    elif text in ["закрыть все позиции", "close all positions"]:
        await close_all_positions_handler(message)
    else:
        await message.reply("Неизвестная команда. Используйте меню.")

def is_moscow_trading_hours() -> bool:
    moscow_time = datetime.now(timezone(timedelta(hours=3)))
    start_hour, start_minute = map(int, CONFIG["trading_hours"]["start"].split(":"))
    end_hour, end_minute = map(int, CONFIG["trading_hours"]["end"].split(":"))
    start_time = moscow_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    end_time = moscow_time.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    return start_time <= moscow_time <= end_time



if __name__ == "__main__":
    try:
        # Проверяем наличие файла модели
        if not os.path.exists("ml_model.pkl"):
            logger.warning("Файл модели ml_model.pkl не найден. Некоторые функции могут быть недоступны.")

        # Инициализация состояния пользователя
        USER_STATE = UserState()
        USER_STATE.active = False
        USER_STATE.balance = 0
        USER_STATE.start_of_day_balance = 0
        USER_STATE.instrument_info = {"lot": 1, "category": "stocks", "min_lot": 1}
        USER_STATE.position = None
        USER_STATE.client = None

        # Добавляем логгер
        USER_STATE.logger = logging.getLogger("UserState")
        USER_STATE.logger.setLevel(logging.INFO)

        executor.start_polling(dp, skip_updates=True)

    except KeyboardInterrupt:
        logger.info("Остановка бота по запросу пользователя.")

        
# Для совместимости оставляем определение PositionData (используется для сохранения портфеля)
class PositionData:
    def __init__(self):
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.size = 0
        self.steps = 0
        self.open_time = None
        self.last_profit_take_time = None

class UserState:
    def __init__(self):
        self.chat_id = None
        self.account_id = None
        self.balance = 0.0
        self.start_of_day_balance = 0.0
        self.position = None
        self.entry_price = None
        self.active = False
        self.instrument_info = {"lot": 1, "category": "stocks", "min_lot": 1}
        self.client = None
        self.logger = logging.getLogger(f"UserState_{id(self)}")
        self.logger.setLevel(logging.INFO)

