import customtkinter as ctk
from PIL import Image, ImageTk
import logging
from collections import deque
import threading
from datetime import datetime, timedelta

# Импортируем калькулятор напрямую
from analysis.calculator import DataCalculator

class App(ctk.CTk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        # ---- Окно ----
        self.title("Воровское казино")
        self.geometry("770x666")
        ctk.set_appearance_mode("dark")

        # ---- Переменные ----
        # Убираем загрузку изображения, используем текстовый символ
        self.original_star_image = None
        self.star_angle = 0
        self.btc_price_history = deque(maxlen=4)

        # ---- Лэйаут ----
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ---- Виджеты ----
        self._create_header()
        self._create_btc_display()
        self._create_table_placeholder()
        self._create_status_bar()

    def _create_header(self):
        header_frame = ctk.CTkFrame(self, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(header_frame, text="это воровское казино", font=ctk.CTkFont(size=24, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        # Используем текстовый символ вместо изображения
        self.star_label = ctk.CTkLabel(header_frame, text="✴", font=ctk.CTkFont(size=60))
        self.star_label.grid(row=0, column=1, padx=20, pady=10, sticky="e")

    def rotate_star(self, direction: int):
        """Анимирует звезду изменением цвета. direction: 1 для вправо, -1 для влево, 0 для стоп."""
        if direction == 1:
            self.star_label.configure(text_color="green")
        elif direction == -1:
            self.star_label.configure(text_color="red")
        else:
            self.star_label.configure(text_color="white")

    def _btc_update_loop(self):
        """Цикл обновления данных по BTC, работающий в главном потоке GUI."""
        try:
            prices = self.controller.api_client.get_btc_price_comparison()
            bybit_price = prices.get('bybit')
            binance_price = prices.get('binance')

            self.update_status("bybit", bybit_price is not None)
            self.update_status("binance", binance_price is not None)

            if binance_price:
                self.btc_price_history.append(binance_price)
                self._handle_animation()

            self.update_btc_display(binance_price, bybit_price)
        except Exception as e:
            logging.error(f"Ошибка в цикле обновления BTC: {e}")
        finally:
            self.after(10000, self._btc_update_loop)

    def _table_update_loop(self):
        """Запускает воркер для обновления таблицы в фоновом потоке."""
        threading.Thread(target=self._table_update_worker, daemon=True).start()

    def _table_update_worker(self):
        """Воркер, выполняющий сбор данных для таблицы в фоновом потоке."""
        try:
            logging.info("Starting full market data update...")
            api_client = self.controller.api_client
            db_manager = self.controller.db_manager

            tickers = api_client.get_bybit_perpetual_tickers()
            if not tickers: return
            tickers = tickers[:20]

            db_manager.update_coins(tickers)
            prices = api_client.fetch_prices('bybit', tickers)
            db_manager.save_prices(prices)

            market_caps = api_client.get_market_caps(tickers)
            self.after(0, lambda: self.update_status("coingecko", bool(market_caps)))

            table_data = []
            for ticker in tickers:
                history = db_manager.get_price_history(ticker, datetime.utcnow() - timedelta(hours=24))
                table_data.append({
                    'ticker': ticker,
                    'price': prices.get(ticker),
                    'market_cap': market_caps.get(ticker, {}).get('market_cap'),
                    'changes': DataCalculator.calculate_price_changes(history)
                })

            self.after(0, lambda: self.update_table_data(table_data))
            logging.info("Successfully updated GUI table data.")
        except Exception as e:
            logging.error(f"Ошибка в потоке обновления таблицы: {e}", exc_info=True)
        finally:
            self.after(60000, self._table_update_loop)

    def _handle_animation(self):
        """Определяет направление тренда и запускает анимацию."""
        if len(self.btc_price_history) < 4:
            direction = 0
        else:
            price_now = self.btc_price_history[-1]
            price_30s_ago = self.btc_price_history[0]

            if price_now > price_30s_ago: direction = 1
            elif price_now < price_30s_ago: direction = -1
            else: direction = 0

        self.rotate_star(direction)

    # --- Остальные методы без изменений ---
    def _create_btc_display(self):
        btc_frame = ctk.CTkFrame(self)
        btc_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        btc_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.binance_btc_price_label = ctk.CTkLabel(btc_frame, text="Binance BTC: $...", font=ctk.CTkFont(size=20), text_color="yellow")
        self.binance_btc_price_label.grid(row=0, column=0, padx=10, pady=5)
        self.bybit_btc_price_label = ctk.CTkLabel(btc_frame, text="Bybit BTC: $...", font=ctk.CTkFont(size=20), text_color="#D2B48C")
        self.bybit_btc_price_label.grid(row=0, column=1, padx=10, pady=5)
        self.btc_change_label = ctk.CTkLabel(btc_frame, text="24h: ...%", font=ctk.CTkFont(size=16))
        self.btc_change_label.grid(row=0, column=2, padx=10, pady=5)

    def update_btc_display(self, binance_price: float, bybit_price: float, change_24h: float = None):
        self.binance_btc_price_label.configure(text=f"Binance BTC: ${binance_price:,.2f}" if binance_price else "Binance BTC: --")
        self.bybit_btc_price_label.configure(text=f"Bybit BTC: ${bybit_price:,.2f}" if bybit_price else "Bybit BTC: --")
        if change_24h is not None:
            color = "green" if change_24h >= 0 else "red"
            self.btc_change_label.configure(text=f"24h: {change_24h:+.2f}%", text_color=color)

    def _create_table_placeholder(self):
        self.table_frame = ctk.CTkScrollableFrame(self, label_text="Рыночные данные")
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        self.table_frame.grid_columnconfigure((0,1,2,3,4,5,6,7,8,9), weight=1)
        self.table_headers = ["Тикер", "Цена", "Капитализация", "5m", "15m", "30m", "1h", "4h", "12h", "24h"]
        self.table_data = []
        self.table_widgets = []
        self.sort_column = 0
        self.sort_reverse = False
        for i, header in enumerate(self.table_headers):
            button = ctk.CTkButton(self.table_frame, text=header, font=ctk.CTkFont(weight="bold"), command=lambda col=i: self._sort_table_by_column(col))
            button.grid(row=0, column=i, padx=5, pady=5, sticky="ew")

    def _sort_table_by_column(self, column_index: int):
        header = self.table_headers[column_index]
        if self.sort_column == column_index: self.sort_reverse = not self.sort_reverse
        else: self.sort_reverse = False
        self.sort_column = column_index
        key_func = {
            "Тикер": lambda i: i.get('ticker', ''), "Цена": lambda i: i.get('price', 0) or 0,
            "Капитализация": lambda i: i.get('market_cap', 0) or 0,
            "5m": lambda i: i.get('changes', {}).get('5m', -999) or -999, "15m": lambda i: i.get('changes', {}).get('15m', -999) or -999,
            "30m": lambda i: i.get('changes', {}).get('30m', -999) or -999, "1h": lambda i: i.get('changes', {}).get('1h', -999) or -999,
            "4h": lambda i: i.get('changes', {}).get('4h', -999) or -999, "12h": lambda i: i.get('changes', {}).get('12h', -999) or -999,
            "24h": lambda i: i.get('changes', {}).get('24h', -999) or -999,
        }.get(header)
        if key_func:
            self.table_data.sort(key=key_func, reverse=self.sort_reverse)
            self._render_table_data()

    def update_table_data(self, data: list[dict]):
        self.table_data = data
        self._sort_table_by_column(self.sort_column)

    def _render_table_data(self):
        for row_widgets in self.table_widgets:
            for widget in row_widgets: widget.destroy()
        self.table_widgets = []
        for row_index, coin_data in enumerate(self.table_data, start=1):
            row_widgets = []
            ticker = coin_data.get('ticker', '--')
            price = f"${coin_data.get('price', 0):,.2f}"
            market_cap = f"${coin_data.get('market_cap', 0):,.0f}" if coin_data.get('market_cap') else "--"
            changes = coin_data.get('changes', {})
            columns = [ticker, price, market_cap, changes.get('5m'), changes.get('15m'), changes.get('30m'), changes.get('1h'), changes.get('4h'), changes.get('12h'), changes.get('24h')]
            for col_index, item in enumerate(columns):
                text = str(item) if item is not None else "--"
                color = "white"
                if col_index > 2 and item is not None:
                    text = f"{item:+.2f}%"
                    color = "green" if item > 0 else "red"
                label = ctk.CTkLabel(self.table_frame, text=text, text_color=color)
                label.grid(row=row_index, column=col_index, padx=5, pady=2, sticky="w")
                row_widgets.append(label)
            self.table_widgets.append(row_widgets)

    def _create_status_bar(self):
        status_frame = ctk.CTkFrame(self, corner_radius=0)
        status_frame.grid(row=3, column=0, sticky="ew", padx=0, pady=0)
        self.bybit_status = ctk.CTkLabel(status_frame, text="Bybit: Offline", text_color="red")
        self.bybit_status.pack(side="left", padx=10)
        self.binance_status = ctk.CTkLabel(status_frame, text="Binance: Offline", text_color="red")
        self.binance_status.pack(side="left", padx=10)
        self.coingecko_status = ctk.CTkLabel(status_frame, text="CoinGecko: Offline", text_color="red")
        self.coingecko_status.pack(side="left", padx=10)

    def update_status(self, service_name: str, is_online: bool):
        labels = {"bybit": self.bybit_status, "binance": self.binance_status, "coingecko": self.coingecko_status}
        label = labels.get(service_name)
        if label:
            if is_online: label.configure(text=f"{service_name.capitalize()}: Online", text_color="green")
            else: label.configure(text=f"{service_name.capitalize()}: Offline", text_color="red")
