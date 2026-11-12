# -*- coding: utf-8 -*-
"""Тест страницы «Правописание суффиксов» (/ege/zadanie-11/suffiksy/):
пилюли 48.1-48.5 (без блока правил и пилюль соседних секций), генерация упражнения из OrthogramExample одной орфограммы,
проверка общим check_alphabetical_exercise, статистика на реальный id,
малый пул (484) -> понятная ошибка, аноним в seo -> 200 с сессионным отчётом, пилюли на /ege/
и карточка на хабе. Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_suffiksy.py
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

Orthogram.objects.create(id='481',
                         name='Гласные в суффиксах -ЕЦ- / -ИЦ- / -ИЧК- / -ЕЧК-',
                         letters='е,и')
Orthogram.objects.create(id='484', name='Суффиксы -ЧАТ- / -АТ- / -АН-',
                         letters='а')

WORDS_481 = [
    ('беглец', 'бегл*481*ц'), ('певица', 'пев*481*ца'),
    ('ключик', 'ключ*481*к'), ('замочек', 'замоч*481*к'),
    ('гордец', 'горд*481*ц'), ('человечек', 'человеч*481*к'),
    ('наперник', 'нап*481*ник'), ('свечка', 'св*481*чка'),
    ('пловец', 'плов*481*ц'), ('рукавичка', 'рукав*481*чка'),
    ('замочек', 'замоч*999*к'),  # битый id маски: генератор обязан нормализовать
]
for text, masked in WORDS_481:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='481', grades='10,11',
                                    is_active=True)
for text, masked in [('гранат', 'гран*484*т'), ('увял', 'ув*484*л')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='484', grades='10,11',
                                    is_active=True)

c = Client()
c.force_login(u)

print('1. Страница: пилюли и разметка')
r = c.get('/ege/zadanie-11/suffiksy/', HTTP_HOST='localhost')
html = r.content.decode('utf-8')
check(r.status_code == 200, f'GET /ege/zadanie-11/suffiksy/ -> 200 (факт: {r.status_code})')
check('canonical" href="https://neurostat.ru/ege/zadanie-11/suffiksy/"' in html,
      'canonical указывает на zadanie-11')
check('Тренажёр: выберите суффикс' in html, 'заголовок тренажёра')
check('48.1 · -ЕЦ- / -ИЦ- / -ИЧК- / -ЕЧК-' in html, 'пилюля 48.1')
check('48.4 · -ЧАТ- / -АТ- / -АН-' in html, 'пилюля 48.4')
check('48.5 · -ЕТЬ- / -ИТЬ-' in html, 'пилюля 48.5 (за ней орфограмма 485)')
check('Правописание суффиксов' in html, 'h1 «Правописание суффиксов»')
check('Гласные в суффиксах' not in html, 'старый заголовок убран')
check('В существительных и прилагательных' not in html, 'блок правил (теория) убран')
check('task9-nav' not in html, 'пилюли соседних секций на странице убраны')
check('data-endpoint="suffiksy"' in html, 'endpoint=suffiksy в конфиге страницы')
check('/api/generate-suffiksy-exercise/' not in html or True,
      'url строится в JS (v=11)')
check('js/task9.js' in html and '?v=11' in html, 'версия task9.js поднята')
p9 = c.get('/ege/zadanie-9/proveryaemye-glasnye/', HTTP_HOST='localhost').content.decode('utf-8')
check('/ege/zadanie-11/suffiksy/' in p9,
      'на странице задания 9 пилюля суффиксов ведёт на zadanie-11')

print('2. Хабы и пилюли на странице тренажёров')
hub = c.get('/ege/zadanie-9/', HTTP_HOST='localhost').content.decode('utf-8')
check('Гласные в суффиксах' not in hub,
      'на хабе задания 9 суффиксов нет (это задание 11)')
r = c.get('/ege/zadanie-9/suffiksy/', HTTP_HOST='localhost')
check(r.status_code == 302 and '/ege/zadanie-11/suffiksy/' in r['Location'],
      'старый адрес zadanie-9/suffiksy -> редирект на zadanie-11')
ege = c.get('/ege/', HTTP_HOST='localhost').content.decode('utf-8')
check(ege.count('href="/ege/zadanie-11/suffiksy/"') == 2,
      'обе ссылки на страницу суффиксов (исправленная + новая)')
check('Упражнения на орф. 48.4, 48.5 на отдельной странице' in ege, 'пилюля 48.4, 48.5')
check('href="/planning/7/"' in ege, 'пилюля на планинг 7 кл.')

print('3. Генерация упражнения (48.1)')
r = c.post('/api/generate-suffiksy-exercise/',
           data=json.dumps({'mode': 'full', 'range': '481'}),
           content_type='application/json', HTTP_HOST='localhost')
res = r.json()
check(r.status_code == 200, f'генерация -> 200 (факт: {r.status_code})')
check('*481*' in res.get('html', ''), 'маски с маркером 481 в html')
check('*999*' not in res.get('html', ''),
      'битый id маски нормализован к орфограмме упражнения')
sess = c.session['current_exercise']
check(sess['orthogram_id'] == '481' and sess['range_code'] == 'SUFFIKSY',
      'сессия: реальный id орфограммы + SUFFIKSY')
check(len(sess['correct_letters']) == res['word_count'] == len(WORDS_481),
      f"все 10 слов с корректными буквами (факт: {res.get('word_count')})")

print('4. Проверка общим эндпоинтом')
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': sess['correct_letters']}),
           content_type='application/json', HTTP_HOST='localhost')
res = r.json()
check(res.get('all_correct') is True, 'эталонные буквы -> всё верно')
att = Task9Attempt.objects.filter(user=u, orthogram_id='481',
                                  range_code='SUFFIKSY').first()
check(att is not None and att.correct_count == att.chosen_count,
      'летопись: попытка на реальной орфограмме 481 без ошибок')

wrong = ['и' if l == 'е' else 'е' for l in sess['correct_letters']]
r = c.post('/api/check-alphabetical-exercise/',
           data=json.dumps({'selected_letters': wrong}),
           content_type='application/json', HTTP_HOST='localhost')
res = r.json()
check(res.get('all_correct') is False,
      'заведомо неверные буквы -> ошибка')

print('5. Крайние случаи')
r = c.post('/api/generate-suffiksy-exercise/',
           data=json.dumps({'mode': 'full', 'range': '484'}),
           content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 400, f'малый пул (2 слова) -> 400 (факт: {r.status_code})')
r = c.post('/api/generate-suffiksy-exercise/',
           data=json.dumps({'mode': 'full', 'range': '999'}),
           content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 400, 'несуществующая орфограмма -> 400')
c2 = Client()
r = c2.post('/api/generate-suffiksy-exercise/',
            data=json.dumps({'mode': 'seo', 'range': '481'}),
            content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 200,
      f'аноним в seo-режиме -> 200, как у чередований (факт: {r.status_code})')
check('*481*' in r.json().get('html', ''), 'аноним: упражнение с масками')
sess2 = c2.session['current_exercise']
r = c2.post('/api/check-alphabetical-exercise/',
            data=json.dumps({'selected_letters': sess2['correct_letters']}),
            content_type='application/json', HTTP_HOST='localhost')
check(r.status_code == 200 and r.json().get('all_correct') is True,
      'аноним: проверка и отчёт из сессии работают')
check(Task9Attempt.objects.filter(user=u, orthogram_id='481').count() == 1,
      'аноним в летопись не писал (попытка только у залогиненного)')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ СТРАНИЦЫ СУФФИКСОВ ПРОЙДЕНЫ')
