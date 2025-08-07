import pandas as pd
import numpy as np
from datetime import timedelta

class DataCalculator:
    """
    Класс для выполнения всех аналитических расчетов над данными о ценах.
    """

    @staticmethod
    def calculate_price_changes(price_history: list) -> dict:
        """
        Рассчитывает процентное изменение цены за разные временные интервалы.

        :param price_history: Список объектов Price из БД, отсортированных по времени.
        :return: Словарь с процентными изменениями, например, {'5m': 1.2, '15m': -0.5}.
        """
        if not price_history or len(price_history) < 2:
            return {}

        # Преобразуем историю в pandas DataFrame для удобства
        df = pd.DataFrame([(p.timestamp, p.price) for p in price_history], columns=['timestamp', 'price'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        latest_price = df['price'].iloc[-1]
        now = df.index[-1]

        changes = {}
        intervals = {
            '5m': timedelta(minutes=5), '15m': timedelta(minutes=15), '30m': timedelta(minutes=30),
            '1h': timedelta(hours=1), '4h': timedelta(hours=4), '12h': timedelta(hours=12),
            '24h': timedelta(hours=24)
        }

        for name, delta in intervals.items():
            past_time = now - delta
            # Находим ближайшую по времени цену в прошлом
            past_prices = df[df.index <= past_time]
            if not past_prices.empty:
                past_price = past_prices['price'].iloc[-1]
                change_pct = ((latest_price - past_price) / past_price) * 100
                changes[name] = round(change_pct, 2)
            else:
                changes[name] = None # Недостаточно данных для расчета

        return changes

    @staticmethod
    def calculate_two_day_volatility(todays_high: float, yesterdays_low: float) -> float | None:
        """
        Рассчитывает двухдневную волатильность по формуле пользователя.
        """
        if todays_high is None or yesterdays_low is None or yesterdays_low == 0:
            return None

        volatility = ((todays_high - yesterdays_low) / yesterdays_low) * 100
        return round(volatility, 2)

    @staticmethod
    def calculate_sma(prices: pd.Series, period: int) -> float | None:
        """Рассчитывает простое скользящее среднее (SMA)."""
        if len(prices) < period:
            return None
        return prices.rolling(window=period).mean().iloc[-1]

    @staticmethod
    def calculate_ema(prices: pd.Series, period: int) -> float | None:
        """Рассчитывает экспоненциальное скользящее среднее (EMA)."""
        if len(prices) < period:
            return None
        return prices.ewm(span=period, adjust=False).mean().iloc[-1]

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> float | None:
        """Рассчитывает индекс относительной силы (RSI)."""
        if len(prices) < period + 1:
            return None

        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]
