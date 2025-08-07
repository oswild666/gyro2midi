import ccxt
import requests
import logging

# Настройка логирования для отслеживания работы клиента API
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ApiClient:
    """
    Клиент для взаимодействия с API криптовалютных бирж и сервисов данных.
    """
    def __init__(self):
        try:
            self.bybit = ccxt.bybit({'rateLimit': True})
            self.binance = ccxt.binance({'rateLimit': True})
            # Убираем load_markets() из конструктора.
            # ccxt будет загружать рынки "лениво" при первом реальном запросе.
            # Это делает запуск более устойчивым к временным сетевым сбоям.
            logging.info("Успешно инициализированы клиенты для Bybit и Binance.")
        except Exception as e:
            logging.error(f"Ошибка при инициализации ccxt: {e}")
            self.bybit = None
            self.binance = None

        self.coingecko_base_url = "https://api.coingecko.com/api/v3"

    def get_bybit_perpetual_tickers(self) -> list:
        """
        Получает список всех бессрочных фьючерсных контрактов (USDT) с Bybit.
        """
        if not self.bybit:
            logging.error("Клиент Bybit не инициализирован.")
            return []
        try:
            markets = self.bybit.fetch_markets()
            # Фильтруем по типу 'swap' (бессрочные контракты) и котируемой валюте 'USDT'
            usdt_perpetuals = [
                market['symbol'] for market in markets
                if market.get('type') == 'swap' and market.get('quote') == 'USDT'
            ]
            logging.info(f"Найдено {len(usdt_perpetuals)} бессрочных контрактов USDT на Bybit.")
            return usdt_perpetuals
        except Exception as e:
            logging.error(f"Ошибка при получении тикеров с Bybit: {e}")
            return []

    def fetch_prices(self, exchange_name: str, tickers: list) -> dict:
        """
        Получает последние цены, 24ч high/low для списка тикеров с биржи.
        Возвращает словарь {тикер: {'price': цена, 'high': максимум, 'low': минимум}}.
        """
        exchange = getattr(self, exchange_name, None)
        if not exchange:
            logging.error(f"Биржа {exchange_name} не найдена или не инициализирована.")
            return {}

        if not tickers:
            return {}

        results = {}
        try:
            ticker_data = exchange.fetch_tickers(tickers)
            for ticker, data in ticker_data.items():
                if data:
                    results[ticker] = {
                        'price': data.get('last'),
                        'high': data.get('high'),
                        'low': data.get('low')
                    }
        except Exception as e:
            logging.error(f"Ошибка при получении цен с {exchange_name}: {e}")

        return results

    def get_btc_price_comparison(self) -> dict:
        """
        Получает цену BTC/USDT с Bybit и Binance.
        Возвращает словарь {'bybit': цена, 'binance': цена}.
        """
        prices = {'bybit': None, 'binance': None}
        try:
            if self.bybit:
                btc_bybit = self.bybit.fetch_ticker('BTC/USDT')
                prices['bybit'] = btc_bybit['last']
        except Exception as e:
            logging.error(f"Ошибка при получении цены BTC с Bybit: {e}")

        try:
            if self.binance:
                btc_binance = self.binance.fetch_ticker('BTC/USDT')
                prices['binance'] = btc_binance['last']
        except Exception as e:
            logging.error(f"Ошибка при получении цены BTC с Binance: {e}")

        logging.info(f"Цены на BTC: Bybit - {prices['bybit']}, Binance - {prices['binance']}")
        return prices

    def _get_coingecko_id_map(self):
        """
        Получает и кэширует карту сопоставления символов монет с их ID в CoinGecko.
        Карта: {'btc': 'bitcoin', 'eth': 'ethereum', ...}
        """
        if hasattr(self, '_coingecko_map'):
            return self._coingecko_map

        logging.info("Загрузка списка монет с CoinGecko для сопоставления ID...")
        try:
            url = f"{self.coingecko_base_url}/coins/list"
            response = requests.get(url)
            response.raise_for_status()
            coins_list = response.json()
            # Создаем карту: символ в нижнем регистре -> id
            self._coingecko_map = {coin['symbol'].lower(): coin['id'] for coin in coins_list}
            logging.info("Карта ID CoinGecko успешно создана.")
            return self._coingecko_map
        except requests.RequestException as e:
            logging.error(f"Ошибка при получении списка монет с CoinGecko: {e}")
            self._coingecko_map = {}
            return {}

    def get_market_caps(self, tickers: list) -> dict:
        """
        Получает рыночную капитализацию и ранг для списка тикеров через CoinGecko.
        Возвращает словарь {тикер: {'rank': ранг, 'market_cap': капитализация}}.
        """
        id_map = self._get_coingecko_id_map()
        if not id_map:
            return {}

        # Извлекаем базовую валюту (например, 'BTC' из 'BTCUSDT') и находим ее ID
        symbol_to_ticker_map = {}
        coingecko_ids = []
        for ticker in tickers:
            base_currency = ticker.replace('USDT', '').lower()
            if base_currency in id_map:
                cg_id = id_map[base_currency]
                coingecko_ids.append(cg_id)
                symbol_to_ticker_map[cg_id] = ticker

        if not coingecko_ids:
            return {}

        market_data = {}
        try:
            # CoinGecko может принимать несколько id, разделенных запятой
            ids_param = ",".join(coingecko_ids)
            url = f"{self.coingecko_base_url}/coins/markets"
            params = {'vs_currency': 'usd', 'ids': ids_param}

            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for item in data:
                ticker = symbol_to_ticker_map.get(item['id'])
                if ticker:
                    market_data[ticker] = {
                        'rank': item.get('market_cap_rank'),
                        'market_cap': item.get('market_cap')
                    }
            logging.info(f"Получены данные о капитализации для {len(market_data)} монет.")

        except requests.RequestException as e:
            logging.error(f"Ошибка при получении данных о капитализации с CoinGecko: {e}")

        return market_data

if __name__ == '__main__':
    # Пример использования клиента
    client = ApiClient()
    if client.bybit and client.binance:
        # 1. Сравнение цен BTC
        btc_prices = client.get_btc_price_comparison()
        print(f"Цены на BTC: {btc_prices}")

        # 2. Получение списка контрактов и их цен
        perp_tickers = client.get_bybit_perpetual_tickers()
        if perp_tickers:
            sample_tickers = perp_tickers[:5]
            print(f"\nЗапрашиваем цены для: {sample_tickers}")
            prices = client.fetch_prices('bybit', sample_tickers)
            print(f"Цены: {prices}")

            # 3. Получение данных о капитализации
            print(f"\nЗапрашиваем капитализацию для: {sample_tickers}")
            market_caps = client.get_market_caps(sample_tickers)
            print(f"Данные о капитализации: {market_caps}")
    else:
        print("Не удалось инициализировать API клиент.")
