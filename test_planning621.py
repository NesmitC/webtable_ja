# -*- coding: utf-8 -*-
"""Кнопка 62.1 в планингах: 5 предложений построчно в случайном порядке
(как у орфограмм задания 13), регресс форматов 21 и 1.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_planning621.py
"""
import json
import os
import re
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main.models import Orthogram, OrthogramExample

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
u = User.objects.create_user(username='p', email='p@example.com',
                             password='Zk9mQ2vLp7xR')
Orthogram.objects.create(id='621', name='Наречия слитно (запомн.)',
                         letters='/,|,-')
for oid in ('64', '65', '67', '68', '69', '70'):
    Orthogram.objects.create(id=oid, name=f'орф {oid}', letters='/,|,-')
Orthogram.objects.create(id='21', name='НЕ с глаголами', letters='е,и')
Orthogram.objects.create(id='1', name='Проверяемые гласные', letters='а,о,е,и')
WORDS_621 = [
    ('на/бок', 'на*621*бок'), ('на/долго', 'на*621*долго'),
    ('в/миг', 'в*621*миг'), ('без\\устали', 'без*621*устали'),
    ('на/утро', 'на*621*утро'), ('в/последствии', 'в*621*последствии'),
    ('на/перерез', 'на*621*перерез'), ('до/суха', 'до*621*суха'),
]
for text, masked in WORDS_621:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='621', grades='7',
                                    is_active=True)
for i in range(20):
    OrthogramExample.objects.create(text=f'слово{i}', masked_word=f'сл*1*во{i}',
                                    orthogram_id='1', grades='5', is_active=True)
for i in range(4):
    OrthogramExample.objects.create(text=f'не/слит{i}', masked_word=f'не*21*слит{i}',
                                    orthogram_id='21', grades='5', is_active=True,
                                    explanation='/')
for i in range(4):
    OrthogramExample.objects.create(text=f'не\\разд{i}', masked_word=f'не*21*разд{i}',
                                    orthogram_id='21', grades='5', is_active=True,
                                    explanation='|')

c = Client()
c.force_login(u)


def gen(oid):
    r = c.post('/api/generate-exercise/', data=json.dumps({'orthogram_ids': [oid]}),
               content_type='application/json', HTTP_HOST='localhost')
    return r.json().get('html', '')


def lines_of(html):
    return re.findall(r'class="practice-line[^"]*">(.*?)</p>', html, re.S)


print('1. Кнопка 62.1: пять предложений построчно')
html = gen('621')
lines = lines_of(html)
check(len(lines) == 5, f'5 строк (факт: {len(lines)})')
check('*621*' in html, 'маски 621 на месте')
first = [re.sub(r'<[^>]+>', '', x).strip() for x in lines]
html2 = gen('621')
second = [re.sub(r'<[^>]+>', '', x).strip() for x in lines_of(html2)]
check(first != second, 'порядок случайный между вызовами')
sess = c.session['current_exercise']
check(len(sess['correct_letters']) == 5, 'в сессии 5 эталонных букв')
check(set(sess['correct_letters']) <= {'/', '|', '-'},
      f'эталоны в алфавите вариантов /,|,- (факт: {set(sess["correct_letters"])})')
check('\\' not in sess['correct_letters'],
      'маркер "\\" нормализован в "|"')

print('2. Кнопки 64, 65, 67, 68: тоже 5 строк построчно')
WORDS_64 = [('в/следствие', 'в*64*следствие'), ('на/подобие', 'на*64*подобие'),
            ('в/роде', 'в*64*роде'), ('на/счет', 'на*64*счет'),
            ('в/виду', 'в*64*виду'), ('в/след', 'в*64*след')]
WORDS_65 = [('в/течение', 'в*65*течение'), ('в\\продолжение', 'в*65*продолжение'),
            ('в/заключение', 'в*65*заключение'), ('в\\отношении', 'в*65*отношении'),
            ('в/силу', 'в*65*силу')]
WORDS_67 = [('так/же', 'так*67*же'), ('то\\же', 'то*67*же'),
            ('что/бы', 'что*67*бы'), ('так\\же2', 'так*67*же2'),
            ('то/же2', 'то*67*же2')]
WORDS_68 = [('какая\\бы', 'какая*68*бы'), ('где\\ли', 'где*68*ли'),
            ('вот\\же', 'вот*68*же'), ('куда\\бы2', 'куда*68*бы2'),
            ('так\\ли', 'так*68*ли')]
for words, oid in ((WORDS_64, '64'), (WORDS_65, '65'), (WORDS_67, '67'),
                   (WORDS_68, '68')):
    for text, masked in words:
        OrthogramExample.objects.create(text=text, masked_word=masked,
                                        orthogram_id=oid, grades='7',
                                        is_active=True)
# 69 и 70: маски съедают дефис, эталон — буква варианта "-"
for text, masked in [('дай-ка', 'дай*69*ка'), ('ну-ка', 'ну*69*ка'),
                     ('смотри-ка', 'смотри*69*ка')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='69', grades='7',
                                    is_active=True)
for text, masked in [('да-да', 'да*70*да'), ('ха-ха', 'ха*70*ха'),
                     ('ай-ай', 'ай*70*ай')]:
    OrthogramExample.objects.create(text=text, masked_word=masked,
                                    orthogram_id='70', grades='7',
                                    is_active=True)

for oid in ('64', '65', '67', '68'):
    html = gen(oid)
    n = len(lines_of(html))
    check(n == 5, f'кнопка {oid}: 5 строк (факт: {n})')
    check(f'*{oid}*' in html, f'кнопка {oid}: маски на месте')

print('3. Аудит 69 и 70: эталон — дефис из алфавита вариантов')
for oid in ('69', '70'):
    gen(oid)
    letters = c.session['current_exercise']['correct_letters']
    check(set(letters) == {'-'},
          f'кнопка {oid}: эталоны "-" (факт: {set(letters)})')

print('4. Регресс форматов')
check(len(lines_of(gen('21'))) == 5, 'кнопка 21: по-прежнему 5 строк')
html1 = gen('1')
check(len(lines_of(html1)) == 1 and html1.count('*1*') == 16,
      'обычная орфограмма: 16 слов одной строкой через запятую')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ КНОПКИ 62.1 ПРОЙДЕНЫ')
