import pandas as pd
from .calculator import DataCalculator

class TradingStrategy:
    """
    Класс для реализации торговой стратегии и поиска точек входа.
    """

    def __init__(self, ohlcv_data: pd.DataFrame, tolerance_pct: float = 0.5):
        """
        :param ohlcv_data: DataFrame с колонками ['timestamp', 'open', 'high', 'low', 'close', 'volume']
                           Данные должны быть за последние 24 часа.
        :param tolerance_pct: Процент для кластеризации пиков в один уровень сопротивления.
        """
        if ohlcv_data.empty:
            raise ValueError("OHLCV data cannot be empty.")

        self.ohlcv = ohlcv_data.set_index('timestamp') if 'timestamp' in ohlcv_data.columns else ohlcv_data
        self.tolerance = tolerance_pct / 100

    def find_resistance_levels(self, min_touches: int = 3) -> list[dict]:
        """
        Находит уровни сопротивления на основе кластеризации локальных максимумов.

        :param min_touches: Минимальное количество касаний для формирования уровня.
        :return: Список словарей, где каждый словарь представляет уровень сопротивления.
                 Пример: [{'level_price': 68000, 'touches': 4, 'timestamps': [...]}]
        """
        # Находим локальные максимумы (простой вариант - пик выше соседей)
        self.ohlcv['is_peak'] = (self.ohlcv['high'] > self.ohlcv['high'].shift(1)) & \
                                (self.ohlcv['high'] > self.ohlcv['high'].shift(-1))

        peaks = self.ohlcv[self.ohlcv['is_peak']]['high']

        if len(peaks) < min_touches:
            return []

        # Сортируем пики для кластеризации
        sorted_peaks = sorted(peaks.tolist(), reverse=True)

        clusters = []
        while sorted_peaks:
            # Начинаем новый кластер с самого высокого пика
            leader = sorted_peaks.pop(0)
            cluster = [leader]

            # Ищем другие пики, которые находятся близко к лидеру
            nearby_peaks = [p for p in sorted_peaks if abs(p - leader) / leader <= self.tolerance]

            for p in nearby_peaks:
                cluster.append(p)
                sorted_peaks.remove(p)

            clusters.append(cluster)

        resistance_levels = []
        for cluster in clusters:
            if len(cluster) >= min_touches:
                avg_price = sum(cluster) / len(cluster)
                # Находим таймстемпы, соответствующие пикам в этом кластере
                level_timestamps = peaks[peaks.between(min(cluster), max(cluster))].index.tolist()

                resistance_levels.append({
                    'level_price': avg_price,
                    'touches': len(cluster),
                    'timestamps': level_timestamps
                })

        return resistance_levels

    def find_short_opportunities(self) -> list[dict]:
        """
        Основной метод, который запускает весь анализ и ищет точки входа.
        """
        # 1. Рассчитать индикаторы
        close_prices = self.ohlcv['close']
        self.ohlcv['ema12'] = DataCalculator.calculate_ema(close_prices, 12)
        self.ohlcv['sma50'] = DataCalculator.calculate_sma(close_prices, 50)
        self.ohlcv['rsi14'] = DataCalculator.calculate_rsi(close_prices, 14)

        # 2. Найти уровни сопротивления
        resistance_levels = self.find_resistance_levels()
        if not resistance_levels:
            return []

        opportunities = []
        daily_high = self.ohlcv['high'].max()
        daily_low = self.ohlcv['low'].min()
        upper_third_range_start = daily_low + (daily_high - daily_low) * 2 / 3

        for level in resistance_levels:
            level_price = level['level_price']

            # 3. Проверить условия на уровне
            # Проверяем индикаторы в моменты касания уровня
            touch_data = self.ohlcv.loc[level['timestamps']]
            ema_lt_sma = (touch_data['ema12'] < touch_data['sma50']).all()
            rsi_over_70 = (touch_data['rsi14'] > 70).all()

            if not (ema_lt_sma and rsi_over_70):
                continue

            # 4. Сгенерировать 3 точки входа, если условия выполнены
            # Убедимся, что уровень находится в верхней трети дневного диапазона
            if level_price < upper_third_range_start:
                continue

            stop_loss = level_price * (1 + 0.003)
            # Take-profit с соотношением Risk/Reward = 1.5
            risk_per_share = stop_loss - level_price
            take_profit = level_price - (risk_per_share * 1.5)

            # Оценка уверенности (простая версия)
            confidence = min(10, 5 + level['touches'] - 3) # 5/10 + 1 за каждое доп. касание

            justification = (f"Уровень {level_price:.2f} протестирован {level['touches']} раз(а). "
                             f"EMA(12) < SMA(50) и RSI > 70 подтверждены. "
                             f"Последний RSI: {self.ohlcv['rsi14'].iloc[-1]:.2f}.")

            # Генерируем 3 точки вокруг уровня
            entry_points = [
                level_price * 0.998, # Агрессивная
                level_price,         # Стандартная
                level_price * 1.002  # Консервативная
            ]

            for entry in entry_points:
                opportunities.append({
                    'entry_price': round(entry, 4),
                    'take_profit': round(take_profit, 4),
                    'stop_loss': round(stop_loss, 4),
                    'confidence': confidence,
                    'justification': justification
                })

        # Возвращаем до 3 лучших возможностей, отсортированных по цене входа
        return sorted(opportunities, key=lambda x: x['entry_price'], reverse=True)[:3]
