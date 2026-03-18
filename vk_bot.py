# vk_bot.py
import os, json, random, requests
from dotenv import load_dotenv
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

load_dotenv()
VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
VK_GROUP_ID = int(os.getenv('VK_GROUP_ID', 0))
API_URL = os.getenv('DJANGO_API_URL', 'http://127.0.0.1:8000').rstrip('/')

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)

user_data = {}  # {vk_id: {'user_id': 123, 'username': 'name'}}


def send(user_id, text, keyboard=None):
    try:
        params = {'user_id': user_id, 'message': text, 'random_id': get_random_id()}
        if keyboard:
            params['keyboard'] = json.dumps(keyboard, ensure_ascii=False)
        vk.messages.send(**params)
    except: pass


def api_post(endpoint, data):
    try:
        r = requests.post(f"{API_URL}{endpoint}", json=data, timeout=5)
        return r.json() if r.status_code == 200 else None
    except: return None


def make_keyboard(word_id, left, right, left_correct=None):
    if left_correct is not None:
        pl = {"action": "quiz_answer", "word_id": word_id, "selected": left, "is_correct": left_correct}
        pr = {"action": "quiz_answer", "word_id": word_id, "selected": right, "is_correct": not left_correct}
    else:
        pl = {"action": "orthoepy_answer", "word_id": word_id, "selected": left}
        pr = {"action": "orthoepy_answer", "word_id": word_id, "selected": right}
    return {
        "inline": True, "buttons": [[
            {"action": {"type": "text", "label": left, "payload": json.dumps(pl)}},
            {"action": {"type": "text", "label": right, "payload": json.dumps(pr)}}
        ]]
    }


def handle(event):
    msg = event.object.get('message', {})
    vk_id = msg.get('from_id')
    text = msg.get('text', '').strip()
    payload = msg.get('payload')
    
    if not vk_id: return
    
    # Кнопки
    if payload:
        try:
            data = json.loads(payload)
            a = data['action']
            if a in ['quiz_answer', 'orthoepy_answer']:
                quiz = user_data.get(vk_id, {}).get('last')
                if not quiz or quiz['id'] != data['word_id']:
                    return send(vk_id, "⚠️ Вопрос устарел")
                
                if a == 'quiz_answer':
                    correct = quiz['correct']
                    if data['is_correct']:
                        send(vk_id, f"✅ Верно!\n\n📚 {quiz.get('exp', '')}")
                    else:
                        send(vk_id, f"❌ Ошибка! Правильно: {correct}\n\n📚 {quiz.get('exp', '')}")
                else:
                    if data['selected'] == quiz['correct']:
                        send(vk_id, "✅ Верно!")
                    else:
                        send(vk_id, f"❌ Ошибка! Правильно: {quiz['correct']}")
                
                menu = {"inline": True, "buttons": [[
                    {"action": {"type": "text", "label": "🎯 Ещё", "payload": '{"action":"quiz"}'}},
                    {"action": {"type": "text", "label": "📊 Стат", "payload": '{"action":"stats"}'}}
                ]]}
                send(vk_id, "Что дальше?", menu)
            
            elif a == 'quiz': handle_quiz(vk_id)
            elif a == 'stats': handle_stats(vk_id)
        except: pass
        return
    
    # Команды
    t = text.lower()
    if t in ['/start', 'start', 'привет']:
        user = api_post('/api/vk/get-user/', {'vk_id': vk_id})
        if user and user.get('found'):
            user_data[vk_id] = {'user_id': user['user_id'], 'username': user['username']}
            send(vk_id, f"👋 Привет, {user['username']}!\n\nКоманды: квиз, ударение, статистика")
        else:
            send(vk_id, "🔗 Привяжи аккаунт:\n1. Сайт → Профиль → Получить код\n2. Отправь код сюда")
    
    elif t in ['квиз', 'орфография']:
        handle_quiz(vk_id)
    elif t in ['ударение', 'орфоэпия']:
        handle_orthoepy(vk_id)
    elif t in ['статистика', 'stats']:
        handle_stats(vk_id)
    elif len(text) == 8 and text.isalnum():
        res = api_post('/api/vk/verify-code/', {'code': text.upper(), 'vk_id': vk_id})
        if res and res.get('success'):
            user_data[vk_id] = {'user_id': res['user_id'], 'username': res['username']}
            send(vk_id, f"✅ Привязан! Привет, {res['username']}!")
        else:
            send(vk_id, "❌ Код не подошёл")
    else:
        send(vk_id, "❓ Неизвестно. Попробуй: квиз, ударение, статистика")


def handle_quiz(vk_id):
    if vk_id not in user_data:
        return send(vk_id, "❌ Сначала /start")
    
    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/daily-quiz/", json={'user_id': user_data[vk_id]['user_id']}, timeout=5)
        quiz = r.json() if r.status_code == 200 else None
        
        if quiz and 'options' in quiz:
            opts = quiz['options']
            correct = opts[0]['text'] if opts[0]['is_correct'] else opts[1]['text']
            incorrect = opts[1]['text'] if opts[0]['is_correct'] else opts[0]['text']
            
            if random.choice([True, False]):
                left, right, lc = correct, incorrect, True
            else:
                left, right, lc = incorrect, correct, False
            
            user_data[vk_id]['last'] = {
                'id': quiz.get('example_id'),
                'correct': correct,
                'exp': quiz.get('explanation', '')
            }
            send(vk_id, f"❓ {quiz.get('question', 'Как пишется?')}", make_keyboard(quiz['example_id'], left, right, lc))
    except: send(vk_id, "⚠️ Ошибка")


def handle_orthoepy(vk_id):
    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/get-orthoepy-pair/", json={}, timeout=5)
        pair = r.json() if r.status_code == 200 else None
        
        if pair and pair.get('variant1'):
            v1, v2, cor = pair['variant1'], pair['variant2'], pair['correct']
            if random.choice([True, False]):
                left, right = v1, v2
            else:
                left, right = v2, v1
            
            user_data[vk_id]['last'] = {'id': pair['id'], 'correct': cor}
            send(vk_id, "❓ Как правильно?", make_keyboard(pair['id'], left, right))
    except: send(vk_id, "⚠️ Ошибка")


def handle_stats(vk_id):
    if vk_id not in user_data:
        return send(vk_id, "❌ Сначала /start")
    
    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
        r = requests.post(f"{API_URL}/api/weekly-report/", json={'user_id': user_data[vk_id]['user_id']}, timeout=5)
        if r.status_code == 200:
            s = r.json()
            send(vk_id, f"📊 Статистика\n📚 Слов: {s.get('total_words',0)}\n🎯 Попыток: {s.get('total_attempts',0)}\n✅ Правильно: {s.get('correct_answers',0)}\n📈 {s.get('success_rate',0)}%")
    except: send(vk_id, "📊 Ошибка")


# Запуск
if __name__ == '__main__':
    print("✅ Бот запущен")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            try: handle(event)
            except: pass