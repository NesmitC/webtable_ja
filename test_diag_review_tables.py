# -*- coding: utf-8 -*-
"""Тест разбора входящей диагностики: таблицы 8/22 показывают ответы ученика
(оба формата ключей), колонка-знак удалена, «Ответ» красится; задания 23/24
без двойной нумерации; чек принимает ключи JS '8_А'.

Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.
Запуск: .\\.venv\\Scripts\\python.exe test_diag_review_tables.py
"""
import json
import os
import sys
from datetime import timedelta

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

from main.models import DiagnosticAttempt, UserProfile
from main.views import _match_rows, _strip_choice_nums, build_student_work

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()

MATCH_TASK = {
    'correct_matches': {'А': '2', 'Б': '6', 'В': '7', 'Г': '3', 'Д': '5'},
    'errors': [
        {'letter': 'А', 'name': 'Причастный оборот'},
        {'letter': 'Б', 'name': 'Видо-временная соотнесённость'},
        {'letter': 'В', 'name': 'Деепричастный оборот'},
        {'letter': 'Г', 'name': 'Связь подлежащего и сказуемого'},
        {'letter': 'Д', 'name': 'Падежная форма с предлогом'},
    ],
}

print('1. _match_rows: ответы находятся в обоих форматах ключей')
rows = _match_rows(MATCH_TASK, {'8_А': '2', '8_Б': '8', '8_В': '7'}, {}, 8)
by = {r['letter']: r for r in rows}
check(by['А']['user'] == '2' and by['А']['touched'], 'ключ 8_А: ответ виден (А=2)')
check(by['Б']['user'] == '8', 'ключ 8_Б: ответ виден (Б=8)')
check(by['Г']['user'] == '—' and not by['Г']['touched'], 'неотвечанная строка: прочерк')
check(by['А']['correct'] == '2' and by['Б']['correct'] == '6', 'колонка «Правильно» заполнена')

rows2 = _match_rows(MATCH_TASK, {'8-А': '2'}, {}, 8)
check({r['letter']: r for r in rows2}['А']['user'] == '2',
      'старый формат ключа 8-А тоже виден')

det_results = {'8': {'details': {'8-В': {'user_answer': '7', 'is_correct': True}}}}
rows3 = _match_rows(MATCH_TASK, {}, det_results, 8)
r3 = {r['letter']: r for r in rows3}['В']
check(r3['user'] == '7' and r3['is_correct'] is True,
      'fallback: ответ и верность берутся из details результата')

rows4 = _match_rows(MATCH_TASK, {'8_А': '2'},
                    {'8_А': {'is_correct': True}, '8_Б': {'is_correct': False}}, 8)
r4 = {r['letter']: r for r in rows4}
check(r4['А']['is_correct'] is True and r4['Б']['is_correct'] is False,
      'верность берётся из results по ключу с подчёркиванием')

print('2. Нумерация вариантов 23/24 не дублируется')
stripped = _strip_choice_nums(['1) Современники рассказчика', '2) Авиация'])
check(stripped == ['Современники рассказчика', 'Авиация'],
      f'встроенные номера сняты: {stripped}')
fixture = {
    'tasks': {
        '23_27': {'text': 'Текст', 'questions': {
            '23': {'text': 'Какие из высказываний...',
                   'choices': ['1) Первое', '2) Второе'],
                   'correct_answer': '12'},
            '24': {'text': 'Какие из перечисленных...',
                   'choices': ['1) А', '2) Б'], 'correct_answer': '1'},
        }},
    },
    'correct_answers': {},
}
work = build_student_work(fixture, {'user_answers': {}, 'results': {}})
tb = [w for w in work if w.get('num') == '23–26'][0]
q23 = tb['questions'][0]
check(all(not c[:2].rstrip(') ').isdigit() or not c.startswith(('1)', '2)'))
          for c in q23['choices']),
      f'choices пришли без номеров: {q23["choices"]}')

print('3. Чек входящей принимает ключи JS (8_А)')
c = Client()
s = c.session
s['starting_diagnostic'] = {
    'task8_correct': {'А': '2', 'Б': '6', 'В': '7', 'Г': '3', 'Д': '5'},
}
s.save()
resp = c.post('/api/check-starting-diagnostic/',
              data=json.dumps({'answers': {'8_А': '2', '8_Б': '8', '8_В': '7'}}),
              content_type='application/json')
check(resp.status_code == 200, f'чек ответил 200 (факт {resp.status_code})')
res8 = resp.json()['results']['8']
check(res8['correct_count'] == 2,
      f'засчитано 2 верных из ответов в формате 8_А (факт {res8["correct_count"]})')
check(res8['score'] == 0, f'2 верных = 0 баллов по шкале (факт {res8["score"]})')
det = res8['details']['8-А']
check(det['user_answer'] == '2', 'user_answer попал в details (А=2)')

print('4. Страница разбора преподавателем: таблица 8 и номера 23/24')
admin = User.objects.create_superuser('boss2', 'boss2@example.com', 'Zk9mQ2vLp7xR')
answers_data = {
    'user_answers': {'8_А': '2', '8_Б': '8', '8_В': '7', '23': '12', '24': '1'},
    'results': {
        '8': {'score': 1, 'max_possible': 2, 'correct_count': 2,
              'details': {'8-А': {'user_answer': '2', 'is_correct': True},
                          '8-Б': {'user_answer': '8', 'is_correct': False},
                          '8-В': {'user_answer': '7', 'is_correct': True}}},
        '8_А': {'is_correct': True}, '8_Б': {'is_correct': False},
        '8_В': {'is_correct': True},
    },
}
attempt = DiagnosticAttempt.objects.create(
    user=admin, test_code='test_fixdiagnostic_ege_2027',
    primary_score=10, score=20, max_score=100,
    answers_data=answers_data, weak_topics=[8], is_completed=True)
ca = Client()
ca.force_login(admin)
rv = ca.get(f'/staff/diagnostic/{attempt.id}/')
check(rv.status_code == 200, f'разбор отдался (факт {rv.status_code})')
html = rv.content.decode('utf-8')
check('rv-col--mark' not in html, 'пустой колонки-знака больше нет')
check('sw-ans--ok">2<' in html.replace('\n', '').replace(' ', '') or
      'sw-ans--ok">2</span>' in html, 'верный ответ 2 подсвечен зелёным')
check('sw-ans--no">8</span>' in html, 'неверный ответ 8 подсвечен красным')
check(html.count('1) 1)') == 0, 'двойной нумерации «1) 1)» нет')
check('Что сопоставляем' in html and 'Правильно' in html, 'колонки таблицы на месте')

print('5. Страница разбора учеником: та же таблица')
student = User.objects.create_user('pupil2', 'pupil2@example.com', 'Zk9mQ2vLp7xR')
a2 = DiagnosticAttempt.objects.create(
    user=student, test_code='test_fixdiagnostic_ege_2027',
    primary_score=10, score=20, max_score=100,
    answers_data=answers_data, is_completed=True)
cs = Client()
cs.force_login(student)
rs = cs.get(f'/my/diagnostic/{a2.id}/')
check(rs.status_code == 200, f'разбор ученика отдался (факт {rs.status_code})')
h2 = rs.content.decode('utf-8')
check('rv-col--mark' not in h2, 'у ученика колонки-знака нет')
check('sw-ans--ok">2</span>' in h2 and 'sw-ans--no">8</span>' in h2,
      'у ученика ответы тоже красятся')
check(h2.count('1) 1)') == 0, 'у ученика двойной нумерации нет')

print('6. Регресс: чужой ученик не видит разбор (403/404)')
other = User.objects.create_user('other2', 'other2@example.com', 'Zk9mQ2vLp7xR')
co = Client()
co.force_login(other)
ro = co.get(f'/my/diagnostic/{a2.id}/')
check(ro.status_code in (403, 404), f'чужая попытка недоступна (факт {ro.status_code})')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('   -', f)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ТАБЛИЦ РАЗБОРА ПРОЙДЕНЫ')
