# vk_bot.py
"""
VK-бот Нейростата. Тонкий адаптер над main.bot_core.

Получает события через Long Polling; вся логика (квизы, статистика,
привязка) — в bot_core прямыми вызовами ORM, без HTTP.

Запуск:  python vk_bot.py   (systemd-сервис vk-bot.service)
"""
import os
import sys
import json
import logging

import django

# --- Поднимаем Django ДО импорта проектных модулей ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.utils import get_random_id

from main import bot_core

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('vk_bot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger('vk_bot')

VK_TOKEN = os.getenv('VK_GROUP_TOKEN')
VK_GROUP_ID = int(os.getenv('VK_GROUP_ID', 0))

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, VK_GROUP_ID)

# --- Состояние в памяти процесса (сбрасывается при рестарте — допустимо) ---
pending_questions = {}   # vk_id -> dict квиза из bot_core
_chat_hinted = set()       # vk_id, кому уже показали подсказку о привязке
user_data = {}           # vk_id -> {'last_mode': str, 'hot_index': int}

LINK_PROMPT = (
    '🔗 Сначала привяжи аккаунт с сайта:\n'
    '1. Сайт → Личный кабинет → блок VK → «Получить код»\n'
    '2. Отправь этот код сюда'
)
ACCESS_DENIED = (
    '⚠️ Тренировки в боте доступны на платных тарифах '
    '(«Я сам», «Вместе», «Премиум») и на триале.\n'
    'Выбрать тариф: https://neurostat.ru/profile/'
)

MODES = {'personalized', 'orthography', 'orthoepy', 'hot_word', 'weak'}
_last_simplify = {}  # последний вопрос для кнопки «Объясни проще»


# ========================================================================
# ОТПРАВКА / КЛАВИАТУРЫ
# ========================================================================

def send(user_id, text, keyboard=None):
    try:
        params = {'user_id': user_id, 'message': text, 'random_id': get_random_id()}
        if keyboard:
            params['keyboard'] = json.dumps(keyboard, ensure_ascii=False)
        vk.messages.send(**params)
    except Exception as e:
        log.error(f'VK send error: {e}')


def _btn(label, payload):
    return {'action': {'type': 'text', 'label': label,
                       'payload': json.dumps(payload, ensure_ascii=False)}}


def kb_main_menu():
    return {
        'inline': True,
        'buttons': [
            [_btn('📖 Мои слова', {'a': 'personalized'}),
             _btn('📝 Орфография', {'a': 'orthography'})],
            [_btn('🎯 Ударения', {'a': 'orthoepy'}),
             _btn('🔥 Горячие', {'a': 'hot_word'}),
             _btn('📊 Стат.', {'a': 'stats'})],
        ],
    }


def kb_next(mode):
    return {
        'inline': True,
        'buttons': [[
            _btn('🎯 Ещё', {'a': mode}),
            _btn('📊 Стат.', {'a': 'stats'}),
            _btn('🏠 Меню', {'a': 'menu'}),
        ]],
    }


def set_activity(vk_id):
    try:
        vk.messages.setActivity(user_id=vk_id, type='typing')
    except Exception:
        pass


# ========================================================================
# ДОСТУП
# ========================================================================

def get_active_profile(vk_id):
    """Возвращает (profile, None) либо (None, текст для отправки)."""
    profile = bot_core.get_profile_by_platform('vk', vk_id)
    if not profile:
        return None, LINK_PROMPT
    if not bot_core.user_can_use_bot(profile):
        return None, ACCESS_DENIED
    return profile, None


# ========================================================================
# КВИЗЫ
# ========================================================================

def send_quiz(vk_id, profile, mode):
    index = 0
    if mode == 'hot_word':
        index = user_data.setdefault(vk_id, {}).get('hot_index', 0)

    set_activity(vk_id)
    quiz = bot_core.get_quiz(profile, mode, index=index)

    if not quiz.get('available'):
        send(vk_id, quiz.get('message') or 'Вопросы пока закончились. Попробуй позже.')
        return

    if mode == 'hot_word' and 'next_index' in quiz:
        user_data.setdefault(vk_id, {})['hot_index'] = quiz['next_index']

    user_data.setdefault(vk_id, {})['last_mode'] = mode
    pending_questions[vk_id] = quiz

    buttons = []
    for i, opt in enumerate(quiz.get('options', [])):
        buttons.append([_btn(str(opt['text'])[:40], {'a': 'answer', 'i': i})])

    send(vk_id, f"❓ {quiz['question']}", {'inline': True, 'buttons': buttons})


def handle_answer(vk_id, idx):
    profile, err = get_active_profile(vk_id)
    if err:
        return send(vk_id, err)

    quiz = pending_questions.pop(vk_id, None)
    if not quiz:
        return send(vk_id, 'Вопрос устарел. Нажми /start и выбери тренировку заново.')

    options = quiz.get('options') or []
    if not isinstance(idx, int) or not (0 <= idx < len(options)):
        return send(vk_id, 'Не понял ответ. Попробуй ещё раз.')

    selected = options[idx]
    was_correct = bool(selected.get('is_correct'))

    result = bot_core.log_answer(
        profile,
        quiz.get('example_id'),
        quiz.get('user_word_id'),
        was_correct,
    )

    explanation = result.get('explanation') or ''
    correct_text = result.get('correct_text') or quiz.get('correct_text') or '?'

    if was_correct:
        text = '✅ Верно!'
        if explanation:
            text += f'\n📚 {explanation}'
    else:
        text = f'❌ Ошибка! Правильно: {correct_text}'
        if explanation:
            text += f'\n📚 {explanation}'

    send(vk_id, text)

    last_mode = user_data.get(vk_id, {}).get('last_mode', 'personalized')
    send(vk_id, 'Что дальше?', kb_next(last_mode))


# ========================================================================
# СТАТИСТИКА / СПРАВКА / МЕНЮ
# ========================================================================

def handle_stats(vk_id):
    profile, err = get_active_profile(vk_id)
    if err:
        return send(vk_id, err)
    set_activity(vk_id)
    try:
        stats = bot_core.get_stats(profile)
        send(vk_id, bot_core.format_stats_message(stats))
    except Exception as e:
        log.exception(f'Stats error: {e}')
        send(vk_id, '⚠️ Не удалось загрузить статистику')


def send_help(vk_id):
    send(vk_id,
         '📚 Команды:\n'
         '• /start — главное меню\n'
         '• мои слова — квиз из твоего планинга\n'
         '• орфография — вопросы из эталонной базы\n'
         '• ударения — тренировка ударений\n'
         '• горячие — горячие слова ЕГЭ\n'
         '• статистика — твой прогресс за неделю')


def handle_start(vk_id):
    profile = bot_core.get_profile_by_platform('vk', vk_id)
    if not profile:
        return send(vk_id, LINK_PROMPT)
    if not bot_core.user_can_use_bot(profile):
        return send(vk_id, ACCESS_DENIED)
    name = profile.first_name or profile.user.first_name or 'друг'
    send(vk_id, f'👋 Привет, {name}! Главное меню:', kb_main_menu())


def handle_link_code(vk_id, code):
    res = bot_core.link_by_code(code, 'vk', vk_id)
    if res['success']:
        send(vk_id, f"✅ Привязан! Привет, {res['username']}!")
        send(vk_id, 'Главное меню:', kb_main_menu())
    else:
        send(vk_id, res['message'])


# ========================================================================
# ДИСПЕТЧЕР СОБЫТИЙ
# ========================================================================

def handle(event):
    obj = event.object
    msg = obj.get('message', {})
    vk_id = msg.get('from_id')
    if not vk_id:
        return

    text = (msg.get('text') or '').strip()
    payload = msg.get('payload')

    # --- Кнопки ---
    if payload:
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
            action = data.get('a') or data.get('action')

            if action == 'answer':
                handle_answer(vk_id, data.get('i', -1))
            elif action in MODES:
                profile, err = get_active_profile(vk_id)
                if err:
                    send(vk_id, err)
                else:
                    send_quiz(vk_id, profile, action)
            elif action in ('planning',):
                profile, err = get_active_profile(vk_id)
                if err:
                    send(vk_id, err)
                else:
                    send_quiz(vk_id, profile, 'personalized')
            elif action in ('all_orthography', 'ortho'):
                profile, err = get_active_profile(vk_id)
                if err:
                    send(vk_id, err)
                else:
                    send_quiz(vk_id, profile, 'orthography')
            elif action == 'stats':
                handle_stats(vk_id)
            elif action == 'help':
                send_help(vk_id)
            elif action == 'menu':
                handle_start(vk_id)
            elif action == 'daily_answer':
                handle_daily_answer(vk_id, data.get('i', -1))
            elif action == 'sales_goal':
                profile, _err = get_active_profile(vk_id)
                send(vk_id, bot_core.sales_goal_answer(profile, data.get('g')))
            elif action == 'simplify':
                q = _last_simplify.pop(vk_id, None)
                if not q:
                    send(vk_id, 'Пришли вопрос ещё раз — объясню проще 🙂')
                else:
                    r2 = bot_core.free_chat('vk', vk_id, q, simplify=True)
                    send(vk_id, r2['reply'])
        except Exception as e:
            log.exception(f'Payload error: {e}')
        return

    # --- Текстовые команды ---
    cmd = text.lower()

    if cmd in ('/start', 'start', 'привет', 'меню', 'menu'):
        handle_start(vk_id)
    elif cmd in ('мои слова', 'планинг', 'planning'):
        profile, err = get_active_profile(vk_id)
        send(vk_id, err) if err else send_quiz(vk_id, profile, 'personalized')
    elif cmd in ('орфография', 'все орф.', 'orthography'):
        profile, err = get_active_profile(vk_id)
        send(vk_id, err) if err else send_quiz(vk_id, profile, 'orthography')
    elif cmd in ('ударение', 'ударения', 'орфоэпия', 'orthoepy'):
        profile, err = get_active_profile(vk_id)
        send(vk_id, err) if err else send_quiz(vk_id, profile, 'orthoepy')
    elif cmd in ('горячие', 'hot'):
        profile, err = get_active_profile(vk_id)
        send(vk_id, err) if err else send_quiz(vk_id, profile, 'hot_word')
    elif cmd in ('статистика', 'stats'):
        handle_stats(vk_id)
    elif cmd in ('помощь', 'help'):
        send_help(vk_id)
    elif len(text) == 8 and text.isalnum():
        handle_link_code(vk_id, text)
    else:
        set_activity(vk_id)
        res = bot_core.free_chat('vk', vk_id, text)
        if not res['allowed']:
            return send(vk_id, LINK_PROMPT)
        reply = res['reply']
        if not res['linked'] and vk_id not in _chat_hinted:
            _chat_hinted.add(vk_id)
            reply += ('\n\n🔗 Хочешь личные квизы и статистику? '
                      'Привяжи аккаунт: пришли код из личного кабинета.')
        rows = [[_btn(b['label'], b['payload']) for b in row]
                for row in (res.get('buttons') or [])]
        if res.get('simplifiable'):
            _last_simplify[vk_id] = text
            rows.append([_btn('🧒 Простыми словами', {'a': 'simplify'})])
        send(vk_id, reply, keyboard={'inline': True, 'buttons': rows} if rows else None)

def handle_daily_answer(vk_id, idx):
    profile, err = get_active_profile(vk_id)
    if err:
        return send(vk_id, err)
    state = bot_core.get_daily_word_state(profile)
    if state.get('state') != 'revealed':
        return send(vk_id, 'Слово дня уже отвечено или ещё не открыто.')
    res = bot_core.answer_daily_word(profile, state['period_date'], idx)
    if res.get('status') == 'already':
        return send(vk_id, 'Слово дня уже отвечено.')
    if res.get('was_correct'):
        text = '✅ Верно!'
    else:
        text = f"❌ Ошибка! Правильно: {res.get('correct_text') or '?'}"
    if res.get('explanation'):
        text += f"\n📚 {res['explanation']}"
    send(vk_id, text)


if __name__ == '__main__':
    log.info('VK Bot starting (bot_core mode)...')
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            try:
                handle(event)
            except Exception as e:
                log.exception(f'Global error: {e}')
