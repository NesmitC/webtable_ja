# vk_bot.py
import os, json, logging, requests
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id
import random

# Глобальное хранилище данных пользователей
user_data = {}

# 🔹 Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('vk_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('vk_bot')

load_dotenv()
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
VK_GROUP_ID = int(os.getenv('VK_GROUP_ID', 0))
API_URL = os.getenv('DJANGO_API_URL', 'http://127.0.0.1:8000').rstrip('/')

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)

def send(user_id, text, keyboard=None):
    try:
        params = {'user_id': user_id, 'message': text, 'random_id': get_random_id()}
        if keyboard:
            params['keyboard'] = json.dumps(keyboard, ensure_ascii=False)
        vk.messages.send(**params)
    except Exception as e:
        log.error(f"❌ VK send error: {e}")

def api_post(endpoint, data):
    try:
        r = requests.post(f"{API_URL}{endpoint}", json=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error(f"❌ Django API error {endpoint}: {e}")
        return None

def get_user_by_vk(vk_id):
    res = api_post('/api/vk/get-user/', {'vk_id': vk_id})
    return res if res and res.get('found') else None

def send_main_menu(vk_id, username=""):
    keyboard = {
        "inline": True, "buttons": [
            [{"action": {"type": "text", "label": "📖 Планинг", "payload": '{"action":"planning"}'}},
             {"action": {"type": "text", "label": "📝 Все орф.", "payload": '{"action":"all_orthography"}'}}],
            [{"action": {"type": "text", "label": "🎯 Ударения", "payload": '{"action":"orthoepy"}'}},
             {"action": {"type": "text", "label": "🔥 Горячие", "payload": '{"action":"hot_word"}'}},
             {"action": {"type": "text", "label": "📊 Стат.", "payload": '{"action":"stats"}'}}]
        ]
    }
    send(vk_id, f"👋 Привет, {username}! Главное меню:", keyboard)

def send_help(vk_id):
    send(vk_id, "📚 Команды:\n• /start — главное меню\n• планинг — квиз из твоих слов\n• все орф. — орфография из базы\n• ударение — тест по ударениям\n• статистика — ваш прогресс")


def handle(event):
    obj = event.object
    msg = obj.get('message', {})
    vk_id = msg.get('from_id')
    if not vk_id:
        return

    text = msg.get('text', '').strip()
    payload = msg.get('payload')

    # --- Обработка нажатия на кнопку (Payload) ---
    if payload:
        try:
            data = json.loads(payload)
            action = data.get('a') or data.get('action')

            if action == 'quiz_answer':
                user = get_user_by_vk(vk_id)
                if not user:
                    return send(vk_id, "⚠️ Сначала привяжи аккаунт: /start")

                word_id = data.get('w') or data.get('word_id')
                if not word_id:
                    return send(vk_id, "⚠️ Ошибка данных вопроса")

                # Логируем ответ
                log_res = api_post('/api/log-quiz-answer/', {
                    'user_id': user['user_id'],
                    'word_id': word_id,
                    'user_answer_correct': data.get('c') if 'c' in data else data.get('is_correct')
                })

                if log_res:
                    is_correct = log_res.get('was_correct', False)
                    explanation = log_res.get('explanation', '')
                    correct_text = log_res.get('correct_text', '?')

                    if is_correct:
                        send(vk_id, f"✅ Верно!\n📚 {explanation}")
                    else:
                        send(vk_id, f"❌ Ошибка!\n📚 Правильно: {correct_text}\n💡 {explanation}")
                else:
                    send(vk_id, "⚠️ Не удалось проверить ответ")

                # Определяем режим для кнопки "Ещё"
                last_mode = user_data.get(vk_id, {}).get('last_mode', 'all_orthography')

                send(vk_id, "Что дальше?", {
                    "inline": True,
                    "buttons": [[
                        {"action": {"type": "text", "label": "🎯 Ещё", "payload": json.dumps({"a": last_mode})}},
                        {"action": {"type": "text", "label": "📊 Стат.", "payload": json.dumps({"a": "stats"})}}
                    ]]
                })
                return

            elif action == 'orthoepy_answer':
                user = get_user_by_vk(vk_id)
                if not user:
                    return send(vk_id, "⚠️ Сначала привяжи аккаунт: /start")

                word_id = data.get('word_id')
                is_correct = data.get('is_correct', False)
                correct_text = data.get('correct', '?')

                # Логируем ответ
                api_post('/api/log-quiz-answer/', {
                    'user_id': user['user_id'],
                    'word_id': word_id,
                    'was_correct': is_correct
                })

                if is_correct:
                    send(vk_id, f"✅ Верно!")
                else:
                    send(vk_id, f"❌ Ошибка!\n📚 Правильно: {correct_text}")

                last_mode = user_data.get(vk_id, {}).get('last_mode', 'orthoepy')
                send(vk_id, "Что дальше?", {
                    "inline": True,
                    "buttons": [[
                        {"action": {"type": "text", "label": "🎯 Ещё", "payload": json.dumps({"a": last_mode})}},
                        {"action": {"type": "text", "label": "📊 Стат.", "payload": json.dumps({"a": "stats"})}}
                    ]]
                })
                return

            # Обработка других действий
            elif action == 'planning':
                handle_planning(vk_id)
            elif action in ['all_orthography', 'ortho']:
                handle_all_orthography(vk_id)
            elif action == 'orthoepy':
                handle_orthoepy(vk_id)
            elif action == 'stats':
                handle_stats(vk_id)
            elif action == 'help':
                send_help(vk_id)
            elif action == 'hot_word':
                handle_hot_word(vk_id)

        except Exception as e:
            log.error(f"Payload error: {e}")
        return

    # --- Обработка текстовых команд ---
    cmd = text.lower()

    if cmd in ['/start', 'start', 'привет', 'меню', 'menu']:
        user = get_user_by_vk(vk_id)
        if user:
            send_main_menu(vk_id, user.get('username', 'друг'))
        else:
            send(vk_id, "🔗 Привяжи аккаунт:\n1. Сайт → Профиль → Получить код\n2. Отправь код сюда")

    elif cmd in ['планинг', 'planning']:
        handle_planning(vk_id)
    elif cmd in ['все орф.', 'орфография', 'all_orthography']:
        handle_all_orthography(vk_id)
    elif cmd in ['ударение', 'орфоэпия', 'orthoepy']:
        handle_orthoepy(vk_id)
    elif cmd in ['статистика', 'stats']:
        handle_stats(vk_id)
    elif cmd in ['помощь', 'help']:
        send_help(vk_id)
    elif cmd in ['горячие', 'hot', 'hot_word']:
        handle_hot_word(vk_id)
    elif len(text) == 8 and text.isalnum():
        res = api_post('/api/vk/verify-code/', {'code': text.upper(), 'vk_id': vk_id})
        if res and res.get('success'):
            username = res.get('username', 'друг')
            send(vk_id, f"✅ Привязан! Привет, {username}!")
            send_main_menu(vk_id, username)
        else:
            send(vk_id, "❌ Код не подошёл или устарел")
    else:
        send(vk_id, "❓ Неизвестная команда. Нажми /start")
        

def handle_planning(vk_id):
    user = get_user_by_vk(vk_id)
    if not user:
        return send(vk_id, "❌ Сначала привяжи аккаунт: отправь /start")

    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/bot/planning-quiz/", json={'user_id': user['user_id']}, timeout=5)
        
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        
        data = r.json()
        
        # ✅ Универсальная обработка ответов
        if data.get('status') == 'empty':
            return send(vk_id, data['message'])
        if data.get('error'):
            return send(vk_id, f"⚠️ {data['error']}")
        if 'options' not in data:
            return send(vk_id, "⚠️ Неверный формат ответа от сервера")

        opts = data['options']
        correct = opts[0]['text'] if opts[0]['is_correct'] else opts[1]['text']
        
        # Безопасное извлечение букв
        l_corr = data.get('letter_correct', '?')
        l_incorr = data.get('letter_incorrect', '?')
        
        buttons = [
            {"action": {"type": "text", "label": l_corr, "payload": json.dumps({
                "a": "quiz_answer", "w": data['example_id'], "c": 1
            }, ensure_ascii=False)}},
            {"action": {"type": "text", "label": l_incorr, "payload": json.dumps({
                "a": "quiz_answer", "w": data['example_id'], "c": 0
            }, ensure_ascii=False)}}
        ]

        # Текст с буквами НАД кнопками
        message = f"❓ {data['question']}\n-{l_corr}-   -{l_incorr}-"

        send(vk_id, message, {
            "inline": True,
            "buttons": [buttons]  # одна строка, две кнопки
        })
        
    except Exception as e:
        log.error(f"❌ Planning error: {e}")
        send(vk_id, "⚠️ Ошибка загрузки планинга")


def handle_quiz(vk_id):
    """Квиз из эталонной базы (общая орфография)"""
    user = get_user_by_vk(vk_id)
    if not user:
        return send(vk_id, "❌ Сначала привяжи аккаунт: отправь /start")

    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/daily-quiz/", json={'user_id': user['user_id']}, timeout=5)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        quiz = r.json()

        if 'options' not in quiz:
            return send(vk_id, "⚠️ Не удалось сформировать вопрос")

        opts = quiz['options']
        correct = opts[0]['text'] if opts[0]['is_correct'] else opts[1]['text']
        
        # Собираем уникальные варианты букв
        letters = []
        for opt in opts:
            letter = quiz.get('letter_correct') if opt['is_correct'] else quiz.get('letter_incorrect')
            if letter and letter not in [l['label'] for l in letters]:
                letters.append({
                    'label': letter,
                    'is_correct': opt['is_correct']
                })

        buttons = []
        for letter in letters:
            payload = {
                "action": "quiz_answer",
                "word_id": quiz['example_id'],
                "is_correct": letter['is_correct'],
                "correct": correct,
                "exp": quiz.get('explanation', '')
            }
            buttons.append({
                "action": {"type": "text", "label": letter['label'], "payload": json.dumps(payload, ensure_ascii=False)}
            })

        button_rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]

        send(vk_id, f"❓ {quiz.get('question', 'Как пишется?')}", {
            "inline": True,
            "buttons": button_rows
        })
    except Exception as e:
        log.error(f"❌ Quiz error: {e}")
        send(vk_id, "⚠️ Ошибка загрузки квиза")

def handle_all_orthography(vk_id):
    """Квиз из эталонной базы (игнорирует планинг)"""
    user = get_user_by_vk(vk_id)
    if not user:
        return send(vk_id, "❌ Сначала привяжи аккаунт: отправь /start")

    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/bot/general-orthography/", json={'user_id': user['user_id']}, timeout=5)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        quiz = r.json()

        if 'options' not in quiz:
            return send(vk_id, "⚠️ Не удалось сформировать вопрос")

        opts = quiz['options']
        correct = opts[0]['text'] if opts[0]['is_correct'] else opts[1]['text']
        
        # Собираем уникальные варианты букв
        letters = []
        for opt in opts:
            letter = quiz.get('letter_correct') if opt['is_correct'] else quiz.get('letter_incorrect')
            if letter and letter not in [l['label'] for l in letters]:
                letters.append({
                    'label': letter,
                    'is_correct': opt['is_correct']
                })

        buttons = []
        for letter in letters:
            payload = {
                "action": "quiz_answer",
                "word_id": quiz['example_id'],
                "is_correct": letter['is_correct'],
                "correct": correct,
                "exp": quiz.get('explanation', '')
            }
            buttons.append({
                "action": {"type": "text", "label": letter['label'], "payload": json.dumps(payload, ensure_ascii=False)}
            })

        # Разбиваем кнопки по рядам (максимум 4 в ряд)
        button_rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]

        send(vk_id, f"❓ {quiz.get('question', 'Как пишется?')}", {
            "inline": True,
            "buttons": button_rows
        })
    except Exception as e:
        log.error(f"❌ All orthography error: {e}")
        send(vk_id, "⚠️ Ошибка загрузки")

def handle_orthoepy(vk_id):
    """Квиз по ударениям"""
    user = get_user_by_vk(vk_id)
    if not user:
        return send(vk_id, "❌ Сначала /start")

    # Сохраняем режим для кнопки "Ещё"
    if vk_id not in user_data:
        user_data[vk_id] = {}
    user_data[vk_id]['last_mode'] = 'orthoepy'

    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/get-orthoepy-pair/", json={}, timeout=5)
        
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        pair = r.json()

        if pair and pair.get('variant1'):
            v1, v2, cor = pair['variant1'], pair['variant2'], pair['correct']
            
            # 🔹 Формируем payload (без лишнего explanation)
            p1 = {
                "action": "orthoepy_answer", 
                "word_id": pair['id'], 
                "is_correct": (v1 == cor),
                "correct": cor
            }
            p2 = {
                "action": "orthoepy_answer", 
                "word_id": pair['id'], 
                "is_correct": (v2 == cor),
                "correct": cor
            }

            send(vk_id, f"❓ Как правильно?\n1. {v1}\n2. {v2}", {
                "inline": True, "buttons": [[
                    {"action": {"type": "text", "label": "1️⃣", "payload": json.dumps(p1, ensure_ascii=False)}},
                    {"action": {"type": "text", "label": "2️⃣", "payload": json.dumps(p2, ensure_ascii=False)}}
                ]]
            })
    except Exception as e:
        log.error(f"❌ Orthoepy error: {e}")
        send(vk_id, "⚠️ Ошибка загрузки")

def handle_hot_word(vk_id):
    """Квиз из горячих слов (ЕГЭ-список)"""
    user = get_user_by_vk(vk_id)
    if not user:
        return send(vk_id, "❌ Сначала привяжи аккаунт: отправь /start")

    # Сохраняем режим для кнопки "Ещё"
    if vk_id not in user_data:
        user_data[vk_id] = {}
    user_data[vk_id]['last_mode'] = 'hot_word'

    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/bot/hot-word/", json={'user_id': user['user_id']}, timeout=5)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        quiz = r.json()

        if 'options' not in quiz:
            return send(vk_id, "⚠️ Не удалось сформировать вопрос")

        opts = quiz['options']
        correct = opts[0]['text'] if opts[0]['is_correct'] else opts[1]['text']

        letters = []
        for opt in opts:
            letter = quiz.get('letter_correct') if opt['is_correct'] else quiz.get('letter_incorrect')
            if letter and letter not in [l['label'] for l in letters]:
                letters.append({'label': letter, 'is_correct': opt['is_correct']})

        buttons = []
        for letter in letters:
            payload = {
                "action": "quiz_answer",
                "word_id": quiz['example_id'],
                "is_correct": letter['is_correct'],
                "correct": correct,
                "exp": quiz.get('explanation', '')
            }
            buttons.append({
                "action": {"type": "text", "label": letter['label'], "payload": json.dumps(payload, ensure_ascii=False)}
            })

        button_rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]

        send(vk_id, f"❓ {quiz.get('question', 'Как пишется?')}", {
            "inline": True,
            "buttons": button_rows
        })
    except Exception as e:
        log.error(f"❌ Hot word error: {e}")
        send(vk_id, "⚠️ Ошибка загрузки")

def handle_stats(vk_id):
    user = get_user_by_vk(vk_id)
    if not user: return send(vk_id, "❌ Сначала /start")
    try:
        r = requests.post(f"{API_URL}/api/weekly-report/", json={'user_id': user['user_id']}, timeout=10)
        if r.status_code == 200:
            s = r.json()
            report = f"📊 Статистика\n📚 Слов: {s.get('total_words',0)}\n🎯 Попыток: {s.get('total_attempts',0)}\n✅ Правильно: {s.get('correct_answers',0)}\n📈 {s.get('success_rate',0)}%"
            if s.get('weak_orthograms'):
                report += "\n⚠️ Сложные темы:\n" + "\n".join([f"• {o['name']}" for o in s['weak_orthograms']])
            send(vk_id, report)
    except Exception as e:
        log.error(f"❌ Stats error: {e}")
        send(vk_id, "⚠️ Не удалось загрузить статистику")

if __name__ == '__main__':
    log.info("✅ VK Bot starting...")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            try:
                handle(event)
            except Exception as e:
                log.error(f"❌ Global error: {e}")