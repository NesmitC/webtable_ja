# max_bot.py
"""
MAX-бот Нейростата. Тонкий адаптер над main.bot_core.

Локальная разработка: Long Polling (GET /updates), публичный HTTPS не нужен.
Продакшн: Webhook — обработчик будет в Django views (POST /subscriptions).

Запуск:  python max_bot.py
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
        logging.FileHandler('max_bot.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger('max_bot')

MAX_TOKEN = os.getenv('MAX_BOT_TOKEN')
MAX_API = 'https://platform-api2.max.ru'
DEBUG = True          # логируем сырые запросы/ответы MAX (отключить на проде)
POLL_INTERVAL = 2     # секунд между опросами

CA_BUNDLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'certs', 'bundle.pem')


# --- Состояние в памяти процесса ---
pending_questions = {}   # chat_id -> dict квиза из bot_core
_chat_hinted = set()       # кому уже показали подсказку о привязке
user_data = {}           # chat_id -> {'last_mode': str, 'hot_index': int}
_seen_updates = set()    # чтобы не обрабатывать одно обновление дважды

LINK_PROMPT = (
    '🔗 Сначала привяжи аккаунт с сайта:\n'
    '1. Сайт → Личный кабинет → блок MAX → «Получить код»\n'
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
# HTTP-слой MAX
# ========================================================================

def _headers():
    return {'Authorization': MAX_TOKEN, 'Content-Type': 'application/json'}


def _max_request(method, path, params=None, json_body=None, timeout=(5, 40)):
    url = f'{MAX_API}{path}'
    verify = CA_BUNDLE if os.path.exists(CA_BUNDLE) else True
    try:
        r = requests.request(method, url, headers=_headers(),
                             params=params, json=json_body, timeout=timeout, verify=verify)
        if DEBUG:
            log.info(f'MAX {method} {path} -> {r.status_code}')
            log.info(f'  resp: {r.text[:600]}')
        return r
    except Exception as e:
        log.error(f'MAX request error {path}: {e}')
        return None




def send_message(chat_id, text, buttons=None):
    """
    Отправить сообщение. buttons: список рядов, ряд = список
    {'label': str, 'payload': str}.

    ВНИМАНИЕ: точное расположение chat_id (query vs body) сверяем по DEBUG-логу.
    """
    body = {'text': text}
    if buttons:
        kb_rows = []
        for row in buttons:
            kb_rows.append([
                {'type': 'callback', 'text': b['label'], 'payload': b['payload']}
                for b in row
            ])
        body['attachments'] = [{'type': 'inline_keyboard', 'payload': {'buttons': kb_rows}}]

    _max_request('POST', '/messages', params={'chat_id': chat_id}, json_body=body)


def _btn(label, payload_dict):
    return {'label': label[:40], 'payload': json.dumps(payload_dict, ensure_ascii=False)}


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

def get_active_profile(max_id):
    """(profile, None) либо (None, текст отказа)."""
    profile = bot_core.get_profile_by_platform('max', max_id)
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
        send_message(chat_id, quiz.get('message') or 'Вопросы пока закончились.')
        return

    if mode == 'hot_word' and 'next_index' in quiz:
        user_data.setdefault(chat_id, {})['hot_index'] = quiz['next_index']

    user_data.setdefault(chat_id, {})['last_mode'] = mode
    pending_questions[chat_id] = quiz

    buttons = []
    for i, opt in enumerate(quiz.get('options', [])):
        buttons.append([_btn(str(opt['text']), {'a': 'answer', 'i': i})])

    send_message(chat_id, f"❓ {quiz['question']}", buttons)


def handle_answer(chat_id, max_id, idx):
    profile, err = get_active_profile(max_id)
    if err:
        return send_message(chat_id, err)

    quiz = pending_questions.pop(chat_id, None)
    if not quiz:
        return send_message(chat_id, 'Вопрос устарел. /start — выбери тренировку заново.')

    options = quiz.get('options') or []
    if not isinstance(idx, int) or not (0 <= idx < len(options)):
        return send_message(chat_id, 'Не понял ответ. Попробуй ещё раз.')

    selected = options[idx]
    was_correct = bool(selected.get('is_correct'))

    result = bot_core.log_answer(profile, quiz.get('example_id'),
                                 quiz.get('user_word_id'), was_correct)
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

    send_message(chat_id, text)
    last_mode = user_data.get(chat_id, {}).get('last_mode', 'personalized')
    send_message(chat_id, 'Что дальше?', kb_next(last_mode))


# ========================================================================
# СТАТИСТИКА / МЕНЮ / ПРИВЯЗКА
# ========================================================================

def handle_stats(chat_id, max_id):
    profile, err = get_active_profile(max_id)
    if err:
        return send_message(chat_id, err)
    try:
        stats = bot_core.get_stats(profile)
        send_message(chat_id, bot_core.format_stats_message(stats))
    except Exception as e:
        log.exception(f'Stats error: {e}')
        send_message(chat_id, '⚠️ Не удалось загрузить статистику')


def handle_start(chat_id, max_id):
    profile = bot_core.get_profile_by_platform('max', max_id)
    if not profile:
        return send_message(chat_id, LINK_PROMPT)
    if not bot_core.user_can_use_bot(profile):
        return send_message(chat_id, ACCESS_DENIED)
    name = profile.first_name or profile.user.first_name or 'друг'
    send_message(chat_id, f'👋 Привет, {name}! Главное меню:', kb_main_menu())


def handle_link_code(chat_id, max_id, code):
    res = bot_core.link_by_code(code, 'max', max_id)
    if res['success']:
        send_message(chat_id, f"✅ Привязан! Привет, {res['username']}!")
        send_message(chat_id, 'Главное меню:', kb_main_menu())
    else:
        send_message(chat_id, res['message'])


def send_help(chat_id):
    send_message(chat_id,
                 '📚 Команды:\n'
                 '• /start — главное меню\n'
                 '• мои слова — квиз из твоего планинга\n'
                 '• орфография — вопросы из эталонной базы\n'
                 '• ударения — тренировка ударений\n'
                 '• горячие — горячие слова ЕГЭ\n'
                 '• статистика — твой прогресс за неделю')


# ========================================================================
# ДИСПЕТЧЕР ТЕКСТА И КНОПОК
# ========================================================================

def handle_text(chat_id, max_id, text):
    cmd = (text or '').strip().lower()

    if cmd in ('/start', 'start', 'привет', 'меню', 'menu'):
        handle_start(chat_id, max_id)
    elif cmd in ('мои слова', 'планинг', 'planning'):
        p, err = get_active_profile(max_id)
        send_message(chat_id, err) if err else send_quiz(chat_id, p, 'personalized')
    elif cmd in ('орфография', 'все орф.', 'orthography'):
        p, err = get_active_profile(max_id)
        send_message(chat_id, err) if err else send_quiz(chat_id, p, 'orthography')
    elif cmd in ('ударение', 'ударения', 'орфоэпия', 'orthoepy'):
        p, err = get_active_profile(max_id)
        send_message(chat_id, err) if err else send_quiz(chat_id, p, 'orthoepy')
    elif cmd in ('горячие', 'hot'):
        p, err = get_active_profile(max_id)
        send_message(chat_id, err) if err else send_quiz(chat_id, p, 'hot_word')
    elif cmd in ('статистика', 'stats'):
        handle_stats(chat_id, max_id)
    elif cmd in ('помощь', 'help'):
        send_help(chat_id)
    elif len(text) == 8 and text.isalnum():
        handle_link_code(chat_id, max_id, text)
    else:
        res = bot_core.free_chat('max', max_id, text)
        if not res['allowed']:
            return send_message(chat_id, LINK_PROMPT)
        reply = res['reply']
        if not res['linked'] and max_id not in _chat_hinted:
            _chat_hinted.add(max_id)
            reply += ('\n\n🔗 Хочешь личные квизы и статистику? '
                      'Привяжи аккаунт: пришли код из личного кабинета.')
        rows = [[{'label': b['label'][:40],
                 'payload': json.dumps(b['payload'], ensure_ascii=False)}
                for b in row] for row in (res.get('buttons') or [])]
        if res.get('simplifiable'):
            _last_simplify[max_id] = text
            rows.append([{'label': '🧒 Простыми словами',
                          'payload': json.dumps({'a': 'simplify'}, ensure_ascii=False)}])
        send_message(chat_id, reply, buttons=rows or None)


def handle_callback(chat_id, max_id, payload_str):
    try:
        data = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
    except Exception:
        return
    action = data.get('a') or data.get('action')

    if action == 'answer':
        handle_answer(chat_id, max_id, data.get('i', -1))
    elif action == 'planning':
        p, err = get_active_profile(max_id)
        send_message(chat_id, err) if err else send_quiz(chat_id, p, 'personalized')
    elif action in ('all_orthography', 'ortho'):
        p, err = get_active_profile(max_id)
        send_message(chat_id, err) if err else send_quiz(chat_id, p, 'orthography')
    elif action in MODES:
        p, err = get_active_profile(max_id)
        send_message(chat_id, err) if err else send_quiz(chat_id, p, action)
    elif action == 'stats':
        handle_stats(chat_id, max_id)
    elif action == 'help':
        send_help(chat_id)
    elif action == 'menu':
        handle_start(chat_id, max_id)
    elif action == 'daily_answer':
        handle_daily_answer(chat_id, max_id, data.get('i', -1))
    elif action == 'sales_goal':
        p, _err = get_active_profile(max_id)
        send_message(chat_id, bot_core.sales_goal_answer(p, data.get('g')))
    elif action == 'simplify':
        q = _last_simplify.pop(max_id, None)
        if not q:
            send_message(chat_id, 'Пришли вопрос ещё раз — объясню проще 🙂')
        else:
            r2 = bot_core.free_chat('max', max_id, q, simplify=True)
            send_message(chat_id, r2['reply'])

def handle_daily_answer(chat_id, max_id, idx):
    profile, err = get_active_profile(max_id)
    if err:
        return send_message(chat_id, err)
    state = bot_core.get_daily_word_state(profile)
    if state.get('state') != 'revealed':
        return send_message(chat_id, 'Слово дня уже отвечено или ещё не открыто.')
    res = bot_core.answer_daily_word(profile, state['period_date'], idx)
    if res.get('status') == 'already':
        return send_message(chat_id, 'Слово дня уже отвечено.')
    if res.get('was_correct'):
        text = '✅ Верно!'
    else:
        text = f"❌ Ошибка! Правильно: {res.get('correct_text') or '?'}"
    if res.get('explanation'):
        text += f"\n📚 {res['explanation']}"
    send_message(chat_id, text)

# ========================================================================
# РАЗБОР ОБНОВЛЕНИЙ (адаптируется по DEBUG-логу)
# ========================================================================
def handle_update(upd):
    utype = upd.get('update_type')
    if DEBUG:
        log.info(f'UPDATE {utype}: {json.dumps(upd, ensure_ascii=False)[:800]}')

    callback = upd.get('callback') or {}
    msg = upd.get('message') or {}
    body = msg.get('body') or {}
    recipient = msg.get('recipient') or {}
    sender = msg.get('sender') or {}

    # user_id: callback.user (кнопка) / message.sender (текст) / user (bot_started)
    user = callback.get('user') or sender or upd.get('user') or {}
    max_id = user.get('user_id')

    # chat_id: message.recipient.chat_id / chat_id (bot_started)
    chat_id = recipient.get('chat_id') or upd.get('chat_id') or max_id

    if not max_id or not chat_id:
        log.warning(f'Не удалось определить user/chat: max_id={max_id}, '
                    f'chat_id={chat_id}, utype={utype}')
        return
    # Запоминаем chat_id для будущих рассылок
    bot_core.remember_max_chat(max_id, chat_id)

    if utype == 'bot_started':
        # Первый запуск / переход по диплинку https://max.ru/<ник>?start=<код>
        payload = upd.get('payload')
        if payload:
            handle_link_code(chat_id, max_id, payload)
        else:
            handle_start(chat_id, max_id)

    elif utype == 'message_created':
        text = body.get('text') or upd.get('text') or ''
        if text:
            handle_text(chat_id, max_id, text)

    elif utype == 'message_callback':
        payload_str = callback.get('payload')
        if payload_str:
            handle_callback(chat_id, max_id, payload_str)

    else:
        log.info(f'Необработанный тип события: {utype}')
        


# ========================================================================
# LONG POLLING (для локальной разработки)
# ========================================================================

def poll_loop():
    marker = None
    log.info('MAX Bot starting (long polling, bot_core mode)...')
    while True:
        try:
            params = {'timeout': 30}   # сколько секунд сервер ждёт события
            if marker is not None:
                params['marker'] = marker
            r = _max_request('GET', '/updates', params=params)

            if r is None or r.status_code != 200:
                time.sleep(POLL_INTERVAL)
                continue

            data = r.json()
            updates = data.get('updates') if isinstance(data, dict) else data
            if isinstance(updates, list):
                for upd in updates:
                    uid = upd.get('update_id') or upd.get('timestamp') or id(upd)
                    if uid in _seen_updates:
                        continue
                    _seen_updates.add(uid)
                    try:
                        handle_update(upd)
                    except Exception as e:
                        log.exception(f'handle_update error: {e}')
                # обновляем курсор (поле сверяем по DEBUG-логу)
                marker = data.get('marker') or marker if isinstance(data, dict) else marker

        except Exception as e:
            log.exception(f'Poll error: {e}')
            time.sleep(POLL_INTERVAL)



if __name__ == '__main__':
    if not MAX_TOKEN:
        log.error('MAX_BOT_TOKEN не задан в .env — бот не запустится.')
        sys.exit(1)
    log.info(f'CA_BUNDLE path: {CA_BUNDLE}')
    log.info(f'CA_BUNDLE exists: {os.path.exists(CA_BUNDLE)}')

    poll_loop()
