# settings_test_sqlite.py — локальный прогон тестов без прав PostgreSQL.
#
# Роль myuser в локальном PostgreSQL не имеет CREATEDB, поэтому Django не может
# создать test_neurostat. Этот модуль подменяет БД на sqlite в памяти ТОЛЬКО на
# время тестов: python manage.py test <модуль> --settings=settings_test_sqlite
#
# Прод не затрагивает: wsgi.py/asgi.py загружают main.settings.
# Не использовать для runserver и миграций рабочей БД.
from main.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
