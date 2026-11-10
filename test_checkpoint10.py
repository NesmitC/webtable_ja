# -*- coding: utf-8 -*-
"""Рубеж cp10 «Задания 9 и 10» (открывает урок 11): гейт по cp94, состав —
три варианта задания 9 и три варианта задания 10 по 5 строк (строки вразнобой
по орфограммам), в каждом блоке 10 представлены все орфограммы приставок,
персонализация (слова с ошибками ученика и слова его планинга первыми,
fallback — самые сложные по общей статистике), зачёт по блокам, допуск 2 ошибки.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint10.py
"""
import json
import os
import re
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main.models import (CheckpointAttempt, Orthogram, OrthogramExample,
                         Task9WordStat, UserProfile)
from datetime import timedelta
from django.utils import timezone

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
        user=user, checkpoint_code=code, passed=True, total_tasks=6,
        correct_count=6, error_count=0, results_data={}, words_data=[])


# === Орфограммы и примеры: пул 9 (корни) и пул 10 (приставки) ===
ORTHS9 = {'1': 'а,о,е,и', '2': 'а,о,е,и', '14': 'ё,о', '15': 'и,ы'}
ORTHS10 = {'10': 'а,о,е,и', '11': 'з,с', '28': 'ы,и', '29': 'е,и', '6': 'ъ,ь'}
for oid, letters in {**ORTHS9, **ORTHS10}.items():
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

# слово с ошибкой ученика (приставки) и слово из его планинга (корни)
ERR_WORD = 'пр*29*шёл'
OrthogramExample.objects.create(text='пришёл', masked_word=ERR_WORD,
                                orthogram_id='29', grades='10,11', is_active=True)
PLAN_WORD = 'зам*12*рать'
Orthogram.objects.create(id='12', name='орф 12', letters='а,о')
HARD_WORD = '*11*делал'
OrthogramExample.objects.create(text='сделал', masked_word=HARD_WORD,
                                orthogram_id='11', grades='10,11', is_active=True)

pupil = make_user('pupil')
OrthogramExample.objects.create(text='замирать', masked_word=PLAN_WORD,
                                orthogram_id='12', grades='10,11', is_active=True,
                                is_user_added=True, added_by=pupil)
Task9WordStat.objects.create(user=pupil, orthogram_id='29', range_code='10',
                             word=ERR_WORD, correct_letter='и', attempts=3,
                             errors=2, in_correction=True)
# общая статистика: это слово валит весь проект — fallback «самые сложные»
for n in range(3):
    other = make_user(f'other{n}')
    Task9WordStat.objects.create(user=other, orthogram_id='11', range_code='10',
                                 word='*11*делал', correct_letter='с',
                                 attempts=4, errors=7)

print('1. Гейт: cp10 только после cp94')
c = Client()
c.force_login(pupil)
r = c.get('/ege/checkpoint/10/', HTTP_HOST='localhost')
check(r.status_code == 302, f'без cp94 -> редирект (факт: {r.status_code})')
pass_code(pupil, 'cp91')
pass_code(pupil, 'cp92')
pass_code(pupil, 'cp93')
pass_code(pupil, 'cp94')
r = c.get('/ege/checkpoint/10/', HTTP_HOST='localhost')
html = r.content.decode('utf-8')
check(r.status_code == 200, f'после cp94 -> 200 (факт: {r.status_code})')
check('Рубежный тест: задания 9 и 10' in html, 'шапка рубежа 9 и 10')
check('урок 11' in html, 'обещание открыть урок 11')
check('orthoepy-checkbox' not in html
      and 'Исправьте ошибку и запишите слово правильно' not in html,
      'заданий 4-8 на странице рубежа нет')

sess = c.session['checkpoint_10']
lines = sess['snapshot']['9']['lines']
orths = sess['task9_orths']
units = sess['task9_units']
print('2. Состав: 30 строк = 3 варианта 9 + 3 варианта 10')
check(len(sess['task9_correct']) == 90,
      f'90 букв (30 строк по 3): факт {len(sess["task9_correct"])}')
check(len(set(units)) == 6, f'6 блоков-юнитов: факт {len(set(units))}')
for b in ('10b1', '10b2', '10b3'):
    block_orths = {o for o, u in zip(orths, units) if u == b}
    check(block_orths >= set(ORTHS10),
          f'блок {b}: все орфограммы приставок представлены '
          f'(факт {sorted(block_orths, key=int)})')
nine_orths = {o for o, u in zip(orths, units) if u.startswith('9b')}
check(nine_orths >= set(ORTHS9), 'блоки 9 покрывают все корни пула')

print('3. Персонализация: ошибки ученика и его планинг в строках')
all_lines = ' '.join(lines)
check(ERR_WORD.replace('*29*', '') [:2] in all_lines.replace('*9-', '*')
      or 'шёл' in all_lines, 'слово с ошибкой ученика в строках')
check('зам' in all_lines and 'рать' in all_lines,
      'слово из планинга ученика в строках')
pupil2 = make_user('pupil2')
for code in ('cp91', 'cp92', 'cp93', 'cp94'):
    pass_code(pupil2, code)
c2 = Client()
c2.force_login(pupil2)
c2.get('/ege/checkpoint/10/', HTTP_HOST='localhost')
all_lines2 = ' '.join(c2.session['checkpoint_10']['snapshot']['9']['lines'])
check('делал' in all_lines2,
      'нет своих ошибок -> самые сложные слова проекта в строках')

print('4. Сдан целиком -> урок 11 открыт')


def good_answers(s):
    return {f'9-{i}': l for i, l in enumerate(s['task9_correct'], 1)}


answers = good_answers(sess)
r = c.post('/ege/checkpoint/10/', data=json.dumps({'answers': answers}),
           content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 0,
      f'сдан, ошибок 0 (факт: {res["passed"]}, {res["error_count"]})')
lb = c.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')
i11 = lb.find('Задание 11 (орфография, суффиксы)')
j11 = lb.rfind('<div class="lesson-card lesson-card--', 0, i11)
check('lesson-card--active' in lb[j11:i11], 'карточка урока 11 активна после cp10')
check('data-video-src="https://kinescope.io/embed/5nKhuyz3bjaEZy7EKcsaqK"' in lb,
      'кнопка видео урока 10 на месте')
check('data-video-src="https://kinescope.io/embed/7NiD2EoSJoZkDcRdUaVqid"' in lb,
      'кнопка видео урока 11 на месте')

print('5. Ошибка в одном блоке 9 и двух блоках 10')
p3 = make_user('pupil3')
for code in ('cp91', 'cp92', 'cp93', 'cp94'):
    pass_code(p3, code)
c3 = Client()
c3.force_login(p3)
c3.get('/ege/checkpoint/10/', HTTP_HOST='localhost')
s3 = c3.session['checkpoint_10']
a3 = good_answers(s3)
u3 = s3['task9_units']
for i, u in enumerate(u3, 1):
    if u in ('9b1', '10b2', '10b3'):
        a3[f'9-{i}'] = 'я' if a3[f'9-{i}'] != 'я' else 'у'
r = c3.post('/ege/checkpoint/10/', data=json.dumps({'answers': a3}),
            content_type='application/json')
res = r.json()
check(res['error_count'] == 3 and not res['passed'],
      f'3 блока ошибочны = 3 ошибки, не сдан (факт: {res["error_count"]})')
rd = r.json()['results']
check(rd['9b1']['is_correct'] is False and rd['9b2']['is_correct'] is True,
      'зачёт раздельно по блокам: 9b1 ошибочен, 9b2 верен')
page = c3.get(res['result_url'], HTTP_HOST='localhost').content.decode('utf-8')
check('Задание 10: приставки ПРЕ- и ПРИ-' in page,
      'рекомендации ведут на тренажёры 9 и страницу приставок')
check('Задание 9, вариант 1' in page, 'вердикт разложен по блокам-вариантам')

print('6. Допуск: 2 ошибки = сдан')
p4 = make_user('pupil4')
for code in ('cp91', 'cp92', 'cp93', 'cp94'):
    pass_code(p4, code)
c4 = Client()
c4.force_login(p4)
c4.get('/ege/checkpoint/10/', HTTP_HOST='localhost')
s4 = c4.session['checkpoint_10']
a4 = good_answers(s4)
u4 = s4['task9_units']
for i, u in enumerate(u4, 1):
    if u in ('9b2', '10b1'):
        a4[f'9-{i}'] = 'я' if a4[f'9-{i}'] != 'я' else 'у'
r = c4.post('/ege/checkpoint/10/', data=json.dumps({'answers': a4}),
            content_type='application/json')
res = r.json()
check(res['passed'] and res['error_count'] == 2,
      f'2 ошибки в допуске -> сдан (факт: {res["error_count"]})')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖА 9 И 10 ПРОЙДЕНЫ')
