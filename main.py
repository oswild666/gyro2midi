import sys
import os
import threading
import time
from collections import deque

# This allows importing from the src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from api.client import ApiClient
from db.database import DatabaseManager
from gui.app import App
import logging

class AppController:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        self.api_client = ApiClient()
        self.db_manager = DatabaseManager()
        self.app = App()

        self.btc_price_history = deque(maxlen=4) # Храним цены за ~30 секунд (4 * 10с интервал)
        self.animation_thread = None
        self.stop_event = threading.Event()

    def start_data_loop(self):
        """Запускает основной цикл получения данных в фоновом потоке."""
        self.data_thread = threading.Thread(target=self._data_loop, daemon=True)
        self.data_thread.start()

    def _data_loop(self):
        """Бесконечный цикл для получения данных по BTC (быстрый)."""
        logging.info("BTC data loop started.")
        while not self.stop_event.is_set():
            self._update_btc_data()
            time.sleep(10) # Обновляем данные по BTC каждые 10 секунд

    def _full_market_data_loop(self):
        """Бесконечный цикл для получения всех рыночных данных (медленный)."""
        logging.info("Full market data loop started.")
        while not self.stop_event.is_set():
            self._update_full_market_data()
            time.sleep(60) # Обновляем все данные раз в минуту

    def start_data_loops(self):
        """Запускает оба цикла получения данных в фоновых потоках."""
        self.btc_data_thread = threading.Thread(target=self._data_loop, daemon=True)
        self.btc_data_thread.start()

        self.full_data_thread = threading.Thread(target=self._full_market_data_loop, daemon=True)
        self.full_data_thread.start()

    def _update_btc_data(self):
        """Получает и обрабатывает данные по BTC."""
        try:
            prices = self.api_client.get_btc_price_comparison()
            bybit_price = prices.get('bybit')
            binance_price = prices.get('binance')

            # Обновляем статус
            self.app.after(0, self.app.update_status, "bybit", bybit_price is not None)
            self.app.after(0, self.app.update_status, "binance", binance_price is not None)

            if binance_price:
                self.btc_price_history.append(binance_price)
                self._handle_animation()

            # Обновляем GUI (передаем управление в основной поток)
            self.app.after(0, self.app.update_btc_display, binance_price, bybit_price)

        except Exception as e:
            logging.error(f"Error in BTC data update loop: {e}")

    def _handle_animation(self):
        """Определяет направление тренда и запускает анимацию."""
        if len(self.btc_price_history) < 4: # Ждем, пока накопится история за 30с
            direction = 0
        else:
            price_now = self.btc_price_history[-1]
            price_30s_ago = self.btc_price_history[0]

            if price_now > price_30s_ago:
                direction = 1 # Растет
            elif price_now < price_30s_ago:
                direction = -1 # Падает
            else:
                direction = 0 # Стоит

        self.app.after(0, self.app.rotate_star, direction)

    def _update_full_market_data(self):
        """Собирает, обрабатывает и отправляет в GUI все рыночные данные."""
        try:
            logging.info("Starting full market data update...")
            # 1. Получаем все тикеры
            tickers = self.api_client.get_bybit_perpetual_tickers()
            if not tickers:
                logging.warning("Ticker list is empty. Skipping update.")
                return

            # Ограничимся небольшим количеством для примера, чтобы не перегружать API
            tickers = tickers[:20]

            # 2. Обновляем список монет в БД
            self.db_manager.update_coins(tickers)

            # 3. Получаем и сохраняем цены
            prices = self.api_client.fetch_prices('bybit', tickers)
            self.db_manager.save_prices(prices)
            logging.info(f"Fetched and saved prices for {len(prices)} tickers.")

            # 4. Получаем капитализацию (можно делать реже)
            market_caps = self.api_client.get_market_caps(tickers)
            self.app.after(0, self.app.update_status, "coingecko", bool(market_caps))

            # 5. Собираем данные для таблицы
            table_data = []
            from datetime import datetime, timedelta
            from analysis.calculator import DataCalculator

            for ticker in tickers:
                price_history = self.db_manager.get_price_history(ticker, datetime.utcnow() - timedelta(hours=24))

                coin_data = {
                    'ticker': ticker,
                    'price': prices.get(ticker),
                    'market_cap': market_caps.get(ticker, {}).get('market_cap'),
                    'changes': DataCalculator.calculate_price_changes(price_history)
                }
                table_data.append(coin_data)

            # 6. Обновляем GUI
            self.app.after(0, self.app.update_table_data, table_data)
            logging.info("Successfully updated GUI table data.")

        except Exception as e:
            logging.error(f"Error in full market data update loop: {e}", exc_info=True)

    def run(self):
        """Запускает приложение."""
        self.start_data_loops()
        self.app.mainloop()
        self.stop_event.set()

if __name__ == "__main__":
    controller = AppController()
    controller.run()
