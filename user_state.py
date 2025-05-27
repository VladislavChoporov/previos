from datetime import datetime
from typing import Optional, Dict
from market_data import get_market_instruments


# Глобальное хранилище всех состояний пользователей
user_states = {}

class UserState:
    """
    Класс для хранения состояния пользователя в торговом боте.
    """

    def __init__(self):
        self.chat_id: Optional[int] = None
        self.account_id: Optional[int] = None
        self.balance: float = 0.0
        self.start_of_day_balance: float = 0.0
        self.position: Optional[str] = None  # "long", "short" или None
        self.entry_price: Optional[float] = None
        self.active: bool = False
        self.open_time: Optional[datetime] = None
        self.instrument_info: Dict[str, float] = {"lot": 1.0}
        self.client = None
        self.logger = None
        self.get_instruments_func = get_market_instruments
        self.get_candles_func = None
        self.get_last_price_func = None
        self.get_orderbook_func = None 


    def set_position(self, direction: str, entry_price: float) -> None:
        if direction not in {"long", "short"}:
            raise ValueError("Направление должно быть 'long' или 'short'.")
        self.position = direction
        self.entry_price = entry_price
        self.open_time = datetime.utcnow()

    def reset(self) -> None:
        self.position = None
        self.entry_price = None
        self.open_time = None

    def update_balance(self, amount: float) -> None:
        self.balance += amount

    def update_position(self, ticker: str, quantity: int):
        if not hasattr(self, "positions"):
            self.positions = {}
        self.positions[ticker] = self.positions.get(ticker, 0) + quantity

    def get_position(self, ticker: str) -> int:
        return getattr(self, "positions", {}).get(ticker, 0)


# 🔧 Глобальные функции доступа к user_states
def get_user_state(user_id):
    return user_states.get(user_id)

def set_user_state(user_id, user_state):
    user_states[user_id] = user_state

def has_user_state(user_id):
    return user_id in user_states
