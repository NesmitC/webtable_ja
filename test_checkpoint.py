# -*- coding: utf-8 -*-
"""Тест рубежного теста cp9: персонализация, сдача, провал, ротация, разблокировка.
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint.py
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
                         UserProfile, UserWord)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
u = User.objects.create_user(username='pupil', email='p@example.com',
                             password='Zk9mQ2vLp7xR')
prof, _ = UserProfile.objects.get_or_create(user=u)
prof.trial_until = timezone.now() + timedelta(days=5)
prof.save()

orth, _ = Orthogram.objects.get_or_create(id=1, defaults={'name': 'корни а/о'})
# персональные слова с ошибками: буква «о»
ex1 = OrthogramExample.objects.create(orthogram=orth, text='земляной',
                                      masked_word='з*1*мляной',
                                      incorrect_variant='зимляной',
                                      correct_letters='о')
ex2 = OrthogramExample.objects.create(orthogram=orth, text='покров',
                                      masked_word='п*1*кров',
                                      incorrect_variant='пакров',
                                      correct_letters='о')
ex3 = OrthogramExample.objects.create(orthogram=orth, text='сторонка',
                                      masked_word='ст*1*ронка',
                                      incorrect_variant='старонка',
                                      correct_letters='о')
# дистракторы с другой буквой
ex4 = OrthogramExample.objects.create(orthogram=orth, text='зелёный',
                                      masked_word='з*1*лёный',
                                      incorrect_variant='зилёный',
                                      correct_letters='е')
ex5 = OrthogramExample.objects.create(orthogram=orth, text='весна',
                                      masked_word='в*1*сна',
                                      incorrect_variant='висна',
                                      correct_letters='е')
for ex in (ex1, ex2, ex3):
    UserWord.objects.create(user=u, field_name='корни', text=ex.text,
                            reference_word=ex, error_count=3)

c = Client()
c.force_login(u)

print('1. GET страницы чекпоинта')
r = c.get('/ege/checkpoint/9/')
check(r.status_code == 200, f'GET /ege/checkpoint/9/ -> {r.status_code}')
body = r.content.decode('utf-8')
check('Рубежный тест: задания 1–8' in body, 'заголовок страницы на месте')
check('data-question="4"' in body, 'задание 4 отрендерено')
check('data-question="5"' in body, 'задание 5 отрендерено')
check('data-error-letter="А"' in body or 'task-eight-select' in body, 'задание 8 (соответствие) на месте')
sess = c.session
correct = sess.get('checkpoint_9_correct', {})
check(bool(correct), 'correct-ответы лежат в сессии')
check(correct.get('4') is not None, 'персональный correct для задания 4')
words4 = sess.get('checkpoint_9_words', [])
personal = {w['word'] for w in words4 if w['task'] == 4} & {'земляной', 'покров', 'сторонка'}
check(len(personal) >= 2, f'в задании 4 персональные слова ученика: {sorted(personal)}')

print('2. Сдача без ошибок -> сдан, урок 10 открыт')
answers = {}
for t in ('1', '2', '3', '5', '6', '7'):
    ca = correct.get(t)
    answers[t] = ca[0] if isinstance(ca, list) else ca
answers['4'] = ' '.join(correct.get('4', []))
m8 = sess.get('checkpoint_9_task8_matches', {})
for letter, val in m8.items():
    answers[f'8_{letter}'] = val
r = c.post('/ege/checkpoint/9/', data=json.dumps({'answers': answers}),
           content_type='application/json')
check(r.status_code == 200, f'POST -> {r.status_code}')
res = r.json()
check('result_url' in res, 'вернулся result_url')
a = CheckpointAttempt.objects.first()
check(a is not None and a.passed, 'попытка сохранена и passed=True')
check(a.correct_count == 8, f'correct_count=8 (факт: {a.correct_count})')
r = c.get(res['result_url'])
check(r.status_code == 200 and 'Рубеж сдан' in r.content.decode('utf-8'),
      'вердикт: сдан')
r = c.get('/ege/lessons/')
check(b'lesson-card--active' in r.content and 'Рубежный тест: задания 1–8' in
      r.content.decode('utf-8'), 'строка чекпоинта на странице уроков')
lessons_body = r.content.decode('utf-8')
i10 = lessons_body.find('Задание 10 (орфография, приставки)')
seg = lessons_body[max(0, i10 - 1300):i10]
check('lesson-card--active' in seg, 'карточка урока 10 стала активной после сдачи')

print('3. Провал: 4 ошибки -> не сдан, рекомендации')
u2 = User.objects.create_user(username='pupil2', email='p2@example.com',
                              password='Zk9mQ2vLp7xR')
prof2, _ = UserProfile.objects.get_or_create(user=u2)
prof2.trial_until = timezone.now() + timedelta(days=5)
prof2.save()
c2 = Client()
c2.force_login(u2)
r = c2.get('/ege/checkpoint/9/')
correct2 = c2.session.get('checkpoint_9_correct', {})
answers2 = {}
for t in ('1', '2', '3', '5', '6', '7'):
    ca = correct2.get(t)
    answers2[t] = ca[0] if isinstance(ca, list) else ca
# ломаем 4 задания
answers2['1'] = 'zzzz'
answers2['2'] = 'zzzz'
answers2['5'] = 'zzzz'
answers2['6'] = 'zzzz'
answers2['4'] = ' '.join(correct2.get('4', []))
m82 = c2.session.get('checkpoint_9_task8_matches', {})
for letter, val in m82.items():
    answers2[f'8_{letter}'] = val
r = c2.post('/ege/checkpoint/9/', data=json.dumps({'answers': answers2}),
            content_type='application/json')
res2 = r.json()
a2 = CheckpointAttempt.objects.filter(user=u2).first()
check(a2 and not a2.passed, 'попытка не сдана')
check(a2.error_count == 4, f'error_count=4 (факт: {a2.error_count})')
r = c2.get(res2['result_url'])
vb = r.content.decode('utf-8')
check('Пока не сдан' in vb, 'вердикт: не сдан')
check('Что повторить перед пересдачей' in vb, 'блок рекомендаций на месте')
r = c2.get('/ege/lessons/')
seg = r.content.decode('utf-8')
i10 = seg.find('Задание 10 (орфография, приставки)')
check('lesson-card--locked' in seg[max(0, i10 - 1300):i10],
      'урок 10 остался закрытым после провала')

print('4. Статистика: карточка рубежных тестов')
r = c2.get('/statistic/')
sb = r.content.decode('utf-8')
check('Рубежные тесты: сдано' in sb, 'карточка на странице статистики')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ЧЕКПОИНТА ПРОЙДЕНЫ')
