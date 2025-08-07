import sys
import os
import logging

# This allows importing from the src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from api.client import ApiClient
from db.database import DatabaseManager
from gui.app import App

class AppController:
    """
    Контроллер приложения. Инициализирует все компоненты и служит
    центральным узлом, к которому обращается GUI за данными.
    """
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Инициализация бэкенд-компонентов
        self.api_client = ApiClient()
        self.db_manager = DatabaseManager()

        # Инициализация GUI. Передаем ему ссылку на самого себя (контроллер),
        # чтобы GUI мог получать доступ к api_client и db_manager.
        self.app = App(controller=self)

    def run(self):
        """Запускает главный цикл приложения."""
        logging.info("Starting the application...")
        self.app.mainloop()

if __name__ == "__main__":
    controller = AppController()
    controller.run()
