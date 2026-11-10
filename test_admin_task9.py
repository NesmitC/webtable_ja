# -*- coding: utf-8 -*-
"""Тест админки статистики задания 9: ленты, фильтры, разбор попытки по словам.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_admin_task9.py
"""
import os
import sys

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

from main.models import Task9Attempt, Task9AttemptWord, Task9WordStat

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
admin = User.objects.create_superuser('owner', 'owner@example.com', 'Zk9mQ2vLp7xR')
pupil = User.objects.create_user('sasha', 'sasha@example.com', 'OldPass123!')

att = Task9Attempt.objects.create(user=pupil, orthogram_id='1', range_code='9',
                                  total_words=3, chosen_count=3, correct_count=2)
Task9AttemptWord.objects.create(attempt=att, word='з*1*мля', chosen_letter='и',
                                correct_letter='е', is_correct=False)
Task9AttemptWord.objects.create(attempt=att, word='в*1*сна', chosen_letter='е',
                                correct_letter='е', is_correct=True)
Task9WordStat.objects.create(user=pupil, orthogram_id='1', range_code='9',
                             word='з*1*мля', correct_letter='е', attempts=2,
                             errors=1, last_result=False, last_chosen_letter='и',
                             last_seen=timezone.now(), in_correction=True,
                             correction_since=timezone.now().date())

c = Client()
c.force_login(admin)

print('1. Ленты статистики в админке')
r = c.get('/admin/main/task9attempt/', HTTP_HOST='localhost')
page = r.content.decode('utf-8')
check(r.status_code == 200, f'лента прохождений -> 200 (факт: {r.status_code})')
check('sasha' in page and 'з*1*мля' not in page, 'в ленте ученик, слов-разбора нет')
r = c.get('/admin/main/task9wordstat/', HTTP_HOST='localhost')
page = r.content.decode('utf-8')
check(r.status_code == 200, f'накопительная статистика -> 200 (факт: {r.status_code})')
check('з*1*мля' in page, 'слово на коррекции видно в ленте')

print('2. Фильтры и поиск')
r = c.get('/admin/main/task9attempt/?range_code=9', HTTP_HOST='localhost')
check(r.status_code == 200 and 'sasha' in r.content.decode('utf-8'),
      'фильтр по блоку (range_code) работает')
r = c.get('/admin/main/task9attempt/?q=sasha', HTTP_HOST='localhost')
check('sasha' in r.content.decode('utf-8'), 'поиск по ученику работает')
r = c.get('/admin/main/task9wordstat/?in_correction=1', HTTP_HOST='localhost')
check('з*1*мля' in r.content.decode('utf-8'), 'фильтр «на коррекции» работает')

print('3. Разбор попытки по словам')
r = c.get(f'/admin/main/task9attempt/{att.id}/change/', HTTP_HOST='localhost')
page = r.content.decode('utf-8')
check(r.status_code == 200, f'карточка попытки -> 200 (факт: {r.status_code})')
check('з*1*мля' in page and 'в*1*сна' in page, 'инлайн показывает оба слова')
check('Выбранная буква' in page or 'chosen_letter' in page,
      'в инлайне виден выбор ученика')

print('4. История неизменяема руками')
r = c.post(f'/admin/main/task9attempt/{att.id}/change/',
           data={'correct_count': 3, 'words-TOTAL_FORMS': 0,
                 'words-INITIAL_FORMS': 2, 'words-MIN_NUM_FORMS': 0,
                 'words-MAX_NUM_FORMS': 1000},
           HTTP_HOST='localhost')
att.refresh_from_db()
check(att.correct_count == 2, 'POST не меняет летопись (correct_count остался 2)')
r = c.get('/admin/main/task9attempt/add/', HTTP_HOST='localhost')
check(r.status_code in (302, 403), f'ручное добавление запрещено (факт: {r.status_code})')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ АДМИНКИ СТАТИСТИКИ ПРОЙДЕНЫ')
