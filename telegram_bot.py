# telegram_bot.py
"""
Telegram-бот Нейростата. Тонкий адаптер над main.bot_core.

Long Polling getUpdates на чистом requests (без aiogram/telebot):
аудитория бота школьники, лишние зависимости = лишние секунды и риски.
Вся логика (квизы, статистика, привязка, свободный чат) — в bot_core.

Запуск:  python telegram_bot.py   (systemd-сервис neurostat-telegram.service)
"""
import os
import sys
import json
import logging
import time

import requests
import django

# --- Поднимаем Django ДО импорта проектных модулей ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from main import bot_core

# --- Настройка логирования ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger('telegram_bot')

TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TG_API = f'https://api.telegram.org/bot{TG_TOKEN}' if TG_TOKEN else None
# api.telegram.org недоступен с российских IP: при наличии прокси
# (например, http://login:pass@host:port) все запросы идут через него.
TG_PROXY = os.getenv('TELEGRAM_PROXY')
PROXIES = {'http': TG_PROXY, 'https': TG_PROXY} if TG_PROXY else None
POLL_INTERVAL = 2  # секунд между опросами при сбое

# --- Состояние в памяти процесса (сбрасывается при рестарте — допустимо) ---
pending_questions = {}   # chat_id -> dict квиза из bot_core
_chat_hinted = set()     # chat_id, кому уже показали подсказку о привязке
user_data = {}           # chat_id -> {'last_mode': str, 'hot_index': int}
_last_simplify = {}      # chat_id -> последний вопрос для «Объясни проще»

MODES = {'personalized', 'orthography', 'orthoepy', 'hot_word', 'weak'}

LINK_PROMPT = (
    '🔗 Сначала привяжи аккаунт с сайта:\n'
    '1. Сайт → Личный кабинет → «Получить код привязки»\n'
    '2. Отправь этот код сюда одним сообщением'
)
ACCESS_DENIED = (
    '⚠️ Тренировки в боте доступны на платных тарифах '
    '(«Я сам», «Вместе», «Премиум») и на триале.\n'
    'Выбрать тариф: https://neurostat.ru/profile/'
)


# ========================================================================
# HTTP-СЛОЙ TELEGRAM
# ========================================================================

def _api(method: str, **body):
    if not TG_API:
        log.error('TELEGRAM_BOT_TOKEN не задан в .env')
        return None
    try:
        r = requests.post(f'{TG_API}/{method}', json=body, timeout=(5, 40),
                          proxies=PROXIES)
        if r.status_code != 200:
            log.error(f'TG {method} -> {r.status_code}: {r.text[:300]}')
        return r
    except Exception as e:
        log.error(f'TG request error {method}: {e}')
        return None


# У Telegram лимит callback_data 64 байта: длинные payload'ы оркестратора
# держим в памяти процесса под коротким ключом.
_cb_store = {}
_cb_seq = 0


def _cb(payload: dict) -> str:
    global _cb_seq
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode('utf-8')) <= 64:
        return raw
    _cb_seq += 1
    key = f'k{_cb_seq}'
    _cb_store[key] = payload
    while len(_cb_store) > 500:
        _cb_store.pop(next(iter(_cb_store)))
    return json.dumps({'k': key})


def _cb_resolve(data: str) -> dict:
    try:
        d = json.loads(data)
    except Exception:
        return {}
    if isinstance(d, dict) and set(d) == {'k'}:
        return _cb_store.pop(d['k'], {})
    return d if isinstance(d, dict) else {}


# ========================================================================
# ОТПРАВКА / КЛАВИАТУРЫ
# ========================================================================

def send(chat_id, text, buttons=None):
    """buttons: список рядов, ряд = список {'label': str, 'payload': dict}."""
    body = {'chat_id': chat_id, 'text': text}
    if buttons:
        body['reply_markup'] = {'inline_keyboard': [
            [{'text': b['label'][:64], 'callback_data': _cb(b['payload'])}
             for b in row]
            for row in buttons]}
    _api('sendMessage', **body)


def _btn(label, payload):
    return {'label': label[:64], 'payload': payload}


def kb_main_menu():
    return [
        [_btn('📖 Мои слова', {'a': 'personalized'}),
         _btn('📝 Орфография', {'a': 'orthography'})],
        [_btn('🎯 Ударения', {'a': 'orthoepy'}),
         _btn('🔥 Горячие', {'a': 'hot_word'}),
         _btn('📊 Стат.', {'a': 'stats'})],
    ]


def kb_next(mode):
    return [[
        _btn('🎯 Ещё', {'a': mode}),
        _btn('📊 Стат.', {'a': 'stats'}),
        _btn('🏠 Меню', {'a': 'menu'}),
    ]]


# ========================================================================
# ДОСТУП
# ========================================================================

def get_active_profile(tg_id):
    """(profile, None) либо (None, текст отказа)."""
    profile = bot_core.get_profile_by_platform('telegram', tg_id)
    if not profile:
        return None, LINK_PROMPT
    if not bot_core.user_can_use_bot(profile):
        return None, ACCESS_DENIED
    return profile, None


# ========================================================================
# КВИЗЫ
# ========================================================================

def send_quiz(chat_id, profile, mode):
    index = 0
    if mode == 'hot_word':
        index = user_data.setdefault(chat_id, {}).get('hot_index', 0)

    quiz = bot_core.get_quiz(profile, mode, index=index)

    if not quiz.get('available'):
        send(chat_id, quiz.get('message') or 'Вопросы пока закончились. Попробуй позже.')
        return

    if mode == 'hot_word' and 'next_index' in quiz:
        user_data.setdefault(chat_id, {})['hot_index'] = quiz['next_index']

    user_data.setdefault(chat_id, {})['last_mode'] = mode
    pending_questions[chat_id] = quiz

    buttons = []
    for i, opt in enumerate(quiz.get('options', [])):
        buttons.append([_btn(str(opt['text']), {'a': 'answer', 'i': i})])

    send(chat_id, f"❓ {quiz['question']}", buttons)


def handle_answer(chat_id, tg_id, idx):
    profile, err = get_active_profile(tg_id)
    if err:
        return send(chat_id, err)

    quiz = pending_questions.pop(chat_id, None)
    if not quiz:
        return send(chat_id, 'Вопрос устарел. Нажми /start и выбери тренировку заново.')

    options = quiz.get('options') or []
    if not isinstance(idx, int) or not (0 <= idx < len(options)):
        return send(chat_id, 'Не понял ответ. Попробуй ещё раз.')

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

    send(chat_id, text)
    last_mode = user_data.get(chat_id, {}).get('last_mode', 'personalized')
    send(chat_id, 'Что дальше?', kb_next(last_mode))


# ========================================================================
# СТАТИСТИКА / МЕНЮ / ПРИВЯЗКА / СЛОВО ДНЯ
# ========================================================================

def handle_stats(chat_id, tg_id):
    profile, err = get_active_profile(tg_id)
    if err:
        return send(chat_id, err)
    try:
        stats = bot_core.get_stats(profile)
        send(chat_id, bot_core.format_stats_message(stats))
    except Exception as e:
        log.exception(f'Stats error: {e}')
        send(chat_id, '⚠️ Не удалось загрузить статистику')


def send_help(chat_id):
    send(chat_id,
         '📚 Команды:\n'
         '• /start — главное меню\n'
         '• мои слова — квиз из твоего планинга\n'
         '• орфография — вопросы из эталонной базы\n'
         '• ударения — тренировка ударений\n'
         '• горячие — горячие слова ЕГЭ\n'
         '• статистика — твой прогресс за неделю')


def handle_start(chat_id, tg_id):
    profile = bot_core.get_profile_by_platform('telegram', tg_id)
    if not profile:
        return send(chat_id, LINK_PROMPT)
    if not bot_core.user_can_use_bot(profile):
        return send(chat_id, ACCESS_DENIED)
    name = profile.first_name or profile.user.first_name or 'друг'
    send(chat_id, f'👋 Привет, {name}! Главное меню:', kb_main_menu())


def handle_link_code(chat_id, tg_id, code):
    res = bot_core.link_by_code(code, 'telegram', tg_id)
    if res['success']:
        send(chat_id, f"✅ Привязан! Привет, {res['username']}!")
        send(chat_id, 'Главное меню:', kb_main_menu())
    else:
        send(chat_id, res['message'])


def handle_daily_answer(chat_id, tg_id, idx):
    profile, err = get_active_profile(tg_id)
    if err:
        return send(chat_id, err)
    state = bot_core.get_daily_word_state(profile)
    if state.get('state') != 'revealed':
        return send(chat_id, 'Слово дня уже отвечено или ещё не открыто.')
    res = bot_core.answer_daily_word(profile, state['period_date'], idx)
    if res.get('status') == 'already':
        return send(chat_id, 'Слово дня уже отвечено.')
    if res.get('was_correct'):
        text = '✅ Верно!'
    else:
        text = f"❌ Ошибка! Правильно: {res.get('correct_text') or '?'}"
    if res.get('explanation'):
        text += f"\n📚 {res['explanation']}"
    send(chat_id, text)


# ========================================================================
# ДИСПЕТЧЕР ТЕКСТА И КНОПОК
# ========================================================================

def handle_text(chat_id, tg_id, text):
    cmd = (text or '').strip().lower()

    if cmd in ('/start', 'start', 'привет', 'меню', 'menu'):
        handle_start(chat_id, tg_id)
    elif cmd in ('мои слова', 'планинг', 'planning'):
        p, err = get_active_profile(tg_id)
        send(chat_id, err) if err else send_quiz(chat_id, p, 'personalized')
    elif cmd in ('орфография', 'все орф.', 'orthography'):
        p, err = get_active_profile(tg_id)
        send(chat_id, err) if err else send_quiz(chat_id, p, 'orthography')
    elif cmd in ('ударение', 'ударения', 'орфоэпия', 'orthoepy'):
        p, err = get_active_profile(tg_id)
        send(chat_id, err) if err else send_quiz(chat_id, p, 'orthoepy')
    elif cmd in ('горячие', 'hot'):
        p, err = get_active_profile(tg_id)
        send(chat_id, err) if err else send_quiz(chat_id, p, 'hot_word')
    elif cmd in ('статистика', 'stats'):
        handle_stats(chat_id, tg_id)
    elif cmd in ('помощь', 'help'):
        send_help(chat_id)
    elif len(text) == 8 and text.isalnum():
        handle_link_code(chat_id, tg_id, text)
    else:
        res = bot_core.free_chat('telegram', tg_id, text)
        if not res['allowed']:
            return send(chat_id, LINK_PROMPT)
        reply = res['reply']
        if not res['linked'] and tg_id not in _chat_hinted:
            _chat_hinted.add(tg_id)
            reply += ('\n\n🔗 Хочешь личные квизы и статистику? '
                      'Привяжи аккаунт: пришли код из личного кабинета.')
        rows = [[_btn(b['label'], b['payload']) for b in row]
                for row in (res.get('buttons') or [])]
        if res.get('simplifiable'):
            _last_simplify[tg_id] = text
            rows.append([_btn('🧒 Простыми словами', {'a': 'simplify'})])
        send(chat_id, reply, buttons=rows or None)


def handle_callback(chat_id, tg_id, payload_str):
    data = _cb_resolve(payload_str)
    action = data.get('a') or data.get('action')

    if action == 'answer':
        handle_answer(chat_id, tg_id, data.get('i', -1))
    elif action == 'planning':
        p, err = get_active_profile(tg_id)
        send(chat_id, err) if err else send_quiz(chat_id, p, 'personalized')
    elif action in ('all_orthography', 'ortho'):
        p, err = get_active_profile(tg_id)
        send(chat_id, err) if err else send_quiz(chat_id, p, 'orthography')
    elif action in MODES:
        p, err = get_active_profile(tg_id)
        send(chat_id, err) if err else send_quiz(chat_id, p, action)
    elif action == 'stats':
        handle_stats(chat_id, tg_id)
    elif action == 'help':
        send_help(chat_id)
    elif action == 'menu':
        handle_start(chat_id, tg_id)
    elif action == 'daily_answer':
        handle_daily_answer(chat_id, tg_id, data.get('i', -1))
    elif action == 'sales_goal':
        p, _err = get_active_profile(tg_id)
        send(chat_id, bot_core.sales_goal_answer(p, data.get('g')))
    elif action == 'simplify':
        q = _last_simplify.pop(tg_id, None)
        if not q:
            send(chat_id, 'Пришли вопрос ещё раз — объясню проще 🙂')
        else:
            r2 = bot_core.free_chat('telegram', tg_id, q, simplify=True)
            send(chat_id, r2['reply'])


# ========================================================================
# РАЗБОР ОБНОВЛЕНИЙ
# ========================================================================

def handle_update(upd):
    if 'callback_query' in upd:
        cq = upd['callback_query']
        msg = cq.get('message') or {}
        chat_id = (msg.get('chat') or {}).get('id')
        tg_id = (cq.get('from') or {}).get('id')
        _api('answerCallbackQuery', callback_query_id=cq.get('id'))
        if chat_id and tg_id and cq.get('data'):
            handle_callback(chat_id, tg_id, cq['data'])
        return

    msg = upd.get('message')
    if not msg:
        return
    chat = msg.get('chat') or {}
    if chat.get('type') != 'private':
        return  # групповые чаты не обслуживаем, как и в VK/MAX
    chat_id = chat.get('id')
    tg_id = (msg.get('from') or {}).get('id')
    text = (msg.get('text') or '').strip()
    if chat_id and tg_id and text:
        handle_text(chat_id, tg_id, text)


# ========================================================================
# LONG POLLING
# ========================================================================

def poll_loop():
    offset = None
    log.info('Telegram Bot starting (long polling, bot_core mode)...')
    while True:
        try:
            params = {'timeout': 50,
                      'allowed_updates': ['message', 'callback_query']}
            if offset is not None:
                params['offset'] = offset
            r = requests.get(f'{TG_API}/getUpdates', params=params,
                             timeout=(5, 60), proxies=PROXIES)
            if r is None or r.status_code != 200:
                time.sleep(POLL_INTERVAL)
                continue
            data = r.json()
            for upd in data.get('result', []):
                offset = max(offset or 0, upd['update_id'] + 1)
                try:
                    handle_update(upd)
                except Exception as e:
                    log.exception(f'handle_update error: {e}')
        except Exception as e:
            log.exception(f'Poll error: {e}')
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':
    if not TG_TOKEN:
        log.error('TELEGRAM_BOT_TOKEN не задан в .env — бот не запустится.')
        sys.exit(1)
    log.info(f'Proxy: {"yes" if TG_PROXY else "no (direct)"}')
    poll_loop()
