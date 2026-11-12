# -*- coding: utf-8 -*-
"""Отчёты владельцу о попытках рубежей: письмо на каждую попытку (сдан/не сдан,
пересдача), ссылка на разбор, МСК-время; сбой SMTP не роняет сдачу.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint_notify.py
"""
import json
import os
import sys
import time
from datetime import timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main import views
from main.models import (CheckpointAttempt, Orthogram, OrthogramExample,
                         UserProfile)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


SENT = []
views._send_owner_notify_bg = lambda subject, body: SENT.append((subject, body))

User = get_user_model()
u = User.objects.create_user(username='sasha', email='sasha@example.com',
                             password='Zk9mQ2vLp7xR')
prof, _ = UserProfile.objects.get_or_create(user=u)
prof.trial_until = timezone.now() + timedelta(days=5)
prof.save()

ORTHS = {'1': 'а,о', '10': 'е,и', '481': 'е,и'}
for oid, letters in ORTHS.items():
    Orthogram.objects.create(id=oid, name=f'орф {oid}', letters=letters)
for oid in ORTHS:
    for i in range(12):
        text = f'сл{oid}в{i}о'
        OrthogramExample.objects.create(
            text=text, masked_word=text.replace('в', f'*{oid}*'),
            orthogram_id=oid, grades='10,11', is_active=True)
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10'):
    CheckpointAttempt.objects.create(
        user=u, checkpoint_code=code, passed=True, total_tasks=9,
        correct_count=9, error_count=0, results_data={}, words_data=[])

c = Client()
c.force_login(u)


def good_answers(s):
    return {f'9-{i}': l for i, l in enumerate(s['task9_correct'], 1)}


print('1. Сданная попытка -> отчёт владельцу')
c.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
sess = c.session['checkpoint_12']
r = c.post('/ege/checkpoint/12/', data=json.dumps({'answers': good_answers(sess)}),
           content_type='application/json')
time.sleep(0.3)
check(r.json()['passed'] is True, 'рубеж сдан')
check(len(SENT) == 1, f'одно письмо (факт: {len(SENT)})')
subj, body = SENT[0]
check('sasha' in subj and 'сдан' in subj, f'тема: ученик и статус ({subj})')
check('sasha@example.com' in body, 'в письме email ученика')
check('Рубежный тест: задания 9, 10, 11' in body, 'в письме название рубежа')
check('Открыт урок: 12.1' in body, 'в письме открытый урок')
check('/staff/checkpoint/' in body, 'в письме ссылка на разбор попытки')
check('(МСК)' in body, 'в письме время в МСК')
check('Провалены блоки: нет' in body, 'проваленных блоков нет')

print('2. Пересдача -> отчёт снова, с пометкой')
c.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
sess = c.session['checkpoint_12']
c.post('/ege/checkpoint/12/', data=json.dumps({'answers': good_answers(sess)}),
       content_type='application/json')
time.sleep(0.3)
check(len(SENT) == 2, f'второе письмо на пересдачу (факт: {len(SENT)})')
check('Пересдача: урок уже был открыт' in SENT[1][1], 'пометка пересдачи')
check('Попытка #2' in SENT[1][1], 'номер попытки в письме')

print('3. Провал -> отчёт тоже приходит')
c.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
sess = c.session['checkpoint_12']
ans = good_answers(sess)
units = sess['task9_units'][::3]
for i, un in enumerate(units, 1):
    if un == '9b1':
        for k in range((i - 1) * 15 + 1, (i - 1) * 15 + 16):
            ans[f'9-{k}'] = 'я' if sess['task9_correct'][k - 1] != 'я' else 'у'
r = c.post('/ege/checkpoint/12/', data=json.dumps({'answers': ans}),
           content_type='application/json')
time.sleep(0.3)
check(r.json()['passed'] is False, 'попытка провалена')
check(len(SENT) == 3, f'письмо о провале пришло (факт: {len(SENT)})')
subj, body = SENT[2]
check('НЕ сдан' in subj, 'тема провала')
check('Урок остаётся закрытым' in body, 'в письме: урок закрыт')
check('Задание 9 (1)' in body, 'в письме назван проваленный блок')

print('4. Сбой SMTP не роняет сдачу')
real = views._send_owner_notify_bg


def boom(subject, body):
    raise RuntimeError('SMTP умер')


views._send_owner_notify_bg = boom
u2 = User.objects.create_user(username='p2', email='p2@example.com',
                              password='Zk9mQ2vLp7xR')
prof2, _ = UserProfile.objects.get_or_create(user=u2)
prof2.trial_until = timezone.now() + timedelta(days=5)
prof2.save()
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10'):
    CheckpointAttempt.objects.create(
        user=u2, checkpoint_code=code, passed=True, total_tasks=9,
        correct_count=9, error_count=0, results_data={}, words_data=[])
c2 = Client()
c2.force_login(u2)
c2.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
s2 = c2.session['checkpoint_12']
r = c2.post('/ege/checkpoint/12/',
            data=json.dumps({'answers': good_answers(s2)}),
            content_type='application/json')
time.sleep(0.3)
check(r.status_code == 200 and r.json()['passed'] is True,
      'сдача прошла несмотря на сбой отправки')
check(CheckpointAttempt.objects.filter(user=u2,
                                       checkpoint_code='cp12').exists(),
      'попытка записана в летопись')
views._send_owner_notify_bg = real

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ОТЧЁТОВ ВЛАДЕЛЬЦУ ПРОЙДЕНЫ')
