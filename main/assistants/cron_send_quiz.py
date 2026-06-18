#!/usr/bin/env python
"""
📅 Cron-скрипт: ежедневная рассылка квизов в ВКонтакте (12:00)
Путь: main/assistants/cron_send_quiz.py
"""

import os
import sys
import time
import json
import logging
import requests
from pathlib import Path

# 🔹 1. Настройка путей Django
# Файл лежит в: /project/main/assistants/cron_send_quiz.py
# Нам нужно добраться до /project/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')

import django
django.setup()

# 🔹 2. Загрузка переменных окружения (.env в корне проекта)
from dotenv import load_dotenv
load_dotenv(BASE_DIR / '.env')

# 🔹 3. Импорт после настройки Django
from main.models import UserProfile
import vk_api
from vk_api.utils import get_random_id

# 🔹 4. Настройки из .env
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
API_URL = os.getenv('DJANGO_API_URL', 'http://127.0.0.1:8000').rstrip('/')

# 🔹 5. Логирование
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / 'cron_daily_quiz.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('cron_quiz')


def send_quiz_to_user(profile, vk):
    """Отправляет квиз одному пользователю"""
    vk_id = profile.vk_id
    user_id = profile.user.id
    username = profile.user.username

    try:
        # 1. Получаем квиз через Django API (с интервалами и приоритетом планинга)
        r = requests.post(f"{API_URL}/api/daily-quiz/", json={'user_id': user_id}, timeout=10)
        r.raise_for_status()
        quiz = r.json()

        if 'options' not in quiz:
            log.warning(f"⚠️ Нет квиза для {username} (ID: {user_id})")
            return False

        # 2. Формируем inline-кнопки
        opts = quiz['options']
        correct = next((o for o in opts if o['is_correct']), opts[0])
        incorrect = next((o for o in opts if not o['is_correct']), opts[1] if len(opts) > 1 else opts[0])

        # 🔹 Payload для обработки ответов ботом (включая user_word_id)
        base_payload = {
            "action": "quiz_answer",
            "word_id": quiz['example_id'],
            "user_word_id": quiz.get('user_word_id'),
            "exp": quiz.get('explanation', '')
        }

        keyboard = {
            "inline": True,
            "buttons": [[
                {"action": {"type": "text", "label": f"1️⃣ {correct['text']}", 
                           "payload": json.dumps({**base_payload, "is_correct": True}, ensure_ascii=False)}},
                {"action": {"type": "text", "label": f"2️⃣ {incorrect['text']}", 
                           "payload": json.dumps({**base_payload, "is_correct": False}, ensure_ascii=False)}}
            ]]
        }

        # 3. Отправка
        vk.messages.send(
            user_id=vk_id,
            message=f"🎯 Квиз дня:\n{quiz.get('question', 'Как пишется?')}",
            keyboard=json.dumps(keyboard, ensure_ascii=False),
            random_id=get_random_id()
        )
        log.info(f"✅ Отправлено: {username} (VK: {vk_id})")
        return True

    except requests.exceptions.RequestException as e:
        log.error(f"❌ API error ({username}): {e}")
        return False
    except vk_api.ApiError as e:
        log.error(f"❌ VK error ({username}): {e}")
        return False
    except Exception as e:
        log.error(f"❌ Unexpected ({username}): {e}")
        return False


def main():
    if not VK_TOKEN:
        log.error("❌ VK_GROUP_TOKEN не найден в .env")
        sys.exit(1)

    log.info("🚀 Запуск ежедневной рассылки квизов...")
    
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()

    # Получаем всех привязанных пользователей
    users = UserProfile.objects.filter(vk_id__isnull=False).select_related('user')
    total = users.count()
    log.info(f"👥 Найдено привязанных пользователей: {total}")

    success = 0
    failed = 0

    for i, profile in enumerate(users, 1):
        if send_quiz_to_user(profile, vk):
            success += 1
        else:
            failed += 1
        
        # 🛡️ Защита от rate-limit VK: задержка 0.5 сек между сообщениями
        time.sleep(0.5)

    log.info(f"🏁 Рассылка завершена. Успешно: {success}, Ошибки: {failed}")


if __name__ == '__main__':
    main()