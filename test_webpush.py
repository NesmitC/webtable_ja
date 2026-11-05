# -*- coding: utf-8 -*-
"""Тесты Web Push (PWA): /sw.js, /api/push/*, сохранение подписок, рассылка
«Слова дня» (dry-run, пропуски по тарифу и по отвеченным, деактивация мёртвых
подписок), генерация VAPID-ключей, карточка в ЛК.

Запуск: .\\.venv\\Scripts\\python.exe test_webpush.py
"""
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfo

# консоль Windows (cp1251) не кодирует ✅/❌ — переключаем stdout в UTF-8
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from main import bot_core, push as push_mod
from main.models import (DailyWord, Orthogram, OrthogramExample,
                         PushSubscription, UserProfile, UserWord)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
MSK = ZoneInfo('Europe/Moscow')
FIXED_NOW = datetime(2026, 11, 5, 16, 0, tzinfo=MSK)   # время отправки по ТЗ

IPHONE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
             'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 '
             'Mobile/15E148 Safari/604.1')

SUB_BODY = {'endpoint': 'https://fcm.googleapis.com/fcm/send/test-endpoint-1',
            'keys': {'p256dh': 'B' * 87, 'auth': 'C' * 22}}


def make_user(name, paid=True):
    u = User.objects.create_user(username=name, email=f'{name}@example.com',
                                 password='Zk9mQ2vLp7xR')
    p = UserProfile.objects.get(user=u)
    if paid:
        p.plan = 'self'
        p.plan_until = timezone.now() + timedelta(days=30)
    p.save()
    return u


print('1. /sw.js: отдаётся с корня с правильными заголовками')
c = Client()
r = c.get('/sw.js')
check(r.status_code == 200, f'200 (факт {r.status_code})')
check(r['Content-Type'] == 'application/javascript',
      'Content-Type application/javascript')
check(r['Service-Worker-Allowed'] == '/', 'Service-Worker-Allowed: /')
check(b'showNotification' in r.content, 'в теле есть push-обработчик')

print('2. /api/push/config/: без ключей выключен, с ключами отдаёт публичный')
r = c.get('/api/push/config/')
data = r.json()
check(data['enabled'] is False and data['vapid_public_key'] == '',
      'enabled=False, ключа нет')
settings.VAPID_PUBLIC_KEY = 'B' * 88
settings.VAPID_PRIVATE_KEY = 'M' * 44
r = c.get('/api/push/config/')
data = r.json()
check(data['enabled'] is True and data['vapid_public_key'] == 'B' * 88,
      'с ключами: enabled=True + публичный ключ')

print('3. subscribe / unsubscribe')
r = c.post('/api/push/subscribe/', data=json.dumps(SUB_BODY),
           content_type='application/json')
check(r.status_code == 302, f'аноним: редирект на логин (факт {r.status_code})')

u1 = make_user('push_pupil')
c1 = Client()
c1.force_login(u1)
r = c1.post('/api/push/subscribe/', data=json.dumps(SUB_BODY),
            content_type='application/json', HTTP_USER_AGENT=IPHONE_UA)
check(r.status_code == 200 and r.json()['status'] == 'ok', 'subscribe: 200 ok')
sub = PushSubscription.objects.first()
check(sub is not None and sub.user == u1 and sub.platform == 'ios' and sub.active,
      'подписка сохранена: пользователь, platform=ios, active')

bad = {'endpoint': 'http://insecure/', 'keys': {}}
r = c1.post('/api/push/subscribe/', data=json.dumps(bad),
            content_type='application/json')
check(r.status_code == 400, f'битая подписка: 400 (факт {r.status_code})')

u2 = make_user('push_pupil2')
c2 = Client()
c2.force_login(u2)
c2.post('/api/push/subscribe/', data=json.dumps(SUB_BODY),
        content_type='application/json')
sub.refresh_from_db()
check(sub.user == u2, 'переподписка с другого аккаунта: устройство перенесено')

r = c2.post('/api/push/unsubscribe/', data=json.dumps(SUB_BODY),
            content_type='application/json')
sub.refresh_from_db()
check(r.status_code == 200 and not sub.active, 'unsubscribe: active=False')

print('4. Рассылка: dry-run, пропуски, мёртвая подписка')
Orthogram.objects.create(id=1, name='тестовая', letters='о,а')
word = OrthogramExample.objects.create(
    text='вода', masked_word='в*1*да', orthogram_id=1, grades='10,11',
    is_active=True, explanation='ударение на первый слог',
    incorrect_variant='вада')

u3 = make_user('push_paid3')
UserWord.objects.create(user=u3, field_name='user-input-orf-1',
                        text=word.text, reference_word=word)
PushSubscription.objects.create(user=u3, endpoint='https://fcm.googleapis.com/e3',
                                p256dh='B' * 87, auth='C' * 22, platform='android')

with mock.patch('main.bot_core.now_msk', return_value=FIXED_NOW):
    stats = push_mod.send_daily_words(user=u3, dry_run=True)
check(stats['sent'] == 1 and stats['skipped'] == 0,
      f'dry-run по платному с планингом: sent=1 (факт {stats})')
dw = DailyWord.objects.filter(user=u3).first()
check(dw is not None and dw.period_date == FIXED_NOW.date(),
      'DailyWord периода создан')
check(dw.question.startswith('Как пишется правильно:'),
      f'текст задания: {dw.question[:34]!r}')

payload = push_mod.daily_payload({'question': dw.question,
                                  'period_date': dw.period_date})
check(payload['title'] == 'Нейростат: слово дня', 'заголовок с брендом')
check(dw.question in payload['body'], 'тело = текст задания сразу, без скрытия')
check(payload['url'].endswith('/ege/quizzes/#daily-word'),
      'тап открывает карточку слова дня')

uf = make_user('push_free', paid=False)
PushSubscription.objects.create(user=uf, endpoint='https://fcm.googleapis.com/ef',
                                p256dh='B' * 87, auth='C' * 22)
with mock.patch('main.bot_core.now_msk', return_value=FIXED_NOW):
    stats = push_mod.send_daily_words(user=uf, dry_run=True)
check(stats['skipped'] == 1 and stats['sent'] == 0,
      'бесплатный тариф: пропуск (слово дня — платная фича)')

p3 = UserProfile.objects.get(user=u3)
with mock.patch('main.bot_core.now_msk', return_value=FIXED_NOW):
    state = bot_core.get_daily_word_state(p3)
    bot_core.answer_daily_word(p3, state['period_date'], 0)
    stats = push_mod.send_daily_words(user=u3, dry_run=True)
check(stats['skipped'] == 1 and stats['sent'] == 0,
      'уже ответил сегодня: пропуск')

u4 = make_user('push_paid4')
UserWord.objects.create(user=u4, field_name='user-input-orf-1',
                        text=word.text, reference_word=word)
sub4 = PushSubscription.objects.create(
    user=u4, endpoint='https://fcm.googleapis.com/e4',
    p256dh='B' * 87, auth='C' * 22)
with mock.patch('main.bot_core.now_msk', return_value=FIXED_NOW), \
        mock.patch.object(push_mod, 'send_push', return_value=(False, 'dead')):
    stats = push_mod.send_daily_words(user=u4)
sub4.refresh_from_db()
check(stats['deactivated'] == 1 and not sub4.active,
      'мёртвая подписка (404/410): деактивирована')

u5 = make_user('push_paid5')
UserWord.objects.create(user=u5, field_name='user-input-orf-1',
                        text=word.text, reference_word=word)
s5 = PushSubscription.objects.create(
    user=u5, endpoint='https://fcm.googleapis.com/e5',
    p256dh='B' * 87, auth='C' * 22)
with mock.patch('main.bot_core.now_msk', return_value=FIXED_NOW), \
        mock.patch.object(push_mod, 'send_push', return_value=(True, '')) as m:
    stats = push_mod.send_daily_words(user=u5)
s5.refresh_from_db()
check(stats['sent'] == 1 and m.called and s5.last_sent_at is not None,
      'отправка: send_push вызван, last_sent_at проставлен')
sent_payload = m.call_args[0][1]
check(sent_payload['title'] == 'Нейростат: слово дня'
      and 'Как пишется правильно' in sent_payload['body'],
      'payload дошёл до отправки с заданием')

print('5. manage.py send_daily_push --dry-run')
buf = io.StringIO()
with mock.patch('main.bot_core.now_msk', return_value=FIXED_NOW):
    call_command('send_daily_push', user='push_paid5', dry_run=True, stdout=buf)
out = buf.getvalue()
check('отправлено=1' in out, f'команда печатает статистику ({out.strip()[:90]})')

print('6. generate_vapid_keys: дописывает в .env, идемпотентна, секрет не печатает')
tmp = tempfile.NamedTemporaryFile('w', suffix='.env', delete=False,
                                  encoding='utf-8')
tmp.write('DEBUG=True\n')
tmp.close()
buf = io.StringIO()
call_command('generate_vapid_keys', env_file=tmp.name, stdout=buf)
with open(tmp.name, encoding='utf-8') as f:
    content = f.read()
check('VAPID_PUBLIC_KEY=' in content and 'VAPID_PRIVATE_KEY=' in content,
      'ключи дописаны в .env')
priv = [ln.split('=', 1)[1] for ln in content.splitlines()
        if ln.startswith('VAPID_PRIVATE_KEY=')][0]
check(priv not in buf.getvalue(), 'приватный ключ НЕ в выводе команды')
buf2 = io.StringIO()
call_command('generate_vapid_keys', env_file=tmp.name, stdout=buf2)
check('уже есть' in buf2.getvalue(), 'повторный запуск: ничего не делает')
os.unlink(tmp.name)

print('7. /profile/: карточка пуша только на платном тарифе')
r = c1.get('/profile/')
body = r.content.decode('utf-8')
check(r.status_code == 200 and 'push-enable' in body,
      'платный: карточка с кнопкой включения')
cf = Client()
cf.force_login(uf)
body = cf.get('/profile/').content.decode('utf-8')
check('push-enable' not in body, 'бесплатный: карточки нет')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ WEB PUSH ПРОЙДЕНЫ')
