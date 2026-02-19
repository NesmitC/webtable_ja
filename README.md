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

ПОПОЛНЕНИЕ БАЗЫ - ЛОКАЛЬНО
python fix_export.py

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


![alt text](image.png)

*******************************************************************
# Создай дамп данных
python manage.py dumpdata main.OrthogramExample --format=json --indent=2 > ortho_examples.json

# Проверь что файл создан
ls -lh ortho_examples.json

# Перейди в папку проекта
cd C:\Users\alex\Jango\webtable_ja_project

# ЧЕРЕЗ ФАЙЛЗИЛЛА СКОПИРОВАТЬ с сервера в корень компа

# НА ЛОКАОЛЬНОМ КОМПЕ
# Очисти фикстуру от проблемных внешних ключей
python clean_fixture.py

# (Опционально) Очисти старые данные
python manage.py shell
>>> from main.models import OrthogramExample
>>> OrthogramExample.objects.all().delete()
>>> exit()

# Загрузи очищенный дамп
python manage.py loaddata ortho_examples_clean.json


project_root/
├── main/
│   ├── __init__.py
│   ├── admin.py
│   ├── assistant.py
│   ├── asgi.py
│   ├── custom_filters.py
│   ├── forms.py
│   ├── models.py
│   ├── settings.py
│   ├── urls.py
│   ├── views.py
│   ├── wsgi.py
│   ├── __pycache__/
│   ├── migrations/
│   ├── static/
│   │   ├── css/
│   │   │   └── planning_style.css
│   │   ├── js/
│   │   │   ├── games.js
│   │   │   ├── correctionModule.js
│   │   │   ├── diagnostic.js
│   │   │   ├── planning_eight.js
│   │   │   ├── planning_orthoe.js
│   │   │   ├── planning_twotwo.js
│   │   │   └── planning.js
│   │   └── images/
│   │       ├── punktum_task_16.webp
│   │       ├── punktum_task_17.webp
│   │       ├── punktum_task_18.webp
│   │       ├── punktum_task_19.webp
│   │       ├── punktum_task_20.webp
│   │       ├── punktum_task_21_0.webp
│   │       ├── punktum_task_21_1.webp
│   │       └── punktum_task_21_2.webp
│   └── templates/
│       ├── diagnostic/
│       │   ├── diagnostic_ege.html
│       │   ├── diagnostic_oge.html
│       │   ├── diagnostic_snippet_ege.html
│       │   └── diagnostic_snippet_oge.html
│       ├── exercise_snippet.html
│       ├── registration/
│       │   ├── correction_test_snippet.html
│       │   ├── diagnostic_snippet.html
│       │   ├── diagnostic_starting.html
│       │   ├── ege.html
│       │   ├── index.html
│       │   ├── orthoepy_test_snippet.html
│       │   ├── planning_5k.html
│       │   ├── planning_6k.html
│       │   ├── planning_7k.html
│       │   ├── planning_8k.html
│       │   ├── planning_orthoe.html
│       │   ├── planning_twotwo.html
│       │   ├── profile.html
│       │   ├── task_grammatic_eight_test_snippet.html
│       │   ├── task_paponim_snippet.html
│       │   └── task_wordok_snippet.html
│       ├── chat_widget.html
│       ├── index.html
│       └── profile.html
├── webtable_ja_project/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── manage.py
├── requirements.txt
└── .env


'''