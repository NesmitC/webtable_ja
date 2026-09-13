# -*- coding: utf-8 -*-
"""Тест летописи задания 9: generate -> check -> отчёт -> коррекция -> история.
Изоляция: test_settings_isolated (SQLite в памяти, боевая БД не трогается).

Запуск: .\\.venv\\Scripts\\python.exe test_task9_chronicle.py
"""
import json
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings

assert settings.DATABASES['default']['NAME'] == ':memory:'
print('Изоляция OK: SQLite в памяти')

from django.core.management import call_command
from django.test.utils import setup_test_environment

setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model
from django.test import Client

from main.models import (
    Orthogram, OrthogramExample, Task9Attempt, Task9AttemptWord, Task9WordStat,
)

User = get_user_model()
FAILS = []


def check(cond, msg):
    print(('  ✅ ' if cond else '  ❌ ') + msg)
    if not cond:
        FAILS.append(msg)


# === данные: орфограмма 1 (проверяемые гласные), слова на А-О и П-С ===
Orthogram.objects.create(id='1', name='Безударные проверяемые', rule='тест',
                         letters='а,о,е,и,я')
WORDS = [
    # (text, masked)  — маска *1* на месте проверяемой буквы
    ('земля', 'з*1*мля'),      # е
    ('вода', 'в*1*да'),        # о
    ('гора', 'г*1*ра'),        # о
    ('лиса', 'л*1*са'),        # и
]
for text, masked in WORDS:
    OrthogramExample.objects.create(
        orthogram_id='1', text=text, masked_word=masked,
        is_active=True, grades='10,11',
    )

user = User.objects.create_user(username='chronicle', email='ch@example.com',
                                password='Zk9mQ2vLp7xRt4w')
c = Client()
c.force_login(user)

print('\n=== ШАГ 1. generate: отчёт пуст, но присутствует в ответе ===')
r = c.post('/api/generate-alphabetical-exercise/',
           data=json.dumps({'orthogram_id': '1', 'range': 'A-O'}),
           content_type='application/json')
check(r.status_code == 200, f'generate -> {r.status_code}')
gen = r.json()
check('report' in gen, 'в ответе generate есть report')
check(gen['report']['correction'] == [], 'коррекция пуста')
check(gen['report']['attempts'] == [], 'история пуста')
check(gen.get('range_code') == 'A-O', 'range_code в ответе')
words_in_exercise = gen['word_count']
print(f'  слов в упражнении: {words_in_exercise}')
check(words_in_exercise == 4, 'все 4 слова диапазона А-О попали в упражнение')

# правильные буквы из сессии клиента
sess = c.session
correct = sess['current_exercise']['correct_letters']
masked_words = sess['current_exercise']['correct_words']
print(f'  правильные буквы: {correct}')
print(f'  маски: {masked_words}')

print('\n=== ШАГ 2. check с двумя ошибками ===')
# ошибаемся в словах 0 и 1, верно в 2 и 3
answers = ['а', 'а', correct[2], correct[3]]
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': answers}),
           content_type='application/json')
check(r.status_code == 200, f'check -> {r.status_code}')
chk = r.json()
check(chk['correct_count'] == 2, f'верно 2 из 4 (факт {chk["correct_count"]})')
check(chk.get('orthogram_id') == '1', 'orthogram_id в ответе')
rep = chk.get('report') or {}
corr = rep.get('correction', [])
check(len(corr) == 2, f'в коррекции 2 слова (факт {len(corr)})')
if corr:
    item = corr[0]
    print(f'  карточка ошибки: word={item["word"]!r} chosen={item["chosen_letter"]!r} '
          f'correct={item["correct_letter"]!r} since={item["correction_since"]!r}')
    check(item['chosen_letter'] in ('а',), 'красная буква = буква ученика')
    check('*1*' in item['word'], 'маска сохранена для подстановки красной буквы')
hist = rep.get('attempts', [])
check(len(hist) == 1, f'история: 1 прохождение (факт {len(hist)})')
if hist:
    check(hist[0]['correct'] == 2 and hist[0]['chosen'] == 4,
          f"строка истории: верно {hist[0]['correct']} из {hist[0]['chosen']}")
check(Task9Attempt.objects.count() == 1, 'Task9Attempt создан')
check(Task9AttemptWord.objects.count() == 4, 'Task9AttemptWord: 4 записи')
check(Task9WordStat.objects.filter(in_correction=True).count() == 2,
      'статистика: 2 слова на коррекции')

print('\n=== ШАГ 3. повторный generate: летопись видна до ответа ===')
r = c.post('/api/generate-alphabetical-exercise/',
           data=json.dumps({'orthogram_id': '1', 'range': 'A-O'}),
           content_type='application/json')
gen2 = r.json()
check(len(gen2['report']['correction']) == 2, 'ошибки прошлого раза видны при открытии')
check(len(gen2['report']['attempts']) == 1, 'история видна при открытии')

print('\n=== ШАГ 4. check без ошибок: слова снимаются с коррекции ===')
correct2 = c.session['current_exercise']['correct_letters']
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': correct2}),
           content_type='application/json')
chk2 = r.json()
check(chk2['correct_count'] == len(correct2), 'второй проход без ошибок')
resolved = chk2.get('resolved', [])
check(len(resolved) == 2, f'resolved: 2 слова отработаны (факт {len(resolved)})')
rep2 = chk2.get('report') or {}
check(rep2.get('correction') == [], 'коррекция пуста после чистого прохода')
check(len(rep2.get('attempts', [])) == 2, 'история: 2 прохождения')
check(Task9WordStat.objects.filter(in_correction=True).count() == 0,
      'все слова сняты с коррекции')

print('\n=== ШАГ 5. другой диапазон не смешивается с А-О ===')
OrthogramExample.objects.create(orthogram_id='1', text='поле', masked_word='п*1*ле',
                                is_active=True, grades='10,11')
r = c.post('/api/generate-alphabetical-exercise/',
           data=json.dumps({'orthogram_id': '1', 'range': 'P-S'}),
           content_type='application/json')
gen3 = r.json()
check(gen3['report']['attempts'] == [], 'история П-С не содержит проходы А-О')
check(gen3['report']['correction'] == [], 'коррекция П-С пуста')

print('\n=== ШАГ 6. орфограмма 2 (непроверяемые) тоже пишется в летопись ===')
Orthogram.objects.create(id='2', name='Безударные непроверяемые', rule='тест',
                         letters='а,о,е,и,я')
OrthogramExample.objects.create(orthogram_id='2', text='вокзал', masked_word='в*2*кзал',
                                is_active=True, grades='10,11')
r = c.post('/api/generate-alphabetical-exercise/',
           data=json.dumps({'orthogram_id': '2', 'range': 'A-D'}),
           content_type='application/json')
check(r.status_code == 200, f'generate orth2 -> {r.status_code}')
gen_o2 = r.json()
check('report' in gen_o2, 'generate orth2 возвращает report')
cw = c.session['current_exercise']['correct_letters']
wrong = 'о' if cw[0] != 'о' else 'а'
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': [wrong]}),
           content_type='application/json')
chk3 = r.json()
check(chk3.get('orthogram_id') == '2', 'orth2 в ответе')
rep3 = chk3.get('report') or {}
check(len(rep3.get('correction', [])) == 1, 'ошибка orth2 попала в коррекцию')
check(len(rep3.get('attempts', [])) == 1, 'история orth2: 1 прохождение')
check(Task9Attempt.objects.filter(orthogram_id='2').count() == 1,
      'проход orth2 сохранён')

print('\n=== ШАГ 7. буква не выбрана (None) не попадает в летопись ===')
before_words = Task9AttemptWord.objects.count()
before_stats = Task9WordStat.objects.count()
r = c.post('/api/generate-alphabetical-exercise/',
           data=json.dumps({'orthogram_id': '1', 'range': 'A-O'}),
           content_type='application/json')
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': [None, None, None, None]}),
           content_type='application/json')
chk4 = r.json()
check(chk4['correct_count'] == 0, 'ничего не выбрано -> 0 верно')
check(Task9AttemptWord.objects.count() == before_words,
      'слов в летопись не добавилось (None не пишем)')
check(Task9WordStat.objects.count() == before_stats,
      'статистика слов не тронута')
last = Task9Attempt.objects.order_by('-created_at').first()
check(last.chosen_count == 0, 'chosen_count = 0 при пустом проходе')

print('\n=== ШАГ 8. Чередующиеся гласные (CHERED) ===')
Orthogram.objects.create(id='12', name='Чередование а/о', rule='тест', letters='а,о')
OrthogramExample.objects.create(orthogram_id='12', text='лагерь', masked_word='л*12*герь',
                                is_active=True, grades='10,11')
OrthogramExample.objects.create(orthogram_id='12', text='полог', masked_word='п*12*лог',
                                is_active=True, grades='10,11')
r = c.post('/api/generate-chered-exercise/', data=json.dumps({}),
           content_type='application/json')
check(r.status_code == 200, f'generate chered -> {r.status_code}')
gen_ch = r.json()
check(gen_ch.get('orthogram_id') == 'CHERED', 'ключ CHERED в ответе generate')
check('report' in gen_ch, 'generate chered возвращает report')
sess_ch = c.session['current_exercise']
check(sess_ch.get('orthogram_id') == 'CHERED' and sess_ch.get('range_code') == 'CHERED',
      'ключи CHERED в сессии')
check(len(sess_ch.get('correct_words', [])) == 2, 'маски слов сохранены в сессии')
cw_ch = sess_ch['correct_letters']
answers_ch = [('о' if cw_ch[0] != 'о' else 'а'), cw_ch[1]]  # одна ошибка
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': answers_ch}),
           content_type='application/json')
chk_ch = r.json()
check(chk_ch.get('orthogram_id') == 'CHERED', 'check возвращает CHERED')
rep_ch = chk_ch.get('report') or {}
corr_ch = rep_ch.get('correction', [])
check(len(corr_ch) == 1, f'chered: 1 ошибка в коррекции (факт {len(corr_ch)})')
if corr_ch:
    check('*12*' in corr_ch[0]['word'],
          'многоцифровая маска *12* сохранена для красной буквы')
check(len(rep_ch.get('attempts', [])) == 1, 'chered: история 1 прохождение')
check(Task9Attempt.objects.filter(orthogram_id='CHERED').count() == 1,
      'проход CHERED сохранён')
r = c.post('/api/generate-chered-exercise/', data=json.dumps({}),
           content_type='application/json')
gen_ch2 = r.json()
check(len(gen_ch2['report']['attempts']) == 1,
      'летопись chered видна при повторном открытии блока')

print('\n' + ('🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ' if not FAILS else f'⚠️ ПРОВАЛЕНО: {len(FAILS)}'))
for f in FAILS:
    print('   - ' + f)
sys.exit(0 if not FAILS else 2)
