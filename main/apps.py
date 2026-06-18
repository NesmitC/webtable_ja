# main/apps.py
from django.apps import AppConfig

class MainConfig(AppConfig):
    """Конфигурация приложения main"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'  # ← Имя твоего приложения (папка с views.py, models.py)

    def ready(self):
        """
        Этот метод вызывается при запуске Django.
        Здесь мы импортируем signals.py, чтобы зарегистрировать обработчики.
        """
        import main.signals  # noqa: F401
        # ↑ Имя модуля должно совпадать с файлом, где лежит @receiver