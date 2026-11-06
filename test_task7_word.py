# -*- coding: utf-8 -*-
"""Тест формата задания 7 по ЕГЭ: эталон — только исправленное слово.
Пара фраз с пустым explanation (кейс «ЛОПНУТАЯ шина») даёт эталон «лопнувшая»,
а не всё словосочетание; тренажёр принимает слово и отвергает всю фразу;
эталон рубежа и диагностики — тоже слово.
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_task7_word.py
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

from main.models import CorrectionExercise, UserProfile
from main.views import _correction_reference

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

print('1. Вывод слова из пары фраз')
check(CorrectionExercise.extract_correct_word('ЛОПНУТАЯ шина',
                                              'лопнувшая шина') == 'лопнувшая',
      'кейс владельца: ЛОПНУТАЯ шина -> лопнувшая')
check(CorrectionExercise.extract_correct_word('золочёные КУПОЛЫ',
                                              'золочёные КУПОЛА') == 'купола',
      'куполы -> купола')
check(CorrectionExercise.extract_correct_word('ЕЗЖАЙ вперёд',
                                              'ПОЕЗЖАЙ вперёд') == 'поезжай',
      'езжай -> поезжай')
check(CorrectionExercise.extract_correct_word('сожгет', 'сожжёт') == 'сожжёт',
      'одиночные слова работают как раньше')
check(CorrectionExercise.extract_correct_word('а б', 'в г д') == '',
      'разное число токенов -> пусто (fallback)')

ROWS = [
    ('ЛОПНУТАЯ шина', 'лопнувшая шина', ''),          # пустой explanation!
    ('золочёные КУПОЛЫ', 'золочёные КУПОЛА', 'КУПОЛА'),
    ('ЕЗЖАЙ вперёд', 'ПОЕЗЖАЙ вперёд', 'ПОЕЗЖАЙ'),
    ('опытные ДИРЕКТОРЫ', 'опытные ДИРЕКТОРА', 'ДИРЕКТОРА'),
    ('более СТРОЖЕ', 'более СТРОГО', 'СТРОГО'),
]
for inc, cor, exp in ROWS:
    CorrectionExercise.objects.create(incorrect_text=inc, correct_text=cor,
                                      explanation=exp, is_active=True,
                                      exercise_id='711')

print('2. Тренажёр: эталон и проверка')
c = Client()
c.force_login(u)
target = None
for _ in range(40):
    r = c.post('/api/generate-correction-test/')
    sess = c.session.get('correction_test', {})
    if sess.get('incorrect_word', '').startswith('лопнутая'):
        target = sess
        break
check(target is not None, 'поймали вариант с «ЛОПНУТАЯ шина»')
if target:
    check(target['correct_answer'] == 'лопнувшая',
          f"эталон в сессии — слово (факт: {target['correct_answer']!r})")
    r = c.post('/api/check-correction/', data=json.dumps({'answer': 'лопнувшая'}),
               content_type='application/json')
    check(r.json()['is_correct'] is True, 'ответ словом принят')
    r = c.post('/api/check-correction/',
               data=json.dumps({'answer': 'лопнувшая шина'}),
               content_type='application/json')
    check(r.json()['is_correct'] is False, 'вся фраза больше не принимается')

print('3. Рубеж: эталон 7 — слово')
r = c.get('/ege/checkpoint/9-1/')
snap = c.session['checkpoint_91']['snapshot']['7']
phrases = snap['phrases']
wrong_phrase = next(p for p in phrases
                    if not CorrectionExercise.objects.filter(
                        correct_text=p).exists())
row = CorrectionExercise.objects.get(incorrect_text=wrong_phrase)
check(snap['correct'] == _correction_reference(row.incorrect_text,
                                               row.correct_text,
                                               row.explanation),
      'эталон рубежа совпадает с выводом слова')
check(' ' not in snap['correct'],
      f"в эталоне рубежа нет пробелов (факт: {snap['correct']!r})")

print('4. Fallback: explanation для невыделяемых пар')
check(_correction_reference('а б', 'в г д', 'ВВЕРХ') == 'вверх',
      'невыделяемая пара -> explanation')
check(_correction_reference('а б', 'в г д', '') == 'в г д',
      'нет explanation -> вся фраза')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ФОРМАТА ЗАДАНИЯ 7 ПРОЙДЕНЫ')
