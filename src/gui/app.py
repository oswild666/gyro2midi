import customtkinter as ctk
from PIL import Image, ImageTk
import requests
from io import BytesIO
import logging

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ---- Окно ----
        self.title("Воровское казино")
        self.geometry("770x666")
        ctk.set_appearance_mode("dark")

        # ---- Переменные ----
        self.star_angle = 0
        self.original_star_image = self._load_star_image()

        # ---- Лэйаут ----
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Основная таблица будет растягиваться

        # ---- Виджеты ----
        self._create_header()
        self._create_btc_display()
        self._create_table_placeholder()
        self._create_status_bar()

    def _load_star_image(self):
        """Загружает изображение звезды из URL."""
        url = "https://publicdomainvectors.org/photos/1530113431.png" # Проверенная ссылка на PNG
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            # Инвертируем цвета, если фон черный, чтобы звезда была белой
            # В данном случае фон прозрачный, так что это не нужно, но может пригодиться
            return image.resize((88, 88), Image.Resampling.LANCZOS)
        except Exception as e:
            logging.error(f"Не удалось загрузить изображение звезды: {e}. Используется текстовый символ.")
            return None

    def _create_header(self):
        header_frame = ctk.CTkFrame(self, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(header_frame, text="это воровское казино", font=ctk.CTkFont(size=24, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        if self.original_star_image:
            self.star_label = ctk.CTkLabel(header_frame, text="")
            self.rotate_star(0) # Отобразить начальное изображение
        else:
            # Запасной вариант - текстовый символ
            self.star_label = ctk.CTkLabel(header_frame, text="✴", font=ctk.CTkFont(size=60))
        self.star_label.grid(row=0, column=1, padx=20, pady=10, sticky="e")

    def _create_btc_display(self):
        btc_frame = ctk.CTkFrame(self)
        btc_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        btc_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Binance BTC
        self.binance_btc_price_label = ctk.CTkLabel(btc_frame, text="Binance BTC: $...", font=ctk.CTkFont(size=20), text_color="yellow")
        self.binance_btc_price_label.grid(row=0, column=0, padx=10, pady=5)

        # Bybit BTC
        self.bybit_btc_price_label = ctk.CTkLabel(btc_frame, text="Bybit BTC: $...", font=ctk.CTkFont(size=20), text_color="#D2B48C") # tan
        self.bybit_btc_price_label.grid(row=0, column=1, padx=10, pady=5)

        # 24h Change
        self.btc_change_label = ctk.CTkLabel(btc_frame, text="24h: ...%", font=ctk.CTkFont(size=16))
        self.btc_change_label.grid(row=0, column=2, padx=10, pady=5)

    def update_btc_display(self, binance_price: float, bybit_price: float, change_24h: float = None):
        self.binance_btc_price_label.configure(text=f"Binance BTC: ${binance_price:,.2f}" if binance_price else "Binance BTC: --")
        self.bybit_btc_price_label.configure(text=f"Bybit BTC: ${bybit_price:,.2f}" if bybit_price else "Bybit BTC: --")
        if change_24h is not None:
            color = "green" if change_24h >= 0 else "red"
            self.btc_change_label.configure(text=f"24h: {change_24h:+.2f}%", text_color=color)

    def rotate_star(self, direction: int):
        """Вращает звезду. direction: 1 для вправо, -1 для влево, 0 для стоп."""
        if not self.original_star_image:
            # Анимация для текстового символа
            if direction == 1: self.star_label.configure(text_color="green")
            elif direction == -1: self.star_label.configure(text_color="red")
            else: self.star_label.configure(text_color="white")
            return

        if direction != 0:
            self.star_angle += 5 * direction
            rotated_image = self.original_star_image.rotate(self.star_angle)
            ctk_image = ctk.CTkImage(light_image=rotated_image, dark_image=rotated_image, size=(88, 88))
            self.star_label.configure(image=ctk_image)

    def _create_table_placeholder(self):
        self.table_frame = ctk.CTkScrollableFrame(self, label_text="Рыночные данные")
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        self.table_frame.grid_columnconfigure((0,1,2,3,4,5,6,7,8,9), weight=1)

        self.table_headers = ["Тикер", "Цена", "Капитализация", "5m", "15m", "30m", "1h", "4h", "12h", "24h"]
        self.table_data = [] # Хранилище для данных
        self.table_widgets = []
        self.sort_column = 0 # Сортировка по тикеру по умолчанию
        self.sort_reverse = False

        for i, header in enumerate(self.table_headers):
            button = ctk.CTkButton(self.table_frame, text=header, font=ctk.CTkFont(weight="bold"),
                                   command=lambda col=i: self._sort_table_by_column(col))
            button.grid(row=0, column=i, padx=5, pady=5, sticky="ew")

    def _sort_table_by_column(self, column_index: int):
        """Сортирует данные таблицы и обновляет отображение."""
        header = self.table_headers[column_index]

        # Определяем, как сортировать
        if self.sort_column == column_index:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False

        self.sort_column = column_index

        # Ключ сортировки
        sort_key_map = {
            "Тикер": lambda item: item.get('ticker', ''),
            "Цена": lambda item: item.get('price', 0) or 0,
            "Капитализация": lambda item: item.get('market_cap', 0) or 0,
            "5m": lambda item: item.get('changes', {}).get('5m', -999) or -999,
            "15m": lambda item: item.get('changes', {}).get('15m', -999) or -999,
            "30m": lambda item: item.get('changes', {}).get('30m', -999) or -999,
            "1h": lambda item: item.get('changes', {}).get('1h', -999) or -999,
            "4h": lambda item: item.get('changes', {}).get('4h', -999) or -999,
            "12h": lambda item: item.get('changes', {}).get('12h', -999) or -999,
            "24h": lambda item: item.get('changes', {}).get('24h', -999) or -999,
        }

        key_func = sort_key_map.get(header)
        if key_func:
            self.table_data.sort(key=key_func, reverse=self.sort_reverse)
            self._render_table_data()

    def update_table_data(self, data: list[dict]):
        """
        Обновляет таблицу с рыночными данными.
        """
        self.table_data = data
        self._sort_table_by_column(self.sort_column) # Применяем текущую сортировку к новым данным

    def _render_table_data(self):
        """Отрисовывает данные из self.table_data в GUI."""
        # Очищаем старые виджеты
        for row_widgets in self.table_widgets:
            for widget in row_widgets:
                widget.destroy()
        self.table_widgets = []

        # Заполняем новыми данными
        for row_index, coin_data in enumerate(self.table_data, start=1):
            row_widgets = []

            # Данные для колонок
            ticker = coin_data.get('ticker', '--')
            price = f"${coin_data.get('price', 0):,.2f}"
            market_cap = f"${coin_data.get('market_cap', 0):,.0f}" if coin_data.get('market_cap') else "--"
            changes = coin_data.get('changes', {})

            columns = [
                ticker, price, market_cap,
                changes.get('5m'), changes.get('15m'), changes.get('30m'),
                changes.get('1h'), changes.get('4h'), changes.get('12h'), changes.get('24h')
            ]

            for col_index, item in enumerate(columns):
                text = str(item) if item is not None else "--"
                color = "white"

                # Раскрашиваем процентные изменения
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


if __name__ == '__main__':
    app = App()
    app.mainloop()
