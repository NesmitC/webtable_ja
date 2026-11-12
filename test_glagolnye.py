# -*- coding: utf-8 -*-
"""Тест страницы «Глагольные формы» (/ege/zadanie-12/glagolnye-formy/):
кнопки 51.1-51.3, генерация из OrthogramExample одной орфограммы, проверка
общим check_alphabetical_exercise, статистика на реальный id, малый пул -> 400,
аноним в seo -> 200 с сессионным отчётом, пилюли на /ege/ и /ege/trainers/,
страницы 9.x без пилюли новой секции. Изоляция: test_settings_isolated.

Запуск: .\\.venv\\Scripts\\python.exe test_glagolnye.py
"""
import json
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from datetime import timedelta
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main.models import (Orthogram, OrthogramExample, Task9Attempt,
                         UserProfile)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
u = User.objects.create_user(username='p', email='p@example.com',
                             password='Zk9mQ2vLp7xR')
prof, _ = UserProfile.objects.get_or_create(user=u)
prof.trial_until = timezone.now() + timedelta(days=5)
prof.save()

Orthogram.objects.create(id='511',
                         name='Гласные перед -ВШ- в действ. прич',
                         letters='а,е,и,я')
Orthogram.objects.create(id='512',
                         name='Гласная в суфф. глаг. пов. наклонения',
                         letters='е,и')
Orthogram.objects.create(id='513', name='Глаголы с приставкой ВЫ-',
                         letters='а,о,е,и,я,у,ю')
Orthogram.objects.create(id='519', name='мало слов', letters='а,о')

WORDS_511 = [
    ('вытерпевший', 'вытерп*511*ший'), ('ненавидевший', 'ненавид*511*ший'),
    ('обидевший', 'обид*511*ший'), ('видевший', 'вид*511*ший'),
    ('слышавший', 'слыш*511*ший'), ('клеивший', 'кле*511*ший'),
    ('сеявший', 'се*511*ший'), ('веявший', 'ве*511*ший'),
    ('лаявший', 'ла*511*ший'), ('чаявший', 'ча*511*ший'),
    ('таявший', 'та*999*ший'),  # битый id маски: генератор обязан нормализовать
]
WORDS_512 = [
    ('выйдите', 'выйд*512*те'), ('крикните', 'крикн*512*те'),
    ('выжмите', 'выж*512*мите'), ('поставьте', 'постав*512*те'),
]
WORDS_513 = [
    ('вылетишь', 'вылет*513*шь'), ('выгоришь', 'выгор*513*шь'),
    ('выбежишь', 'выбеж*513*шь'), ('вымостишь', 'вымост*513*шь'),
]
for text, masked in WORDS_511:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='511', grades='10,11',
                                    is_active=True)
for text, masked in WORDS_512:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='512', grades='10,11',
                                    is_active=True)
for text, masked in WORDS_513:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='513', grades='10,11',
                                    is_active=True)
for text, masked in [('слово', 'сл*519*во'), ('ещё', 'е*519*щё')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='519', grades='10,11',
                                    is_active=True)

c = Client()
c.force_login(u)

print('1. Страница: разметка и кнопки')
r = c.get('/ege/zadanie-12/glagolnye-formy/', HTTP_HOST='localhost')
html = r.content.decode('utf-8')
check(r.status_code == 200, f'GET -> 200 (факт: {r.status_code})')
check('canonical" href="https://neurostat.ru/ege/zadanie-12/glagolnye-formy/"'
      in html, 'canonical указывает на zadanie-12')
check('Глагольные формы' in html, 'h1 «Глагольные формы»')
check('51.1 · гласная перед -ВШ-' in html and '51.3 · приставка ВЫ-' in html,
      'кнопки 51.1-51.3 на месте')
check('Поставить глагол в неопределённую форму' not in html
      and 'Отбросить окончание' not in html,
      'блок правил (теория) убран')
check('task9-nav' not in html, 'пилюли соседних секций скрыты')
check('?v=11' in html, 'версия task9.js поднята до v=11')
check('data-endpoint="glagolnye"' in html, 'endpoint=glagolnye в конфиге страницы')

print('2. Пилюли на страницах тренажёров')
for url in ('/ege/trainers/', '/ege/'):
    page = c.get(url, HTTP_HOST='localhost').content.decode('utf-8')
    check(page.count('href="/ege/zadanie-12/glagolnye-formy/"') == 2,
          f'{url}: две пилюли на страницу глагольных форм')
p9 = c.get('/ege/zadanie-9/proveryaemye-glasnye/',
           HTTP_HOST='localhost').content.decode('utf-8')
check('Глагольные формы' not in p9, 'на страницах 9.x пилюли новой секции нет')

print('3. Генерация упражнения (51.1)')
r = c.post('/api/generate-glagolnye-exercise/',
           data=json.dumps({'mode': 'full', 'range': '511'}),
           content_type='application/json', HTTP_HOST='localhost')
res = r.json()
check(r.status_code == 200, f'генерация -> 200 (факт: {r.status_code})')
check('*511*' in res.get('html', ''), 'маски с маркером 511 в html')
check('*999*' not in res.get('html', ''), 'битый id маски нормализован')
sess = c.session['current_exercise']
check(sess['orthogram_id'] == '511' and sess['range_code'] == 'GLAGOLNYE',
      'сессия: реальный id орфограммы + GLAGOLNYE')
check(len(sess['correct_letters']) == res['word_count'] == len(WORDS_511),
      f'все слова с корректными буквами (факт: {res.get("word_count")})')

print('4. Проверка общим эндпоинтом')
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': sess['correct_letters']}),
           content_type='application/json', HTTP_HOST='localhost')
res = r.json()
check(res.get('all_correct') is True, 'эталонные буквы -> всё верно')
att = Task9Attempt.objects.filter(user=u, orthogram_id='511',
                                  range_code='GLAGOLNYE').first()
check(att is not None and att.correct_count == att.chosen_count,
      'летопись: попытка на реальной орфограмме 511 без ошибок')

print('5. Крайние случаи')
r = c.post('/api/generate-glagolnye-exercise/',
           data=json.dumps({'mode': 'full', 'range': '519'}),
           content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 400, f'малый пул (2 слова) -> 400 (факт: {r.status_code})')
r = c.post('/api/generate-glagolnye-exercise/',
           data=json.dumps({'mode': 'full', 'range': '999'}),
           content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 400, 'несуществующая орфограмма -> 400')
c2 = Client()
r = c2.post('/api/generate-glagolnye-exercise/',
            data=json.dumps({'mode': 'seo', 'range': '513'}),
            content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 200,
      f'аноним в seo-режиме -> 200, как у чередований (факт: {r.status_code})')
sess2 = c2.session['current_exercise']
r = c2.post('/api/check-alphabetical-exercise/',
            data=json.dumps({'selected_letters': sess2['correct_letters']}),
            content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 200 and r.json().get('all_correct') is True,
      'аноним: проверка и отчёт из сессии работают')
check(Task9Attempt.objects.filter(user=u, orthogram_id='511').count() == 1,
      'аноним в летопись не писал')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ СТРАНИЦЫ ГЛАГОЛЬНЫХ ФОРМ ПРОЙДЕНЫ')
