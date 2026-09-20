# -*- coding: utf-8 -*-
"""Тест защиты от дублей диагностики + форма звонка на крайних баллах.
Изоляция: test_settings_isolated. Запуск: python test_diag_dedup.py
"""
import json
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from django.test import override_settings

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from main.models import DiagnosticAttempt

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


def build_answers(sess, mode='perfect'):
    correct = dict(sess.get('test_fixdiagnostic_ege_2027_correct', {}))
    answers = dict(correct)
    for key in ('test_fixdiagnostic_ege_2027_task8_matches',
                'test_fixdiagnostic_ege_2027_task22_matches'):
        prefix = '8' if key.endswith('task8_matches') else '22'
        for letter, val in (sess.get(key) or {}).items():
            answers[f'{prefix}_{letter}'] = val
    if mode == 'zero':
        for k in list(answers):
            if isinstance(answers[k], list):
                answers[k] = ['9']
            else:
                answers[k] = 'zzz'
    return answers


with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
    print('1. Двойная отправка одних и тех же ответов')
    c = Client()
    c.get('/diagnostic/fix-ege/')
    answers = build_answers(c.session)
    r1 = c.post('/diagnostic/fix-ege/', data=json.dumps({'answers': answers}),
                content_type='application/json')
    r2 = c.post('/diagnostic/fix-ege/', data=json.dumps({'answers': answers}),
                content_type='application/json')
    import time
    time.sleep(1.2)  # письмо уходит фоновым потоком
    j1, j2 = r1.json(), r2.json()
    check(j1.get('attempt_id') == j2.get('attempt_id'),
          'второй POST вернул ту же попытку')
    check(j1['total_score'] == 28,
          f'балл на странице без фантомного минуса: 28 (факт: {j1["total_score"]})')
    check(DiagnosticAttempt.objects.count() == 1,
          f'в БД одна попытка (факт: {DiagnosticAttempt.objects.count()})')
    check(len(mail.outbox) == 1, f'письмо владельцу одно (факт: {len(mail.outbox)})')

    print('2. Другие ответы -> новая попытка')
    answers2 = build_answers(c.session)
    answers2['1'] = 'zzz'
    r3 = c.post('/diagnostic/fix-ege/', data=json.dumps({'answers': answers2}),
                content_type='application/json')
    check(r3.json().get('attempt_id') != j1.get('attempt_id'),
          'изменённые ответы создали новую попытку')
    check(DiagnosticAttempt.objects.count() == 2, 'попыток стало две')

    print('3. Форма звонка при максимальном балле')
    a_max = DiagnosticAttempt.objects.get(id=j1['attempt_id'])
    rb = c.get(f'/diagnostic/result/{a_max.id}/').content.decode('utf-8')
    check(a_max.primary_score == 28 and a_max.score == 55,
          f'попытка: 28/50 первичных, 55/100 тестовых '
          f'(факт: {a_max.primary_score}/{a_max.score})')
    check('callbackForm' in rb and '5 дней полного доступа' in rb,
          'на максимальном результате есть форма звонка и строка про 5 дней')

    print('4. Форма звонка при 0 баллов')
    c0 = Client()
    c0.get('/diagnostic/fix-ege/')
    zero = build_answers(c0.session, mode='zero')
    rz = c0.post('/diagnostic/fix-ege/', data=json.dumps({'answers': zero}),
                 content_type='application/json')
    a0 = DiagnosticAttempt.objects.get(id=rz.json()['attempt_id'])
    rb0 = c0.get(f'/diagnostic/result/{a0.id}/').content.decode('utf-8')
    check(a0.score == 0, f'балл попытки = 0 (факт: {a0.score})')
    check('callbackForm' in rb0 and 'Жду звонка' in rb0,
          'на результате 0/100 есть форма «Жду звонка»')
    check('Слабые задания' in rb0, 'при 0 баллов показан список слабых заданий')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('   -', f)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ДУБЛЕЙ И ФОРМЫ ПРОЙДЕНЫ')
