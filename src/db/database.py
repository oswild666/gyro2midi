from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Импортируем наши модели и функцию для создания БД
from .models import Base, Coin, Price, DailyData

class DatabaseManager:
    """
    Класс для управления всеми операциями с базой данных.
    """
    def __init__(self, db_name="crypto_data.db"):
        self.engine = create_engine(f'sqlite:///{db_name}')
        Base.metadata.create_all(self.engine) # Создаем таблицы, если их нет
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def update_coins(self, tickers: list[str]):
        """
        Добавляет новые тикеры в таблицу 'coins', избегая дубликатов.
        """
        existing_tickers = {c.ticker for c in self.session.query(Coin.ticker).all()}
        new_tickers = set(tickers) - existing_tickers

        if new_tickers:
            for ticker in new_tickers:
                # Простое извлечение имени, например, 'Bitcoin' из 'BTC/USDT'
                # В реальности может потребоваться более сложная логика или маппинг
                coin_name = ticker.split('/')[0]
                coin = Coin(ticker=ticker, name=coin_name)
                self.session.add(coin)
            self.session.commit()

    def get_coin_ids(self) -> dict[str, int]:
        """
        Возвращает словарь, сопоставляющий тикеры с их ID в базе данных.
        Кэширует результат для производительности.
        """
        if not hasattr(self, '_coin_id_map'):
            coins = self.session.query(Coin.id, Coin.ticker).all()
            self._coin_id_map = {ticker: id for id, ticker in coins}
        return self._coin_id_map

    def save_prices(self, price_data: dict[str, float]):
        """
        Сохраняет данные о ценах в таблицу 'prices'.
        price_data: Словарь вида {'BTC/USDT': 65000.0, 'ETH/USDT': 3500.0}
        """
        coin_ids = self.get_coin_ids()
        prices_to_add = []
        now = datetime.utcnow()

        for ticker, price in price_data.items():
            coin_id = coin_ids.get(ticker)
            if coin_id and price is not None:
                price_entry = Price(
                    coin_id=coin_id,
                    timestamp=now,
                    price=price
                )
                prices_to_add.append(price_entry)

        if prices_to_add:
            self.session.bulk_save_objects(prices_to_add)
            self.session.commit()

    def save_daily_data(self, daily_data_map: dict):
        """
        Сохраняет или обновляет различные ежедневные данные для монет.
        daily_data_map: Словарь вида {'BTC/USDT': {'rank': 1, 'high': 68000, ...}}
        """
        coin_ids = self.get_coin_ids()
        today = datetime.utcnow().date()

        for ticker, data in daily_data_map.items():
            coin_id = coin_ids.get(ticker)
            if not coin_id:
                continue

            daily_entry = self.session.query(DailyData).filter_by(coin_id=coin_id, date=today).first()

            if not daily_entry:
                daily_entry = DailyData(coin_id=coin_id, date=today)
                self.session.add(daily_entry)

            # Обновляем поля, если они переданы в словаре data
            if 'rank' in data:
                daily_entry.market_cap_rank = data['rank']
            if 'market_cap' in data:
                daily_entry.market_cap = data['market_cap']
            if 'high' in data:
                daily_entry.high_price_today = data['high']
            if 'low' in data:
                daily_entry.low_price_today = data['low']
            # Можно добавить yesterday_high/low и volume, если понадобится

        self.session.commit()

    def get_price_history(self, ticker: str, start_time: datetime) -> list[Price]:
        """
        Получает историю цен для указанного тикера, начиная с определенного времени.
        """
        coin_ids = self.get_coin_ids()
        coin_id = coin_ids.get(ticker)
        if not coin_id:
            return []

        return self.session.query(Price).filter(
            Price.coin_id == coin_id,
            Price.timestamp >= start_time
        ).order_by(Price.timestamp.asc()).all()

    def close(self):
        """Закрывает сессию базы данных."""
        self.session.close()

if __name__ == '__main__':
    # Пример использования
    db_manager = DatabaseManager("test_db.sqlite")

    # 1. Обновляем список монет
    test_tickers = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
    db_manager.update_coins(test_tickers)
    print("Монеты обновлены.")

    # 2. Сохраняем цены
    test_prices = {'BTC/USDT': 65001.5, 'ETH/USDT': 3502.0, 'DOGE/USDT': 0.15} # DOGE не будет добавлен
    db_manager.save_prices(test_prices)
    print("Цены сохранены.")

    # Проверка
    coin_ids = db_manager.get_coin_ids()
    print(f"ID монет в базе: {coin_ids}")

    btc_id = coin_ids.get('BTC/USDT')
    if btc_id:
        price_entry = db_manager.session.query(Price).filter_by(coin_id=btc_id).first()
        print(f"Последняя сохраненная цена для BTC: {price_entry.price} в {price_entry.timestamp}")

    db_manager.close()
