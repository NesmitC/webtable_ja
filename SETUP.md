# Установка проекта

## 1. Установить зависимости

```bash
pip install -r requirements.txt
```

## 2. Настроить .env

Открыть файл `.env` и заполнить:

**Для PostgreSQL:**
```
DB_ENGINE=postgresql
DB_NAME=neurostat        # имя вашей БД
DB_USER=postgres         # пользователь
DB_PASSWORD=yourpassword # пароль
DB_HOST=localhost
DB_PORT=5432
```

**Для SQLite (локальная разработка):**
```
DB_ENGINE=sqlite3
```

**Остальные обязательные поля:**
```
SECRET_KEY=your-secret-key-here
EMAIL_HOST=smtp.yourhost.ru
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=your@email.ru
EMAIL_HOST_PASSWORD=yourpassword
DEFAULT_FROM_EMAIL=your@email.ru
CSRF_TRUSTED_ORIGINS=https://yourdomain.ru
```

## 3. Создать базу данных (только для PostgreSQL)

```bash
psql -U postgres -c "CREATE DATABASE neurostat;"
```

## 4. Применить миграции

```bash
python manage.py migrate
```

## 5. Загрузить данные

```bash
python manage.py loaddata datadump.json
```

## 6. Собрать статику

```bash
python manage.py collectstatic --noinput
```

## 7. Запустить

```bash
# Локально:
python manage.py runserver

# Продакшн:
sudo systemctl restart gunicorn
```
