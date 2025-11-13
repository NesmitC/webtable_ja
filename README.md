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

*******************************************
ГИТ ХАБ
git add .
git status
git commit -m " коммит"
git push
*******************************************

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



*********************************************************************
!!! ОБНОВЛЕНИЕ ЧЕРЕЗ PuttY:

# 1. Перейдите в проект
cd /home/neurostat

# 2. Активируйте виртуальное окружение (если есть)
source .venv/bin/activate

# 3. Примените миграции (если менялись модели)
python manage.py makemigrations
python manage.py migrate

# 4. Соберите статические файлы
python manage.py collectstatic --noinput

# Запустите импорт 
python manage.py loaddata orthogram_fixed.json

# 5. Перезапустите Gunicorn
sudo systemctl restart gunicorn

# 6. Проверьте статус
sudo systemctl status gunicorn

*********************************************************************



открыть конфиг
sudo nano /etc/nginx/sites-available/neurostat

Команда nano - редактирование файла
nano /home/neurostat/main/views.py
nano /home/neurostat/main/settings.py

# Перезагружаем конфигурацию systemd
sudo systemctl daemon-reload

Перезапуск Gunicorn
sudo systemctl restart gunicorn

ls -la /home/neurostat/main/staticfiles/
cat /home/neurostat/main/.env

====================================================
ЗАПУСК через ТЕРМИНАЛ
ssh root@91.197.96.233


ПЕРЕЗАЛИВКА ФАЙЛОВ на примере settings.py
(venv) PS C:\Users\alex\Jango\webtable_ja_project>

cd C:\Users\alex\Jango\webtable_ja_project

🔹 Команда для копирования:
scp .\main\settings.py root@91.197.96.233:/home/neurostat/main/settings.py

Перезапусти Gunicorn:
sudo systemctl restart gunicorn

===================================================================

ВЫХОД:
exit


✅ Шаг 5: Как использовать в браузере (для теста):
http://127.0.0.1:8000/api/assistant/?action=daily_question
http://127.0.0.1:8000/api/assistant/?action=progress
http://127.0.0.1:8000/api/assistant/?action=weak
http://127.0.0.1:8000/api/assistant/?action=planning



🔍 Как подключиться к БД с локального компьютера (через DBeaver)
Используйте SSH-туннель:

SSH Host: ваш VPS IP (123.45.67.89)
SSH User: ubuntu (или ваш пользователь)
SSH Auth: пароль или приватный ключ
Database Host: localhost
Port: 5432
Database: neurostat
User: myuser
Password: mypassword



'''