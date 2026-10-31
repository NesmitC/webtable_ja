# -*- coding: utf-8 -*-
"""Персонализация рубежей: задания 4 и 9.1 тянут слова с ошибками ученика.
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint_personal.py
"""
import os
import re
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

from main.models import (CorrectionExercise, OrthoepyWord, OrthoepyWordStat,
                         Orthogram, OrthogramExample, TaskPaponim, Task9WordStat,
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


# ===== Контент БД =====
ortho_words = {}
for word, lemma, ok in [
        ('звонИт', 'звонить', True), ('тОрты', 'торт', True),
        ('бАнты', 'бант', True), ('дОговор', 'договор', False),
        ('каталОг', 'каталог', False), ('свЁкла', 'свекла', False)]:
    ortho_words[word] = OrthoepyWord.objects.create(
        word=word, lemma=lemma, is_correct=ok, is_active=True)

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
WordOk.objects.create(text='Мы **оплатили** за проезд.', task_type='6100',
                      correct_variants='за, заплатили', is_active=True)
for i, (bad, good) in enumerate([
        ('сожгет', 'сожжёт'), ('чулков', 'чулок'), ('замзрнул', 'замёрз'),
        ('ихний', 'их'), ('ездию', 'езжу')]):
    CorrectionExercise.objects.create(incorrect_text=bad, correct_text=good,
                                      is_active=True, exercise_id=f'71{i}')

Orthogram.objects.create(id=1, name='Проверяемая безударная гласная',
                         letters='а,о,е,и,я,у,ю')
examples = {}
for text, masked in [('вода', 'в*1*да'), ('воды', 'в*1*ды'), ('водой', 'в*1*дой'),
                     ('гора', 'г*1*ра'), ('горы', 'г*1*ры'), ('горой', 'г*1*рой'),
                     ('трава', 'тр*1*ва'), ('травы', 'тр*1*вы'), ('травой', 'тр*1*вой'),
                     ('река', 'р*1*ка'), ('реки', 'р*1*ки'), ('рекой', 'р*1*кой'),
                     ('земля', 'з*1*мля'), ('земли', 'з*1*мли'), ('землёй', 'з*1*млёй'),
                     ('сосна', 'с*1*сна')]:
    examples[masked] = OrthogramExample.objects.create(
        text=text, masked_word=masked, orthogram_id=1, grades='10,11',
        is_active=True)

PREFER9 = ['в*1*да', 'в*1*ды', 'в*1*дой']
PREFER4 = 'звонИт'

u = make_user('personal')
OrthoepyWordStat.objects.create(user=u, word_id=ortho_words[PREFER4].id,
                                word=PREFER4, errors=2, attempts=3,
                                in_correction=True)
for masked in PREFER9:
    Task9WordStat.objects.create(user=u, orthogram_id='1', range_code='A-O',
                                 word=masked, correct_letter='о', errors=1,
                                 attempts=2, in_correction=True)

c = Client()
c.force_login(u)

print('1. Задание 4: слово с ошибкой попадает в варианты')
for run in range(1, 4):
    c.get('/ege/checkpoint/9-1/')
    variants = c.session['checkpoint_91'].get('variants_4', [])
    texts = [v.get('word') if isinstance(v, dict) else v for v in variants]
    check(PREFER4 in texts, f'попытка {run}: «{PREFER4}» среди вариантов 4')

print('2. Задание 9.1: слова с ошибками — в строках, без повторов')
for run in range(1, 4):
    c.get('/ege/checkpoint/9-1/')
    lines = c.session['checkpoint_91']['snapshot']['9']['lines']
    blob = ' '.join(ln if isinstance(ln, str) else ln['display_line']
                    for ln in lines)
    for masked in PREFER9:
        stem = masked.split('*1*')
        pat = re.escape(stem[0]) + r'\*9-\d+\*' + re.escape(stem[1])
        hits = len(re.findall(pat, blob))
        check(hits == 1,
              f'попытка {run}: «{masked}» в строках ровно 1 раз (факт {hits})')

print('3. Нет ошибок в статистике — генерация случайная и живая')
u2 = make_user('clean')
c2 = Client()
c2.force_login(u2)
r = c2.get('/ege/checkpoint/9-1/')
check(r.status_code == 200, f'GET -> {r.status_code}')
check(len(c2.session['checkpoint_91']['task9_correct']) == 15,
      '15 букв задания 9.1 на чистой статистике')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ПЕРСОНАЛИЗАЦИЯ РУБЕЖЕЙ РАБОТАЕТ')
