# -*- coding: utf-8 -*-
"""Рубеж cp12 «Задания 9, 10, 11» (после урока 11, открывает урок 12):
гейт по cp10; состав — по три варианта заданий 9, 10 и 11, по 5 строк по 3 слова;
в каждом блоке 11 представлены все орфограммы суффиксов; персонализация
(ошибки ученика + его планинг, fallback — самые сложные); зачёт по 9 блокам,
допуск 2 ошибки; заголовки блоков на странице; карточка 12.1 с видео после сдачи.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint12.py
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
        user=user, checkpoint_code=code, passed=True, total_tasks=9,
        correct_count=9, error_count=0, results_data={}, words_data=[])


ORTHS9 = {'1': 'а,о,е,и', '2': 'а,о,е,и', '14': 'ё,о', '15': 'и,ы'}
ORTHS10 = {'10': 'а,о,е,и', '11': 'з,с', '28': 'ы,и', '29': 'е,и', '6': 'ъ,ь'}
ORTHS11 = {'481': 'е,и', '482': 'е,и', '483': 'и,е', '484': 'а', '485': 'е,и'}
LET = {'1': 'а', '2': 'о', '14': 'о', '15': 'ы', '10': 'е', '11': 'с',
       '28': 'и', '29': 'и', '6': 'ъ', '481': 'и', '482': 'е', '483': 'и',
       '484': 'а', '485': 'и'}
for oid, letters in {**ORTHS9, **ORTHS10, **ORTHS11}.items():
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

# персонализация: ошибка ученика в суффиксах + слово из его планинга
ERR11 = 'гран*484*тый'
OrthogramExample.objects.create(text='гранатый', masked_word=ERR11,
                                orthogram_id='484', grades='10,11',
                                is_active=True)
PLAN11 = 'клев*482*ющий'
OrthogramExample.objects.create(text='клевующий', masked_word=PLAN11,
                                orthogram_id='482', grades='10,11',
                                is_active=True)

pupil = make_user('pupil')
OrthogramExample.objects.create(text='клевать', masked_word=PLAN11,
                                orthogram_id='482', grades='10,11',
                                is_active=True, is_user_added=True,
                                added_by=pupil)
Task9WordStat.objects.create(user=pupil, orthogram_id='484', range_code='SUFFIKSY',
                             word=ERR11, correct_letter='а', attempts=3,
                             errors=2, in_correction=True)
# общая статистика: самое сложное слово проекта (fallback)
HARD = '*11*делал'
OrthogramExample.objects.create(text='сделал', masked_word=HARD,
                                orthogram_id='11', grades='10,11',
                                is_active=True)
for n in range(3):
    o = make_user(f'other{n}')
    Task9WordStat.objects.create(user=o, orthogram_id='11', range_code='10',
                                 word=HARD, correct_letter='с', attempts=4,
                                 errors=7)

print('1. Гейт: cp12 только после cp10')
c = Client()
c.force_login(pupil)
r = c.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
check(r.status_code == 302, f'без cp10 -> редирект (факт: {r.status_code})')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10'):
    pass_code(pupil, code)
r = c.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
html = r.content.decode('utf-8')
check(r.status_code == 200, f'после cp10 -> 200 (факт: {r.status_code})')
check('Рубежный тест: задания 9, 10, 11' in html, 'шапка рубежа 9, 10, 11')
check('урок 12' in html, 'обещание открыть урок 12')

print('2. Заголовки блоков на странице')
for title in ('Задание 9 (1)', 'Задание 10 (2)', 'Задание 11 (3)'):
    check(title in html, f'заголовок блока «{title}» на странице')

sess = c.session['checkpoint_12']
lines = sess['snapshot']['9']['lines']
orths = sess['task9_orths']
units = sess['task9_units']
print('3. Состав: 45 строк = 3×9 + 3×10 + 3×11')
check(len(sess['task9_correct']) == 135,
      f'135 букв (45 строк по 3): факт {len(sess["task9_correct"])}')
check(list(dict.fromkeys(units)) == ['9b1', '9b2', '9b3', '10b1', '10b2',
                                     '10b3', '11b1', '11b2', '11b3'],
      'девять блоков по порядку')
for b in range(1, 4):
    seg = {o for o, u in zip(orths, units) if u == f'11b{b}'}
    check(seg == set(ORTHS11),
          f'блок 11-{b}: все орфограммы суффиксов (факт {sorted(seg, key=int)})')

print('4. Персонализация блоков 11')
blob = ' '.join(ln for ln, u in zip(lines, units[::3]) if u.startswith('11b'))
check('гран' in blob and 'тый' in blob, 'слово с ошибкой ученика (484) в блоках 11')
check('клев' in blob, 'слово из планинга ученика (482) в блоках 11')
p2 = make_user('pupil2')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10'):
    pass_code(p2, code)
c2 = Client()
c2.force_login(p2)
c2.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
blob2 = ' '.join(ln for ln, u in
                 zip(c2.session['checkpoint_12']['snapshot']['9']['lines'],
                     c2.session['checkpoint_12']['task9_units'][::3])
                 if u.startswith('10b'))
check('делал' in blob2, 'нет своих ошибок -> самое сложное слово проекта')

print('5. Сдан целиком -> урок 12 открыт, видео на месте')


def good_answers(s):
    return {f'9-{i}': l for i, l in enumerate(s['task9_correct'], 1)}


r = c.post('/ege/checkpoint/12/', data=json.dumps({'answers': good_answers(sess)}),
           content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 0,
      f'сдан, ошибок 0 (факт: {res["passed"]}, {res["error_count"]})')
lb = c.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')
i12 = lb.find('Задание 12.1 (спряжения глаголов)')
j12 = lb.rfind('<div class="lesson-card lesson-card--', 0, i12)
check('lesson-card--active' in lb[j12:i12], 'карточка 12.1 активна после cp12')
k12 = lb.find('Задание 12.2', i12)
check('33eEeY5RTLjdipxja6THgY' in lb[i12:k12], 'видео урока 12 в карточке 12.1')

print('6. Зачёт по блокам и допуск')
p3 = make_user('pupil3')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10'):
    pass_code(p3, code)
c3 = Client()
c3.force_login(p3)
c3.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
s3 = c3.session['checkpoint_12']
a3 = good_answers(s3)
for i, u in enumerate(s3['task9_units'], 1):
    if u in ('9b1', '11b2'):
        a3[f'9-{i}'] = 'я' if a3[f'9-{i}'] != 'я' else 'у'
r = c3.post('/ege/checkpoint/12/', data=json.dumps({'answers': a3}),
            content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 2,
      f'2 ошибки в допуске -> сдан (факт: {res["error_count"]})')
check(res['results']['9b1']['is_correct'] is False
      and res['results']['11b3']['is_correct'] is True,
      'блоки посчитаны раздельно')
page = c3.get(res['result_url'], HTTP_HOST='localhost').content.decode('utf-8')
check('Задание 11: суффиксы' in page, 'рекомендация по блокам 11 ведёт на суффиксы')

p4 = make_user('pupil4')
for code in ('cp91', 'cp92', 'cp93', 'cp94', 'cp10'):
    pass_code(p4, code)
c4 = Client()
c4.force_login(p4)
c4.get('/ege/checkpoint/12/', HTTP_HOST='localhost')
s4 = c4.session['checkpoint_12']
a4 = good_answers(s4)
for i, u in enumerate(s4['task9_units'], 1):
    if u in ('9b1', '10b1', '11b1'):
        a4[f'9-{i}'] = 'я' if a4[f'9-{i}'] != 'я' else 'у'
r = c4.post('/ege/checkpoint/12/', data=json.dumps({'answers': a4}),
            content_type='application/json')
res = r.json()
check(res['passed'] is False and res['error_count'] == 3,
      f'3 ошибки -> провал (факт: {res["error_count"]})')
lb = c4.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')
i12 = lb.find('Задание 12.1 (спряжения глаголов)')
j12 = lb.rfind('<div class="lesson-card lesson-card--', 0, i12)
check('lesson-card--locked' in lb[j12:i12], '12.1 закрыт после провала')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖА 9, 10, 11 ПРОЙДЕНЫ')
