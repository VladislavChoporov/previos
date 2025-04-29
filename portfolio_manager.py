import json
import os
import csv
from datetime import datetime, timedelta

PORTFOLIO_FILE_TEMPLATE = "portfolio_{user_id}.json"

class PortfolioManager:
    def __init__(self):
        self.positions = {}

    def update_position(self, ticker: str, quantity: int):
        self.positions[ticker] = self.positions.get(ticker, 0) + quantity

    def get_position(self, ticker: str) -> int:
        return self.positions.get(ticker, 0)

    def get_all_positions(self) -> dict:
        return self.positions

def save_portfolio(user_id, data):
    filename = f"portfolio_{user_id}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_portfolio(user_id):
    filename = f"portfolio_{user_id}.json"
    if not os.path.exists(filename):
        return None
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def log_trade(action: str, ticker: str, direction: str, price: float, quantity: int, reason: str):
    log_file = "trades_history.csv"
    try:
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().isoformat(), action, ticker, direction, price, quantity, reason])
        # Предполагается, что logger настроен в основном модуле
    except Exception as e:
        print(f"Ошибка записи сделки: {e}")

# Новый функционал:

def generate_report(user_id, trades_file="trades_history.csv"):
    """
    Генерирует отчёт по прибыли за день, неделю и месяц на основе истории сделок.
    Отчёт возвращается в виде словаря.
    """
    report = {"day": 0.0, "week": 0.0, "month": 0.0}
    try:
        with open(trades_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            trades = list(reader)
    except Exception as e:
        print(f"Ошибка чтения файла сделок: {e}")
        return report

    now_dt = datetime.now()
    for trade in trades:
        try:
            trade_time = datetime.fromisoformat(trade[0])
            action = trade[1]
            price = float(trade[4])
            quantity = int(trade[5])
            # Для упрощения считаем прибыль как сумма (при условии, что BUY+SELL формируют сделку)
            profit = price * quantity  # Это упрощенная модель
            if now_dt - trade_time < timedelta(days=1):
                report["day"] += profit
            if now_dt - trade_time < timedelta(weeks=1):
                report["week"] += profit
            if now_dt - trade_time < timedelta(days=30):
                report["month"] += profit
        except Exception:
            continue
    return report

def rebalance_portfolio(portfolio, market_data):
    """
    Перебалансирует портфель, распределяя капитал между ликвидными акциями и фьючерсами.
    market_data: данные о текущем состоянии рынка.
    Ограничение: не более 10% капитала в одном рискованном активе.
    Возвращает обновленный портфель.
    """
    # Пример логики ребалансировки
    total_capital = sum(asset["value"] for asset in portfolio.values())
    max_risk_per_asset = total_capital * 0.10
    for asset, data in portfolio.items():
        if data["value"] > max_risk_per_asset:
            # Сокращаем позицию
            portfolio[asset]["value"] = max_risk_per_asset
    # Можно добавить логику переключения между акциями и фьючерсами по сигналам рынка
    return portfolio
