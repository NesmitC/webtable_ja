# -*- coding: utf-8 -*-
"""Рубеж cp13 «Задания 9, 10, 11, 12» (после урока 12, открывает урок 13):
гейт по cp12; состав — по два варианта заданий 9, 10, 11 и 12, по 5 строк
по 3 слова; орфограммы задания 12 покрыты парой блоков; персонализация;
зачёт по 8 блокам, допуск 2 ошибки; карточка 13 с видео после сдачи.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint13.py
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
from django.test import Client
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main.models import (CheckpointAttempt, Orthogram, OrthogramExample,
                         Task9WordStat, UserProfile)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()


def make_user(name):
    u = User.objects.create_user(username=name, email=f'{name}@example.com',
                                 password='Zk9mQ2vLp7xR')
    prof, _ = UserProfile.objects.get_or_create(user=u)
    prof.trial_until = timezone.now() + timedelta(days=5)
    prof.save()
    return u


def pass_code(user, code):
    CheckpointAttempt.objects.create(
        user=user, checkpoint_code=code, passed=True, total_tasks=8,
        correct_count=8, error_count=0, results_data={}, words_data=[])


ORTHS9 = {'1': 'а,о,е,и', '2': 'а,о,е,и', '14': 'ё,о', '15': 'и,ы'}
ORTHS10 = {'10': 'а,о,е,и', '11': 'з,с', '28': 'ы,и', '29': 'е,и', '6': 'ъ,ь'}
ORTHS11 = {'481': 'е,и', '482': 'е,и', '483': 'и,е', '484': 'а', '485': 'е,и'}
ORTHS12 = {'25': 'е,и', '49': 'у,ю', '50': 'е,и', '51': 'а,я',
           '511': 'а,е', '512': 'и,е', '513': 'е,и'}
LET = {'1': 'а', '2': 'о', '14': 'о', '15': 'ы', '10': 'е', '11': 'с',
       '28': 'и', '29': 'и', '6': 'ъ', '481': 'и', '482': 'е', '483': 'и',
       '484': 'а', '485': 'и', '25': 'и', '49': 'ю', '50': 'и', '51': 'а',
       '511': 'е', '512': 'и', '513': 'и'}
for oid, letters in {**ORTHS9, **ORTHS10, **ORTHS11, **ORTHS12}.items():
    Orthogram.objects.create(id=oid, name=f'орф {oid}', letters=letters)
for oid in ORTHS9:
    for i in range(12):
        text = f'кор{oid}ь{i}а'
        OrthogramExample.objects.create(
            text=text, masked_word=text.replace('ь', f'*{oid}*'),
            orthogram_id=oid, grades='10,11', is_active=True)
for oid in ORTHS10:
    for i in range(10):
        text = f'при{oid}в{i}а'
        OrthogramExample.objects.create(
            text=text, masked_word=text.replace('в', f'*{oid}*'),
            orthogram_id=oid, grades='10,11', is_active=True)
for oid in ORTHS11:
    for i in range(10):
        text = f'суф{oid}к{i}ой'
        OrthogramExample.objects.create(
            text=text, masked_word=text.replace('к', f'*{oid}*'),
            orthogram_id=oid, grades='10,11', is_active=True)
for oid in ORTHS12:
    for i in range(10):
        text = f'глаг{oid}л{i}ая'
        OrthogramExample.objects.create(
            text=text, masked_word=text.replace('л', f'*{oid}*'),
            orthogram_id=oid, grades='10,11', is_active=True)

ERR12 = 'кле*49*щий'
OrthogramExample.objects.create(text='клеющий', masked_word=ERR12,
                                orthogram_id='49', grades='10,11',
                                is_active=True)
pupil = make_user('pupil')
Task9WordStat.objects.create(user=pupil, orthogram_id='49', range_code='12',
                             word=ERR12, correct_letter='ю', attempts=3,
                             errors=2, in_correction=True)
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10', 'cp12'):
    pass_code(pupil, code)

print('1. Гейт: cp13 только после cp12')
u2 = make_user('nogate')
c0 = Client()
c0.force_login(u2)
r = c0.get('/ege/checkpoint/13/', HTTP_HOST='localhost')
check(r.status_code == 302, f'без cp12 -> редирект (факт: {r.status_code})')

c = Client()
c.force_login(pupil)
r = c.get('/ege/checkpoint/13/', HTTP_HOST='localhost')
html = r.content.decode('utf-8')
check(r.status_code == 200, f'после cp12 -> 200 (факт: {r.status_code})')
check('Рубежный тест: задания 9, 10, 11, 12' in html, 'шапка рубежа')
check('урок 13' in html, 'обещание открыть урок 13')
for title in ('Задание 9 (1)', 'Задание 10 (2)', 'Задание 11 (1)',
              'Задание 12 (2)'):
    check(title in html, f'заголовок блока «{title}» на странице')

sess = c.session['checkpoint_13']
lines = sess['snapshot']['9']['lines']
orths = sess['task9_orths']
units = sess['task9_units']
line_units = units[::3]
print('2. Состав: 40 строк = 2×9 + 2×10 + 2×11 + 2×12')
check(len(sess['task9_correct']) == 120,
      f'120 букв (40 строк по 3): факт {len(sess["task9_correct"])}')
check(list(dict.fromkeys(line_units)) == ['9b1', '9b2', '10b1', '10b2',
                                          '11b1', '11b2', '12b1', '12b2'],
      'восемь блоков по порядку')
seg12 = {o for o, u in zip(orths, units) if u.startswith('12b')}
check(seg12 == set(ORTHS12),
      f'блоки 12 вместе покрывают все орфограммы (факт {sorted(seg12, key=int)})')

print('3. Персонализация блоков 12')
blob = ' '.join(ln for ln, u in zip(lines, line_units) if u.startswith('12b'))
check('кле' in blob and 'щий' in blob, 'слово с ошибкой ученика (49) в блоках 12')

print('4. Сдан целиком -> урок 13 открыт, видео на месте')


def good_answers(s):
    return {f'9-{i}': l for i, l in enumerate(s['task9_correct'], 1)}


r = c.post('/ege/checkpoint/13/', data=json.dumps({'answers': good_answers(sess)}),
           content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 0,
      f'сдан, ошибок 0 (факт: {res["passed"]}, {res["error_count"]})')
lb = c.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')
i13 = lb.find('Задание 13 (орфография, НЕ и НИ слитно / раздельно)')
j13 = lb.rfind('<div class="lesson-card lesson-card--', 0, i13)
check('lesson-card--active' in lb[j13:i13], 'карточка 13 активна после cp13')
k13 = lb.find('Задание 14', i13)
check('0QT3xD41pySq19RXA9qSXj' in lb[i13:k13], 'видео урока 13 в карточке 13')

print('5. Зачёт по блокам и допуск')
p3 = make_user('pupil3')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10', 'cp12'):
    pass_code(p3, code)
c3 = Client()
c3.force_login(p3)
c3.get('/ege/checkpoint/13/', HTTP_HOST='localhost')
s3 = c3.session['checkpoint_13']
a3 = good_answers(s3)
for i, un in enumerate(s3['task9_units'], 1):
    if un in ('9b1', '12b2'):
        a3[f'9-{i}'] = 'я' if s3['task9_correct'][i - 1] != 'я' else 'у'
r = c3.post('/ege/checkpoint/13/', data=json.dumps({'answers': a3}),
            content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 2,
      f'2 ошибки в допуске -> сдан (факт: {res["error_count"]})')
check(res['results']['9b1']['is_correct'] is False
      and res['results']['12b1']['is_correct'] is True,
      'блоки посчитаны раздельно')
page = c3.get(res['result_url'], HTTP_HOST='localhost').content.decode('utf-8')
check('Задание 12: спряжения и суффиксы' in page,
      'рекомендация по блокам 12 ведёт на тренажёры')

p4 = make_user('pupil4')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10', 'cp12'):
    pass_code(p4, code)
c4 = Client()
c4.force_login(p4)
c4.get('/ege/checkpoint/13/', HTTP_HOST='localhost')
s4 = c4.session['checkpoint_13']
a4 = good_answers(s4)
for i, un in enumerate(s4['task9_units'], 1):
    if un in ('9b1', '10b1', '11b1'):
        a4[f'9-{i}'] = 'я' if s4['task9_correct'][i - 1] != 'я' else 'у'
r = c4.post('/ege/checkpoint/13/', data=json.dumps({'answers': a4}),
            content_type='application/json')
res = r.json()
check(res['passed'] is False and res['error_count'] == 3,
      f'3 ошибки -> провал (факт: {res["error_count"]})')
lb = c4.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')
i13 = lb.find('Задание 13 (орфография, НЕ и НИ слитно / раздельно)')
j13 = lb.rfind('<div class="lesson-card lesson-card--', 0, i13)
check('lesson-card--locked' in lb[j13:i13], '13 закрыт после провала')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖА 9, 10, 11, 12 ПРОЙДЕНЫ')
