# Deployment

See deploy/README_deploy.md for a production deployment guide (Nginx + Gunicorn + PostgreSQL).
'''
структура проекта

webtable_ja_project/
├── .venv/                   ← виртуальное окружение
├── main/                    ← приложение Django (app)
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py          ← настройки проекта
│   ├── urls.py              ← глобальные маршруты
│   └── wsgi.py
└    ── views.py
├── project/     ← папка с `manage.py` и `db.sqlite3`
│   ├── db.sqlite3           ← база данных SQLite
│   └── manage.py            ← утилита управления проектом
├── .gitignore
├── README.md
└── requirements.txt


запуск проекта
python manage.py runserver

Удали тестовых пользователей:
from django.contrib.auth.models import User

# Удаляем пользователя Ric
User.objects.filter(username='Ric').delete()

# Удаляем пользователя mika
User.objects.filter(username='mika').delete()

МИГРАЦИИ
python manage.py makemigrations
python manage.py migrate

СКРИПТ для УДАЛЕНИЯ ПОЛЬЗОВАТЕЛЕЙ
DELETE FROM main_userprofile WHERE user_id IN (
    SELECT id FROM auth_user WHERE username IN ('Ric', 'mika')
);

DELETE FROM auth_user WHERE username IN ('Ric', 'mika');




'''