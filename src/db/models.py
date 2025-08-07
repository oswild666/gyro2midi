import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Date, BigInteger, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Coin(Base):
    """Таблица для хранения информации о монетах."""
    __tablename__ = 'coins'

    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, nullable=False, index=True) # e.g., BTCUSDT
    name = Column(String) # e.g., Bitcoin

    prices = relationship("Price", back_populates="coin")
    daily_data = relationship("DailyData", back_populates="coin")

    def __repr__(self):
        return f"<Coin(ticker='{self.ticker}')>"

class Price(Base):
    """Таблица для хранения ежеминутных цен для каждой монеты."""
    __tablename__ = 'prices'

    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False, index=True)
    price = Column(Float, nullable=False)

    coin = relationship("Coin", back_populates="prices")

    def __repr__(self):
        return f"<Price(coin_id={self.coin_id}, price={self.price}, time='{self.timestamp}')>"

class DailyData(Base):
    """Таблица для хранения ежедневных данных по каждой монете."""
    __tablename__ = 'daily_data'

    id = Column(Integer, primary_key=True)
    coin_id = Column(Integer, ForeignKey('coins.id'), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    market_cap = Column(BigInteger)
    market_cap_rank = Column(Integer)
    bybit_volume_24h = Column(Float)
    binance_volume_24h = Column(Float)

    high_price_today = Column(Float)
    low_price_today = Column(Float)
    high_price_yesterday = Column(Float)
    low_price_yesterday = Column(Float)

    coin = relationship("Coin", back_populates="daily_data")

    def __repr__(self):
        return f"<DailyData(coin_id={self.coin_id}, date='{self.date}')>"

# Пример того, как можно будет создать базу данных и таблицы
def setup_database(db_name="crypto_data.db"):
    """Создает файл БД и таблицы, если их еще нет."""
    engine = create_engine(f'sqlite:///{db_name}')
    Base.metadata.create_all(engine)
    return engine

if __name__ == '__main__':
    # Этот блок выполнится, только если запустить этот файл напрямую.
    # Используется для инициализации или тестирования БД.
    print("Setting up the database...")
    engine = setup_database()
    print(f"Database 'crypto_data.db' and tables created successfully.")
    # Здесь можно будет добавить тестовые данные
