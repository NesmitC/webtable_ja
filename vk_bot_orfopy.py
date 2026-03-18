import os
import random
import json
import requests
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

# Загружаем .env
load_dotenv()
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
VK_GROUP_ID = int(os.getenv('VK_GROUP_ID'))
DJANGO_API_URL = os.getenv('DJANGO_API_URL', 'http://127.0.0.1:8000')

# Инициализация VK
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)

# Хранилище последних тестов для каждого пользователя
user_last_word = {}

print(f"✅ VK Бот Орфоэпия запущен!")
print(f"📚 Тренировка ударений (из базы данных)")


def send_message(user_id, text, keyboard=None):
    """Отправляет сообщение пользователю (обычный текст, без markdown)"""
    try:
        params = {
            'user_id': user_id,
            'message': text,
            'random_id': random.randint(-10**10, 10**10)
        }
        if keyboard:
            params['keyboard'] = json.dumps(keyboard, ensure_ascii=False)
        vk.messages.send(**params)
        return True
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False


def create_orthoepy_keyboard(word_id, left_variant, right_variant):
    """
    Создает клавиатуру для теста по орфоэпии (2 варианта)
    """
    keyboard = {
        "one_time": False,
        "inline": True,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": left_variant,
                        "payload": json.dumps({
                            "action": "orthoepy_answer",
                            "word_id": word_id,
                            "selected": left_variant
                        }, ensure_ascii=False)
                    }
                },
                {
                    "action": {
                        "type": "text",
                        "label": right_variant,
                        "payload": json.dumps({
                            "action": "orthoepy_answer",
                            "word_id": word_id,
                            "selected": right_variant
                        }, ensure_ascii=False)
                    }
                }
            ]
        ]
    }
    return keyboard


def get_orthoepy_pair():
    """
    Получает пару слов для теста по орфоэпии из базы данных
    Возвращает: правильное и неправильное ударение для одного слова
    """
    try:
        response = requests.post(
            f"{DJANGO_API_URL}/api/get-orthoepy-pair/",
            json={},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data
        return None
    except Exception as e:
        print(f"Ошибка получения пары: {e}")
        return None


def handle_message(event):
    """Обработчик сообщений"""
    message = event.object.get('message', {})
    user_id = message.get('from_id')
    text = message.get('text', '').strip().lower()
    payload = message.get('payload')
    
    if not user_id:
        return
    
    # Обработка нажатия кнопок (ответ на тест)
    if payload:
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
            action = data.get('action')
            
            # Ответ на тест по орфоэпии
            if action == 'orthoepy_answer':
                selected = data.get('selected')
                word_id = data.get('word_id')
                
                # Получаем слово из хранилища
                word_data = user_last_word.get(user_id)
                
                if word_data and word_data.get('id') == word_id:
                    correct = word_data.get('correct')
                    
                    if selected == correct:
                        send_message(user_id, f"✅ Верно! Правильное ударение: {correct}")
                    else:
                        send_message(user_id, f"❌ Ошибка! Правильное ударение: {correct}")
                    
                    # Меню действий
                    menu_keyboard = {
                        "one_time": False,
                        "inline": True,
                        "buttons": [
                            [
                                {
                                    "action": {
                                        "type": "text",
                                        "label": "🎯 Ещё слово",
                                        "payload": json.dumps({"action": "more_word"}, ensure_ascii=False)
                                    }
                                },
                                {
                                    "action": {
                                        "type": "text",
                                        "label": "❓ Помощь",
                                        "payload": json.dumps({"action": "help"}, ensure_ascii=False)
                                    }
                                }
                            ]
                        ]
                    }
                    send_message(user_id, "Что дальше? 👇", keyboard=menu_keyboard)
                else:
                    send_message(user_id, "⚠️ Ошибка: данные не найдены")
                    
                return
            
            # Ещё слово
            elif action == 'more_word':
                send_word_to_user(user_id)
                return
            
            # Помощь
            elif action == 'help':
                send_help(user_id)
                return
                
        except Exception as e:
            print(f"Ошибка обработки payload: {e}")
        return
    
    # Текстовые команды
    if text in ['/start', 'start', 'начать', 'привет', 'ударения']:
        welcome = (
            "👋 Привет! Я бот для тренировки ударений!\n\n"
            "📝 Я показываю слово в двух вариантах ударения, а ты выбирай правильный.\n\n"
            "Команды:\n"
            "• ударение — получить новое слово\n"
            "• помощь — эта справка"
        )
        send_message(user_id, welcome)
    
    elif text in ['ударение', 'тест', 'слово', 'задание', 'тренировка', 'орфоэпия']:
        send_word_to_user(user_id)
    
    elif text in ['помощь', 'help', 'команды']:
        send_help(user_id)
    
    else:
        send_message(user_id, "❓ Неизвестная команда. Напиши помощь или ударение")


def send_word_to_user(user_id):
    """Отправляет тест по орфоэпии пользователю"""
    try:
        vk.messages.setActivity(user_id=user_id, type='typing')
        
        word_data = get_orthoepy_pair()
        
        if word_data:
            # Сохраняем данные для этого пользователя
            user_last_word[user_id] = word_data
            
            variant1 = word_data.get('variant1')
            variant2 = word_data.get('variant2')
            word_id = word_data.get('id')
            
            if variant1 and variant2:
                # Случайным образом определяем порядок вариантов
                if random.choice([True, False]):
                    left_variant, right_variant = variant1, variant2
                else:
                    left_variant, right_variant = variant2, variant1
                
                # Только вопрос, без дублирования слов в тексте
                question = "Как правильно?"
                keyboard = create_orthoepy_keyboard(word_id, left_variant, right_variant)
                
                send_message(user_id, f"❓ {question}", keyboard=keyboard)
                return
        
        # Если тест не получен
        send_message(user_id, "😕 Временно нет слов для тренировки. Попробуй позже.")
            
    except Exception as e:
        print(f"Ошибка: {e}")
        send_message(user_id, "⚠️ Техническая ошибка. Попробуй позже.")


def send_help(user_id):
    """Отправляет справку"""
    help_text = (
        "📚 Команды бота орфоэпии:\n\n"
        "• ударение — получить новое слово с двумя вариантами\n"
        "• помощь — эта справка\n\n"
        "Как это работает:\n"
        "1. Бот показывает слово в двух вариантах ударения\n"
        "2. Ты выбираешь правильный вариант\n"
        "3. Бот проверяет и показывает правильный ответ\n\n"
        "Удачи в тренировке! 🎯"
    )
    send_message(user_id, help_text)


# Главный цикл
if __name__ == '__main__':
    print(f"🎧 Слушаю сообщения...")
    
    for event in longpoll.listen():
        try:
            if event.type == VkBotEventType.MESSAGE_NEW:
                handle_message(event)
        except Exception as e:
            print(f"Ошибка в цикле: {e}")