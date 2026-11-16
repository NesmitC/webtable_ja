# -*- coding: utf-8 -*-
"""Рубежи cp10/cp12/cp13/cp14: алфавит ответов покрывает все буквы пула.
Жалобы учеников: пророссийский (буква 'о', орф. 10) и парт/ячейка ('/',
орф. 6) попадали в строки задания 10, но кнопок 'о' и '/' не было;
березонька ('о', орф. 482) — то же в задании 11. Плюс регресс: генератор
диагностики generate_task10_lines не подменяет эталоны в fallback.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_cp_letters.py
"""
import os
import random
import re

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

import main.views as views
from main.models import Orthogram, OrthogramExample

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
pupil = User.objects.create_user('cp_letters_pupil', password='x')

ORTHS = {
    '10': 'Одновариантные приставки', '11': 'Приставки на -З и -С',
    '28': 'Ы-И после приставок', '29': 'ПРЕ- и ПРИ-',
    '6': 'Разделительные Ъ и Ь',
    '481': 'Суффиксы -ЕЦ-/-ИЦ-', '482': 'Суффиксы -ЕНК-/-ИНК-/-ОНЬК-',
    '483': 'Суффиксы -ЛИВ-/-ЧИВ-', '484': 'Суффиксы -ЧАТ-/-АТ-',
    '485': '-ЕТЬ-/-ИТЬ-',
    '21': 'НЕ с глаголами', '36': 'НЕ с прилагательными',
    '54': 'НЕ с причастиями',
}
for oid, name in ORTHS.items():
    Orthogram.objects.create(id=oid, name=name, rule='-')

# (orth_id, text, masked_word) — маска заменяет РОВНО один символ
WORDS = [
    ('10', 'прообраз', 'пр*10*образ'),
    ('10', 'пророссийский', 'пр*10*российский'),
    ('10', 'праязык', 'пр*10*язык'),
    ('10', 'подпись', 'по*10*пись'),
    ('10', 'отдай', 'о*10*дай'),
    ('11', 'безвкусный', 'бе*11*вкусный'),
    ('11', 'расписать', 'ра*11*писать'),
    ('28', 'предыстория', 'пред*28*стория'),
    ('28', 'взимать', 'вз*28*мать'),
    ('29', 'приехать', 'пр*29*ехать'),
    ('29', 'превратить', 'пр*29*вратить'),
    ('6', 'объезд', 'об*6*езд'),
    ('6', 'вьюга', 'в*6*юга'),
    ('6', 'парт/ячейка', 'парт*6*ячейка'),
    ('6', 'ин/яз', 'ин*6*яз'),
    ('481', 'ситец', 'сит*481*ц'),
    ('482', 'березонька', 'берез*482*нька'),
    ('482', 'лисонька', 'лис*482*нька'),
    ('483', 'дождливый', 'дождл*483*вый'),
    ('484', 'зубчатый', 'зубч*484*тый'),
    ('485', 'видеть', 'вид*485*ть'),
    ('485', 'клеить', 'кле*485*ть'),
    ('21', 'НЕ\\ПОЙДЁТ', 'НЕ*21*ПОЙДЁТ'),
    ('54', 'НЕ\\ ЗНАЧАЩИЕ', 'НЕ*54*ЗНАЧАЩИЕ'),
    ('36', 'НЕ/ПРИВЫЧНЫЕ', 'НЕ*36*ПРИВЫЧНЫЕ'),
]
for oid, text, masked in WORDS:
    OrthogramExample.objects.create(orthogram_id=oid, text=text,
                                    masked_word=masked)

print('=== Задание 10 рубежа: алфавит покрывает буквы пула ===')
random.seed(7)
res = views._cp_mixed_lines(pupil, ('10',), blocks=3)
lines = res['lines']
check(len(lines) == 15, f'15 строк (3 блока x 5), получено {len(lines)}')
bad = [(ln['display_line'], l) for ln in lines
       for l in ln['expected_letters'] if l not in ln['available_letters']]
check(not bad, f'все эталоны есть в алфавите строки (нарушений: {len(bad)})')
for b in bad[:5]:
    print('     ', b)
all_letters = {l for ln in lines for l in ln['expected_letters']}
for need in ('о', 'а', 'д', 'т', '/', 'з', 'с', 'ы', 'и', 'е', 'ъ', 'ь'):
    check(need in all_letters, f'буква {need!r} встречается в строках')
check('/' in res['subgroup_letters']['b10-1'],
    "алфавит блока содержит '/' (слитно)")
check('о' in res['subgroup_letters']['b10-1'],
    "алфавит блока содержит 'о' (одновариантные приставки)")

print('=== Задание 11 рубежа: -ОНЬК- (буква о) ===')
random.seed(7)
res11 = views._cp_mixed_lines(pupil, ('11',), blocks=3)
bad11 = [(ln['display_line'], l) for ln in res11['lines']
         for l in ln['expected_letters'] if l not in ln['available_letters']]
check(not bad11, f'все эталоны в алфавите (нарушений: {len(bad11)})')
check('о' in res11['subgroup_letters']['b11-1'],
    "алфавит задания 11 содержит 'о'")
check(any(l == 'о' for ln in res11['lines'] for l in ln['expected_letters']),
    'березонька/лисонька попали в строки')

print('=== Задание 13 рубежа: маркер раздельности с пробелом ===')
random.seed(7)
res13 = views._cp_mixed_lines(pupil, ('13',), blocks=3)
letters13 = {l for ln in res13['lines'] for l in ln['expected_letters']}
check(letters13 <= {'|', '/'}, f'только маркеры | и /, got {letters13}')
check('|' in letters13 and '/' in letters13, 'оба маркера встречаются')
check(any('ЗНАЧАЩИЕ' in ln['display_line'] for ln in res13['lines']),
    "НЕ\\ ЗНАЧАЩИЕ (маркер '\\ ') не выпал из пула")

print('=== Диагностика generate_task10_lines: эталоны не подменяются ===')
# В каждой подгруппе ни одна буква не набирает 3 слов,
# значит uniform-строки идут через fallback (раньше он подменял буквы)
OrthogramExample.objects.create(orthogram_id='10', text='надпилить',
                                masked_word='на*10*пилить')
OrthogramExample.objects.create(orthogram_id='10', text='отдел',
                                masked_word='о*10*дел')
texts = {t for _, t, _ in WORDS} | {'надпилить', 'отдел'}
recon_bad = []
for seed in range(1, 31):
    random.seed(seed)
    data = views.generate_task10_lines()
    check_ok = True
    for ln in data['lines']:
        for part in ln['display_line'].split(', '):
            m = re.search(r'\*(10_\d+-\d+)\*', part)
            if not m:
                recon_bad.append((seed, part, 'нет маски'))
                continue
            letter = data['expected_map'][m.group(1)]
            rebuilt = part[:m.start()] + letter + part[m.end():]
            if rebuilt not in texts:
                recon_bad.append((seed, part, f'эталон {letter!r} -> {rebuilt!r}'))
    if len(data['lines']) != 5:
        recon_bad.append((seed, 'строк != 5', ''))
check(not recon_bad,
      f'30 генераций: маска+эталон всегда дают исходное слово '
      f'(нарушений: {len(recon_bad)})')
for b in recon_bad[:5]:
    print('     ', b)

print()
if fails:
    print(f'ПРОВАЛЕНО ПРОВЕРОК: {len(fails)}')
    raise SystemExit(1)
print('ВСЕ ПРОВЕРКИ ЗЕЛЁНЫЕ')