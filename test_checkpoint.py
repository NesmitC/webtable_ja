# -*- coding: utf-8 -*-
"""Тест рубежного теста cp9 v4: контент из БД (как текущая/контрольная
диагностика), ошибки по заданиям, подсветка, ротация паронимов, замок урока 10.
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

from main.models import (CheckpointAttempt, CorrectionExercise, QuestionOption,
                         TaskPaponim, TextAnalysisTask, TextQuestion,
                         UserProfile, WordOk)

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


# ===== Контент БД (те же источники, что у текущей диагностики) =====
task_text = TextAnalysisTask.objects.create(
    title='Микротест', task_type='1_3', is_active=True,
    text_content='Язык — это история народа. Язык — это культура народа.')
q1 = TextQuestion.objects.create(
    task=task_text, question_number=1, question_type='missing_word',
    question_text='1. Вставьте пропущенное слово.', correct_answer='история/летопись')
q2 = TextQuestion.objects.create(
    task=task_text, question_number=2, question_type='multiple_choice',
    question_text='2. Укажите верные утверждения.', correct_answer='13')
q3 = TextQuestion.objects.create(
    task=task_text, question_number=3, question_type='multiple_choice',
    question_text='3. Укажите верные утверждения.', correct_answer='12')
for num, txt in [(1, 'первое'), (2, 'второе'), (3, 'третье')]:
    QuestionOption.objects.create(question=q2, option_number=num, option_text=txt)
    QuestionOption.objects.create(question=q3, option_number=num, option_text=txt)

TaskPaponim.objects.create(text='Он решил **одеть** очки и вышел на улицу.',
                           correct_word='надеть', root='дет',
                           is_active=True, is_for_quiz=True)
for sent, root in [
        ('Это было **гарантийное** обслуживание.', 'гарант'),
        ('Она **адресовала** письмо подруге.', 'адрес'),
        ('Мы **оплатили** проезд.', 'оплат'),
        ('**Дипломатичный** ответ устроил всех.', 'диплом'),
]:
    TaskPaponim.objects.create(text=sent, correct_word='', root=root,
                               is_active=True, is_for_quiz=True)

WordOk.objects.create(text='Мы **оплатили** за проезд.', task_type='6100',
                      correct_variants='за, заплатили', is_active=True)

for i, (bad, good) in enumerate([
        ('сожгет', 'сожжёт'), ('чулков', 'чулок'), ('замзрнул', 'замёрз'),
        ('ихний', 'их'), ('едь', 'поезжай')]):
    CorrectionExercise.objects.create(incorrect_text=bad, correct_text=good,
                                      is_active=True, exercise_id=f'71{i}')

u = make_user('pupil')
c = Client()
c.force_login(u)

print('1. GET: контент собирается из БД')
r = c.get('/ege/checkpoint/9/')
check(r.status_code == 200, f'GET /ege/checkpoint/9/ -> {r.status_code}')
body = r.content.decode('utf-8')
check('Язык — это история народа' in body, 'задания 1-3: текст из БД')
check('data-question="1"' in body, 'задание 1: инпут из БД')
check('<u>одеть</u>' in body, 'задание 5: пароним из БД с выделенным словом')
check('оплатили' in body, 'задание 6: лексика из БД (WordOk)')
check('сожжёт' in body or 'чулок' in body or 'поезжай' in body,
      'задание 7: грамматика из БД (CorrectionExercise)')
check('check-task-submit' in body, 'кнопка в едином стиле check-task-submit')
check('task9-letter-groups' not in body,
      'без пула задания 9 скрипт-теги не рендерятся (деградация мягкая)')

sess = c.session['checkpoint_9']
check('answers_1_3' in sess and sess['answers_1_3'].get('1') == 'история/летопись',
      'сессия: эталон заданий 1-3')
check(sess.get('answer_5') == 'надеть', "сессия: эталон 5 = 'надеть'")
check(bool(sess.get('answer_6')), 'сессия: эталон 6')
check(bool(sess.get('answer_7')), 'сессия: эталон 7')

print('2. Всё верно -> сдан, урок 10 открыт')
answers = {
    '1': 'история',
    '2': ['1', '3'],
    '3': ['1', '2'],
    '5': 'НАДЕТЬ',
    '6': 'за',
    '7': sess['answer_7'],
}
r = c.post('/ege/checkpoint/9/', data=json.dumps({'answers': answers}),
           content_type='application/json')
check(r.status_code == 200, f'POST -> {r.status_code}')
res = r.json()
a = CheckpointAttempt.objects.first()
check(a is not None and a.passed, 'попытка сохранена и passed=True')
check(a.total_tasks == 6 and a.correct_count == 6 and a.error_count == 0,
      f'6 заданий из БД: 6/6, ошибок 0 (факт: {a.correct_count}/{a.total_tasks}, '
      f'ошибок {a.error_count})')
check(res['results']['1']['is_correct'] and res['results']['5']['is_correct'],
      'results для подсветки: 1 и 5 верны (регистр не важен)')
r = c.get(res['result_url'])
vb = r.content.decode('utf-8')
check('Рубеж сдан' in vb and 'из 6' in vb, 'вердикт: сдан, знаменатель динамический')

r = c.get('/ege/lessons/')
lb = r.content.decode('utf-8')
i10 = lb.find('Задание 10 (орфография, приставки)')
check('lesson-card--active' in lb[max(0, i10 - 1300):i10],
      'карточка урока 10 активна после сдачи')

print('3. Всё неверно -> ошибка за каждое задание, не сдан')
u2 = make_user('pupil2')
c2 = Client()
c2.force_login(u2)
c2.get('/ege/checkpoint/9/')
r = c2.post('/ege/checkpoint/9/', data=json.dumps({'answers': {
    '1': 'чушь', '2': ['2'], '3': ['3'], '5': 'чушь', '6': 'чушь', '7': 'чушь',
}}), content_type='application/json')
res2 = r.json()
a2 = CheckpointAttempt.objects.filter(user=u2).first()
check(a2 and not a2.passed, 'попытка не сдана')
check(a2.error_count == 6 and a2.correct_count == 0,
      f'6 ошибок = 6 неверных заданий (факт: {a2.error_count})')
check(res2['error_count'] == 6 and res2['passed'] is False,
      'в ответе error_count/passed для вердикт-ссылки')
r = c2.get(res2['result_url'])
vb2 = r.content.decode('utf-8')
check('Пока не сдан' in vb2 and 'Что повторить' in vb2,
      'вердикт: не сдан + рекомендации')
check('/paponim_trening/' in vb2, 'рекомендация задания 5 ведёт в словник паронимов')
r = c2.get('/ege/lessons/')
lb2 = r.content.decode('utf-8')
i10 = lb2.find('Задание 10 (орфография, приставки)')
check('lesson-card--locked' in lb2[max(0, i10 - 1300):i10],
      'урок 10 закрыт после провала')

print('4. Ротация паронимов и случайность сборки')
s2a = c2.session['checkpoint_9']
u3 = make_user('pupil3')
c3 = Client()
c3.force_login(u3)
c3.get('/ege/checkpoint/9/')
c3.get('/ege/checkpoint/9/')
check(bool(c3.session['checkpoint_9'].get('answer_5')),
      'две генерации подряд стабильны (задание 5 на месте)')

print('5. Статистика: карточка и таблица прохождений')
sb = c2.get('/statistic/').content.decode('utf-8')
check('Рубежные тесты: сдано' in sb, 'карточка на странице статистики')
check('История прохождений рубежей' in sb, 'таблица прохождений на месте')
check('/ 6' in sb, 'в таблице динамический знаменатель (6)')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ЧЕКПОИНТА ПРОЙДЕНЫ')
