# -*- coding: utf-8 -*-
"""Тест Telegram-адаптера: привязка кодом, меню, квиз, ответ, статистика,
свободный чат, слово дня, лимит callback_data. Сеть не трогается:
telegram_bot.send и LLM-ветки bot_core подменяются.
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_telegram_bot.py
"""
import json
import os
import sys
from datetime import timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main import bot_core
from main.models import UserProfile
import telegram_bot

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()

SENT = []
telegram_bot.send = lambda chat_id, text, buttons=None: SENT.append(
    {'chat': chat_id, 'text': text, 'buttons': buttons})
telegram_bot._api = lambda method, **body: None  # сеть в тесте не трогаем


def last_text():
    return SENT[-1]['text'] if SENT else ''


def make_user(name):
    u = User.objects.create_user(username=name, email=f'{name}@example.com',
                                 password='Zk9mQ2vLp7xR')
    prof, _ = UserProfile.objects.get_or_create(user=u)
    prof.trial_until = timezone.now() + timedelta(days=5)
    prof.save()
    return u, prof


QUIZ = {
    'available': True,
    'question': 'Как пишется слово?',
    'options': [{'text': 'верно', 'is_correct': True},
                {'text': 'неверно', 'is_correct': False}],
    'example_id': 77,
    'user_word_id': None,
    'correct_text': 'верно',
}

# --- подмена тяжёлых/сетевых веток bot_core ---
bot_core.get_quiz = lambda profile, mode, index=0: dict(QUIZ)
bot_core.log_answer = lambda profile, example_id, user_word_id, was_correct: {
    'explanation': 'потому что', 'correct_text': 'верно'}
bot_core.get_stats = lambda profile: {
    'total_words': 5, 'total_attempts': 4, 'correct_answers': 3,
    'success_rate': 75, 'weak_orthograms': []}
bot_core.free_chat = lambda platform, platform_id, text, simplify=False: {
    'allowed': True, 'linked': True, 'reply': f'ЭХО:{platform}:{text}',
    'buttons': None, 'simplifiable': False}
bot_core.get_daily_word_state = lambda profile: {
    'state': 'revealed', 'period_date': '2026-11-03',
    'question': 'Слово дня: как пишется?',
    'options': [{'text': 'а'}, {'text': 'б'}]}
bot_core.answer_daily_word = lambda profile, period_date, idx: {
    'was_correct': True, 'explanation': 'так надо'}

print('1. Привязка кодом из личного кабинета')
u, prof = make_user('pupil')
prof.link_code = 'TGCODE01'
prof.link_code_expires = timezone.now() + timedelta(minutes=10)
prof.save()
telegram_bot.handle_link_code(1001, 5001, 'tgcode01')
prof.refresh_from_db()
check(prof.telegram_id == 5001, f'profile.telegram_id проставлен (факт: {prof.telegram_id})')
check(any('✅ Привязан!' in s['text'] for s in SENT),
      'приветствие после привязки')
check(bot_core.get_profile_by_platform('telegram', 5001) is not None,
      'get_profile_by_platform("telegram") находит профиль')
check(any(p.id == prof.id for p in bot_core.iter_bot_eligible_profiles()),
      'профиль с telegram_id попадает в рассылочный итератор')

print('2. Меню и отказ непривязанному')
SENT.clear()
telegram_bot.handle_text(2002, 6002, '/start')
check('привяжи аккаунт' in last_text(), 'непривязанному /start -> подсказка привязки')
SENT.clear()
telegram_bot.handle_text(1001, 5001, '/start')
check('Главное меню' in last_text() and SENT[-1]['buttons'],
      'привязанному /start -> меню с кнопками')

print('3. Квиз и ответ кнопкой')
SENT.clear()
telegram_bot.handle_text(1001, 5001, 'мои слова')
check(last_text().startswith('❓'), 'квиз отправлен')
check(len(SENT[-1]['buttons']) == 2, 'две кнопки-варианта')
SENT.clear()
telegram_bot.handle_callback(1001, 5001, json.dumps({'a': 'answer', 'i': 0}))
check(any('✅ Верно!' in s['text'] and 'потому что' in s['text'] for s in SENT),
      'верный ответ: вердикт + объяснение')
check('Что дальше?' in SENT[-1]['text'], 'после вердикта — кнопки следующего шага')

print('4. Статистика и свободный чат')
SENT.clear()
telegram_bot.handle_text(1001, 5001, 'статистика')
check(last_text() == bot_core.format_stats_message(
    {'total_words': 5, 'total_attempts': 4, 'correct_answers': 3,
     'success_rate': 75, 'weak_orthograms': []}),
      'статистика форматом bot_core')
SENT.clear()
telegram_bot.handle_text(1001, 5001, 'расскажи про ЕГЭ')
check(last_text() == 'ЭХО:telegram:расскажи про ЕГЭ',
      'свободный чат уходит в оркестратор с platform=telegram')

print('5. Слово дня кнопкой')
SENT.clear()
telegram_bot.handle_callback(
    1001, 5001, json.dumps({'a': 'daily_answer', 'i': 1, 'p': '2026-11-03'}))
check(any('✅ Верно!' in s['text'] for s in SENT),
      'ответ на слово дня обработан')

print('6. callback_data: длинный payload через хранилище')
big = {'a': 'x', 'note': 'ы' * 100}
cd = telegram_bot._cb(big)
check(len(cd.encode('utf-8')) <= 64, 'длинный payload ужат до ключа <=64 байт')
check(telegram_bot._cb_resolve(cd) == big, 'ключ разворачивается обратно')
small = {'a': 'stats'}
check(telegram_bot._cb_resolve(telegram_bot._cb(small)) == small,
      'короткий payload идёт как есть')

print('7. Разбор обновлений Telegram')
SENT.clear()
telegram_bot.handle_update({'message': {
    'chat': {'id': 1001, 'type': 'private'},
    'from': {'id': 5001}, 'text': 'помощь'}})
check('Команды:' in last_text(), 'message -> текстовый диспетчер')
SENT.clear()
telegram_bot.handle_update({'message': {
    'chat': {'id': 1001, 'type': 'group'},
    'from': {'id': 5001}, 'text': 'помощь'}})
check(not SENT, 'групповые чаты игнорируются')
SENT.clear()
telegram_bot.handle_update({'callback_query': {
    'id': 'cq1', 'data': json.dumps({'a': 'menu'}),
    'from': {'id': 5001},
    'message': {'chat': {'id': 1001}}}})
check('Главное меню' in last_text(), 'callback_query -> диспетчер кнопок')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ TELEGRAM-АДАПТЕРА ПРОЙДЕНЫ')
