from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Авто-трейдинг")],
            [KeyboardButton(text="Баланс")],
            [KeyboardButton(text="Стоп авто")],
            [KeyboardButton(text="Отчёт")],
            [KeyboardButton(text="Настройки")],
            [KeyboardButton(text="Помощь")],
            [KeyboardButton(text="Полная остановка")],
            [KeyboardButton(text="Закрыть все позиции")]
        ],
        resize_keyboard=True
    )
    return keyboard
