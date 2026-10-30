# -*- coding: utf-8 -*-
"""Тест рубежного теста cp91 (задания 4–9.1, открывает урок 9.2).
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint91.py
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

from main.models import (CheckpointAttempt, CorrectionExercise, Orthogram,
                         OrthogramExample, OrthoepyWord, TaskPaponim, UserProfile,
                         WordOk)

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


# ===== Контент БД =====
# Задание 4: орфоэпия (пары вариантов леммы)
for word, lemma, ok in [
        ('звонИт', 'звонить', True), ('тОрты', 'торт', True),
        ('бАнты', 'бант', True), ('дОговор', 'договор', False),
        ('каталОг', 'каталог', False), ('свЁкла', 'свекла', False)]:
    OrthoepyWord.objects.create(word=word, lemma=lemma, is_correct=ok,
                                is_active=True)

# Задание 5: паронимы
TaskPaponim.objects.create(text='Он решил **одеть** очки и вышел на улицу.',
                           correct_word='надеть', root='дет',
                           is_active=True, is_for_quiz=True)
for sent, root in [
        ('Это было **гарантийное** обслуживание.', 'гарант'),
        ('Она **адресовала** письмо подруге.', 'адрес'),
        ('Мы **оплатили** проезд.', 'оплат'),
        ('**Дипломатичный** ответ устроил всех.', 'диплом')]:
    TaskPaponim.objects.create(text=sent, correct_word='', root=root,
                               is_active=True, is_for_quiz=True)

# Задание 6: лексика
WordOk.objects.create(text='Мы **оплатили** за проезд.', task_type='6100',
                      correct_variants='за, заплатили', is_active=True)

# Задание 7: грамматика (генератору нужно >= 5 упражнений)
for i, (bad, good) in enumerate([
        ('сожгет', 'сожжёт'), ('чулков', 'чулок'), ('замзрнул', 'замёрз'),
        ('ихний', 'их'), ('ездию', 'езжу')]):
    CorrectionExercise.objects.create(incorrect_text=bad, correct_text=good,
                                      is_active=True, exercise_id=f'71{i}')

# Задание 9.1: орфограмма 1 (проверяемые ударением)
Orthogram.objects.create(id=1, name='Проверяемая безударная гласная',
                         letters='а,о,е,и,я,у,ю')
for text, masked in [('вода', 'в*1*да'), ('гора', 'г*1*ра'), ('трава', 'тр*1*ва'),
                     ('воды', 'в*1*ды'), ('горы', 'г*1*ры'), ('травы', 'тр*1*вы'),
                     ('водой', 'в*1*дой'), ('горой', 'г*1*рой')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id=1, grades='10,11',
                                    is_active=True)

u = make_user('pupil91')
c = Client()
c.force_login(u)

print('1. GET: состав рубежа 4–9.1')
r = c.get('/ege/checkpoint/9-1/')
check(r.status_code == 200, f'GET /ege/checkpoint/9-1/ -> {r.status_code}')
body = r.content.decode('utf-8')
check('Рубежный тест: задания 4–9.1' in body, 'заголовок рубежа 4–9.1')
check('Прочитайте текст' not in body, 'заданий 1-3 (микротекст) нет')
check('9.1. Выберите правильную букву' in body, 'блок 9.1 с подписью 9.1')
check('открылся урок 9.2' in body, 'в шапке обещание открыть урок 9.2')
check('не более 2 ошибок' in body, 'допуск 2 ошибки для шести заданий')
sess = c.session['checkpoint_91']
check('answers_1_3' not in sess, 'сессия: эталонов 1-3 нет')
check(bool(sess.get('answer_5')), 'сессия: эталон 5')
check(len(sess.get('task9_correct', [])) == 9,
      f'сессия: 9 букв задания 9.1 (3 строки по 3) факт {len(sess.get("task9_correct", []))}')
check('task9_correct' not in c.session.get('checkpoint_9', {}),
      'сессия старого рубежа не тронута')

print('2. Всё верно -> сдан, урок 9.2 открыт')
answers = {}
for k in ('4', '7'):
    if f'answer_{k}' in sess:
        answers[k] = sess[f'answer_{k}']
if 'answer_5' in sess:
    answers['5'] = 'НАДЕТЬ'
if 'answer_6' in sess:
    answers['6'] = sess['answer_6'].split(',')[0].strip()
for i, letter in enumerate(sess['task9_correct'], 1):
    answers[f'9-{i}'] = letter
r = c.post('/ege/checkpoint/9-1/', data=json.dumps({'answers': answers}),
           content_type='application/json')
check(r.status_code == 200, f'POST -> {r.status_code}')
res = r.json()
a = CheckpointAttempt.objects.filter(checkpoint_code='cp91').first()
check(a is not None and a.passed, 'попытка cp91 сохранена и passed=True')
scored = len([k for k in ('4', '5', '6', '7') if f'answer_{k}' in sess]) + 1
check(a.total_tasks == scored and a.error_count == 0,
      f'все сгенерированные задания ({scored}: 4,5,6,7 по наличию + 9) верны: '
      f'факт {a.total_tasks}, ошибок {a.error_count}')
check(res['passed'] is True, 'в ответе passed=True')
vb = c.get(res['result_url']).content.decode('utf-8')
check('Рубеж сдан' in vb and 'Урок 9.2 открыт' in vb,
      'вердикт: сдан, откроется урок 9.2')
lb = c.get('/ege/lessons/').content.decode('utf-8')
i92 = lb.find('Задание 9.2 (корни: гласные, НЕПРОВЕРЯЕМЫЕ ударениями)')
check('lesson-card--active' in lb[max(0, i92 - 900):i92],
      'карточка урока 9.2 активна после сдачи')
check('Сдан: урок 9.2 открыт' in lb, 'статус карточки рубежа: сдан')

print('3. Провал: урок 9.2 остаётся закрытым')
u2 = make_user('pupil91b')
c2 = Client()
c2.force_login(u2)
c2.get('/ege/checkpoint/9-1/')
r2 = c2.post('/ege/checkpoint/9-1/', data=json.dumps({'answers': {
    '4': ['чушь'], '5': 'чушь', '6': 'чушь', '7': 'чушь',
    '9-1': 'я', '9-2': 'я', '9-3': 'я', '9-4': 'я', '9-5': 'я',
    '9-6': 'я', '9-7': 'я', '9-8': 'я', '9-9': 'я',
}}), content_type='application/json')
a2 = CheckpointAttempt.objects.filter(user=u2, checkpoint_code='cp91').first()
check(a2 and not a2.passed, 'попытка не сдана')
check(a2.total_tasks >= 4 and a2.error_count == a2.total_tasks,
      f'все задания неверны: {a2.error_count} из {a2.total_tasks}')
lb2 = c2.get('/ege/lessons/').content.decode('utf-8')
i92b = lb2.find('Задание 9.2 (корни: гласные, НЕПРОВЕРЯЕМЫЕ ударениями)')
check('lesson-card--locked' in lb2[max(0, i92b - 900):i92b],
      'урок 9.2 закрыт после провала')
vb2 = c2.get(r2.json()['result_url']).content.decode('utf-8')
check('Что повторить' in vb2 and 'proveryaemye-glasnye' in vb2,
      'рекомендация по 9.1 ведёт в раздел проверяемых гласных')

print('4. Строки 9.1 — только орфограмма 1')
lines = c2.session['checkpoint_91'].get('snapshot', {}).get('9', {}).get('lines', [])
check(bool(lines), 'снимок строк 9.1 в сессии')
check(all('*29*' not in ln and '*24*' not in ln for ln in lines),
      'в строках нет масок других орфограмм')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ РУБЕЖА 4–9.1 ПРОЙДЕНЫ')
