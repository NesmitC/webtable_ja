# -*- coding: utf-8 -*-
"""Рубеж cp14 «Задания 9, 10, 11, 12, 13» (после урока 13, открывает урок 14):
гейт по cp13; состав — по два варианта заданий 9-13, по 5 строк по 3 слова;
орфограммы задания 13 покрыты парой блоков, эталоны 13 — только | и /;
персонализация; зачёт по 10 блокам, допуск 2 ошибки; карточка 14 с видео.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint14.py
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
        user=user, checkpoint_code=code, passed=True, total_tasks=10,
        correct_count=10, error_count=0, results_data={}, words_data=[])


ORTHS9 = {'1': 'а,о,е,и', '2': 'а,о,е,и', '14': 'ё,о', '15': 'и,ы'}
ORTHS10 = {'10': 'а,о,е,и', '11': 'з,с', '28': 'ы,и', '29': 'е,и', '6': 'ъ,ь'}
ORTHS11 = {'481': 'е,и', '482': 'е,и', '483': 'и,е', '484': 'а', '485': 'е,и'}
ORTHS12 = {'25': 'е,и', '49': 'у,ю', '50': 'е,и', '51': 'а,я',
           '511': 'а,е', '512': 'и,е', '513': 'е,и'}
ORTHS13 = {'21': '|,/', '32': '|,/', '36': '|,/', '46': '|,/', '54': '|,/',
           '56': '|,/', '57': '|,/', '58': '|,/', '581': '|,/', '582': '|,/'}
for oid, letters in {**ORTHS9, **ORTHS10, **ORTHS11, **ORTHS12,
                     **ORTHS13}.items():
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
for oid in ORTHS13:
    for i in range(10):
        sep = '\\' if i % 2 else '/'
        text = f'не{sep}слов{oid}о{i}'
        OrthogramExample.objects.create(
            text=text, masked_word=text.replace(sep, f'*{oid}*', 1),
            orthogram_id=oid, grades='10,11', is_active=True)
# битая строка владельца: эталон-буква вместо маркера — не должна попасть в рубеж
OrthogramExample.objects.create(text='неОслово21', masked_word='не*21*Ослово21',
                                orthogram_id='21', grades='10,11',
                                is_active=True)

ERR13 = 'не*54*слов54о0'
pupil = make_user('pupil')
Task9WordStat.objects.create(user=pupil, orthogram_id='54', range_code='13',
                             word=ERR13, correct_letter='|', attempts=3,
                             errors=2, in_correction=True)
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10', 'cp12', 'cp13'):
    pass_code(pupil, code)

print('1. Гейт: cp14 только после cp13')
u2 = make_user('nogate')
c0 = Client()
c0.force_login(u2)
r = c0.get('/ege/checkpoint/14/', HTTP_HOST='localhost')
check(r.status_code == 302, f'без cp13 -> редирект (факт: {r.status_code})')

c = Client()
c.force_login(pupil)
r = c.get('/ege/checkpoint/14/', HTTP_HOST='localhost')
html = r.content.decode('utf-8')
check(r.status_code == 200, f'после cp13 -> 200 (факт: {r.status_code})')
check('Рубежный тест: задания 9, 10, 11, 12, 13' in html, 'шапка рубежа')
check('урок 14' in html, 'обещание открыть урок 14')
for title in ('Задание 9 (1)', 'Задание 10 (2)', 'Задание 11 (1)',
              'Задание 12 (2)', 'Задание 13 (1)', 'Задание 13 (2)'):
    check(title in html, f'заголовок блока «{title}» на странице')

sess = c.session['checkpoint_14']
lines = sess['snapshot']['9']['lines']
orths = sess['task9_orths']
units = sess['task9_units']
line_units = units[::3]
print('2. Состав: 50 строк = по 2 блока заданий 9-13, 150 масок')
check(len(sess['task9_correct']) == 150,
      f'150 букв (50 строк по 3): факт {len(sess["task9_correct"])}')
check(list(dict.fromkeys(line_units)) == ['9b1', '9b2', '10b1', '10b2',
                                          '11b1', '11b2', '12b1', '12b2',
                                          '13b1', '13b2'],
      'десять блоков по порядку')
seg13 = {o for o, u in zip(orths, units) if u.startswith('13b')}
check(seg13 == set(ORTHS13),
      f'блоки 13 вместе покрывают все орфограммы (факт {sorted(seg13, key=int)})')
lets13 = {l for l, u in zip(sess['task9_correct'], units)
          if u.startswith('13b')}
check(lets13 <= {'|', '/'}, f'эталоны 13 — только маркеры (факт {lets13})')
check(not any('Ослово21' in ln for ln in lines),
      'битая строка с буквой-эталоном не попала в рубеж')
check(not any('*21*' in ln or '*54*' in ln for ln in lines),
      'сырые маски орфограмм не утекли в строки')

print('3. Персонализация блоков 13')
blob = ' '.join(ln for ln, u in zip(lines, line_units) if u.startswith('13b'))
check('слов54' in blob, 'слово с ошибкой ученика (54) в блоках 13')

print('4. Сдан целиком -> урок 14 открыт, видео и карточка рубежа на месте')


def good_answers(s):
    return {f'9-{i}': l for i, l in enumerate(s['task9_correct'], 1)}


r = c.post('/ege/checkpoint/14/', data=json.dumps({'answers': good_answers(sess)}),
           content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 0,
      f'сдан, ошибок 0 (факт: {res["passed"]}, {res["error_count"]})')
lb = c.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')
i14 = lb.find('Задание 14 (орфография, слитно / раздельно / дефис)')
j14 = lb.rfind('<div class="lesson-card lesson-card--', 0, i14)
check('lesson-card--active' in lb[j14:i14], 'карточка 14 активна после cp14')
k14 = lb.find('Задание 15', i14)
check('3j3Zr4645Mf4RMkJajfXbx' in lb[i14:k14], 'видео урока 14 в карточке 14')
check('Рубежный тест: задания 9, 10, 11, 12, 13' in lb
      and '/ege/checkpoint/14/' in lb, 'карточка рубежа cp14 на странице уроков')

print('5. Зачёт по блокам и допуск')
p3 = make_user('pupil3')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10', 'cp12', 'cp13'):
    pass_code(p3, code)
c3 = Client()
c3.force_login(p3)
c3.get('/ege/checkpoint/14/', HTTP_HOST='localhost')
s3 = c3.session['checkpoint_14']
a3 = good_answers(s3)
for i, un in enumerate(s3['task9_units'], 1):
    if un in ('9b1', '13b2'):
        a3[f'9-{i}'] = 'я' if s3['task9_correct'][i - 1] != 'я' else 'у'
r = c3.post('/ege/checkpoint/14/', data=json.dumps({'answers': a3}),
            content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 2,
      f'2 ошибки в допуске -> сдан (факт: {res["error_count"]})')
check(res['results']['9b1']['is_correct'] is False
      and res['results']['13b1']['is_correct'] is True,
      'блоки посчитаны раздельно')
page = c3.get(res['result_url'], HTTP_HOST='localhost').content.decode('utf-8')
check('Задание 13: НЕ и НИ слитно / раздельно' in page,
      'рекомендация по блокам 13 ведёт на тренажёры')

p4 = make_user('pupil4')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10', 'cp12', 'cp13'):
    pass_code(p4, code)
c4 = Client()
c4.force_login(p4)
c4.get('/ege/checkpoint/14/', HTTP_HOST='localhost')
s4 = c4.session['checkpoint_14']
a4 = good_answers(s4)
for i, un in enumerate(s4['task9_units'], 1):
    if un in ('9b1', '10b1', '13b1'):
        a4[f'9-{i}'] = 'я' if s4['task9_correct'][i - 1] != 'я' else 'у'
r = c4.post('/ege/checkpoint/14/', data=json.dumps({'answers': a4}),
            content_type='application/json')
res = r.json()
check(res['passed'] is False and res['error_count'] == 3,
      f'3 ошибки -> провал (факт: {res["error_count"]})')
lb = c4.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')
i14 = lb.find('Задание 14 (орфография, слитно / раздельно / дефис)')
j14 = lb.rfind('<div class="lesson-card lesson-card--', 0, i14)
check('lesson-card--locked' in lb[j14:i14], '14 закрыт после провала')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖА 9, 10, 11, 12, 13 ПРОЙДЕНЫ')
