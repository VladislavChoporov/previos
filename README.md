# Trading Bot

## Описание
Это продвинутая архитектура торгового робота для Московской биржи, интегрированная с API Tinkoff. Проект включает:
- Модульную архитектуру (config.py, market_data.py, strategy.py, ml_model.py, risk_management.py, backtesting.py, bot_ui.py, ai_monitor.py, main.py)
- Backtesting с автоматической оптимизацией параметров
- Интеграцию модели машинного обучения (на основе scikit-learn) для генерации сигналов
- Улучшенный риск-менеджмент с динамическим управлением позицией и базовым корреляционным анализом
- Расширенный Telegram-интерфейс с дополнительными командами (отчёты, настройки, помощь, админ-панель, полная остановка)
- Логирование и мониторинг с автоматическим анализом логов и сбором новостей
- Примеры unit-тестов (директория tests) и возможность интеграции с CI/CD

## Установка
1. Установите зависимости:
pip install -r requirements.txt

2. Создайте файл `.env` с переменными:
TELEGRAM_TOKEN=your_telegram_token TINKOFF_TOKEN=your_tinkoff_token TINKOFF_ACCOUNT_ID=your_account_id NEWS_API_KEY=your_news_api_key

3. (Опционально) Отредактируйте `config.json` для изменения параметров стратегии.

## Запуск
python main.py