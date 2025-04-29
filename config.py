import json
import os
from dotenv import load_dotenv


load_dotenv()

def load_config():
    config_file = "config.json"
    if os.path.exists(config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {
            "trading_hours": {"start": "07:00", "end": "23:45"},
            "risk_per_trade": 0.02,
            "daily_loss_limit": 0.1,  # 10% дневной убыток
            "max_position_duration_hours": 3,  # Макс. время удержания позиции
            "atr_period": 14,
            "atr_multiplier": 1.5,
            "rsi_period": 14,
            "rsi_overbought": 65,
            "rsi_oversold": 35,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "volatility_threshold": 0.01,
            "volatility_filter_period": 14,
            "min_avg_volume": 1000,
            "retry_attempts": 3,
            "retry_initial_delay": 1.0,
            "leverage": 3,
            "commission": {
                "stocks": {"rate": 0.0005, "fixed": 0.01},
                "precious_metals": {"rate": 0.015, "fixed": 0.01},
                "currency": {"rate": 0.005, "fixed": 0.01},
                "default": {"rate": 0.001, "fixed": 5.0}
            },
            "strong_signal_threshold": 0.02,
            "profit_take": {
                "enabled": True,
                "take_profit_percentage": 0.02,  # 2% прибыли – порог для частичного закрытия
                "partial_close_ratio": 0.5,      # закрывать 50% позиции при достижении порога
                "interval_minutes": 60           # проверять каждые 60 минут
            },
            "optimization": {
                "rsi_periods": [14, 20],
                "macd_fast": [12, 10],
                "macd_slow": [26, 20],
                "macd_signal": [9]
            },
            # Новые параметры:
            "self_learning": {
                "analyze_period": "weekly"
            },
            "limit_order": {
                "enabled": True
            },
            "portfolio_rebalance": {
                "max_risk_asset": 0.10,
                "asset_types": "russian"
            }
        }
    return config

CONFIG = load_config()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TINKOFF_TOKEN = os.getenv("TINKOFF_TOKEN")
ACCOUNT_ID = os.getenv("TINKOFF_ACCOUNT_ID")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
