from datetime import datetime
from typing import Optional, Dict

# Состояние всех пользователей бота
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
        self.open_time: Optional[datetime] = None  # Время открытия позиции
        self.instrument_info: Dict[str, float] = {"lot": 1.0}  # Например: {"lot": 1.0}
        self.client = None

    def set_position(self, direction: str, entry_price: float) -> None:
        """
        Устанавливает позицию пользователя.

        Args:
            direction (str): Направление позиции ("long" или "short").
            entry_price (float): Цена входа в позицию.

        Raises:
            ValueError: Если направление позиции некорректно.
        """
        if direction not in {"long", "short"}:
            raise ValueError("Направление должно быть 'long' или 'short'.")
        self.position = direction
        self.entry_price = entry_price
        self.open_time = datetime.utcnow()

    def reset(self) -> None:
        """
        Сбрасывает состояние позиции пользователя.
        """
        self.position = None
        self.entry_price = None
        self.open_time = None

    def update_balance(self, amount: float) -> None:
        """
        Обновляет баланс пользователя.

        Args:
            amount (float): Сумма для добавления или вычитания.
        """
        self.balance += amount
