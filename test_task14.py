# -*- coding: utf-8 -*-
"""Задание 14 (орф. 1400) на /ege/trainers/: генерация и проверка.
Регресс бага «раздельное '|' всегда красное»: explanation владельца с '\\'
и скобки в masked_word ломали позиционный fallback.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_task14.py
"""
import json
import os

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
from main.views import (extract_from_text_and_masks, generate_task14_lines,
                        parse_task14_markers)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
u = User.objects.create_user(username='t14', email='t14@example.com',
                             password='Zk9mQ2vLp7xR')
Orthogram.objects.create(id='1400', name='ЗАДАНИЕ 14', letters='|,/,-')
Orthogram.objects.create(id='1500', name='ЗАДАНИЕ 15', letters='н,нн')

# Прод-подобные строки (дампы backups/*.sql): скобки в masked_word,
# '\\' как маркер раздельного в text/explanation.
ROWS = [
    # id-метка, text, masked_word, explanation, ожидаемые маркеры
    ('sep_sep', 'В\\НАЧАЛЕ романа герой В\\ОДИНОЧКУ пытается противостоять обстоятельствам.',
     '(В)*1400*НАЧАЛЕ романа герой (В)*1400*ОДИНОЧКУ пытается противостоять обстоятельствам.',
     '\\,\\', ['|', '|']),
    ('sep_sep2', 'ПО\\ТОМУ, как этот человек держится, видно, что он ВО\\ВСЁМ привык быть первым.',
     '(ПО)*1400*ТОМУ, как этот человек держится, видно, что он (ВО)*1400*ВСЁМ привык быть первым.',
     '\\,\\', ['|', '|']),
    ('def_def', 'По утрам с запада, ИЗ-ЗА дальних бугров, выползала ПЕПЕЛЬНО-СИНЯЯ туча.',
     'По утрам с запада, ИЗ*1400*(ЗА) дальних бугров, выползала (ПЕПЕЛЬНО)*1400*СИНЯЯ туча.',
     '-,-', ['-', '-']),
    ('def_sli', 'Вопреки ожиданиям нам ВСЁ-ТАКИ разрешили осмотреть приусадебное хозяйство, пострадавшее В/СЛЕДСТВИЕ наводнения.',
     'Вопреки ожиданиям нам ВСЁ*1400*(ТАКИ) разрешили осмотреть приусадебное хозяйство, пострадавшее (В)*1400*СЛЕДСТВИЕ наводнения.',
     '-,/', ['-', '/']),
    ('sep_sli', 'Этот С\\ВИДУ тихий и скромный человек В/ПОСЛЕДСТВИИ проявил себя как настоящий герой.',
     'Этот (С)*1400*ВИДУ тихий и скромный человек (В)*1400*ПОСЛЕДСТВИИ проявил себя как настоящий герой.',
     '|,/', ['|', '/']),
    ('fallback', 'Он пришёл ВО/ВРЕМЯ и ТОТ/ЧАС ушёл.',
     'Он пришёл (ВО)*1400*ВРЕМЯ и (ТОТ)*1400*ЧАС ушёл.',
     '', ['/', '/']),
    ('three', 'Отец пошёл КУДА-ТО, сказав, что ему нужно КОЕ\\С\\КЕМ встретиться.',
     'Отец пошёл КУДА*1400*(ТО), сказав, что ему нужно (КОЕ)*1400*(С)*1400*КЕМ встретиться.',
     '-,\\,\\', ['-', '|', '|']),
    ('broken', 'Я закончил ТО\\ЖЕ училище, что и отец.',
     'Я закончил ТО*1400(ЖЕ) училище, что и отец.',
     '\\,\\', None),  # битая маска: пример должен пропускаться
]
ids = {}
for key, text, masked, expl, _ in ROWS:
    ex = OrthogramExample.objects.create(text=text, masked_word=masked,
                                         explanation=expl, orthogram_id='1400',
                                         grades='7,8,9,10,11', is_active=True)
    ids[key] = ex.id

print('== парсер explanation ==')
check(parse_task14_markers('\\,\\') == ['|', '|'], "'\\\\,\\\\' -> ['|','|']")
check(parse_task14_markers('-,\\') == ['-', '|'], "'-,\\\\' -> ['-','|']")
check(parse_task14_markers(' | , / ') == ['|', '/'], 'пробелы вокруг маркеров')
check(parse_task14_markers('слова, вместо маркеров') == [], 'слова не считаются маркерами')
check(parse_task14_markers('') == [], 'пустой explanation')

print('== якорный fallback (скобки в masked_word) ==')
for key, text, masked, expl, want in ROWS:
    if want is None:
        continue
    got = extract_from_text_and_masks(text, masked, 1400)
    check(got == want, f'{key}: {got} == {want}')
check(extract_from_text_and_masks('текст без маркера', 'слово*1400*слово', 1400) == [],
      'немаркерный символ -> [] (не выдумываем)')

print('== API: generate-exercise-multi + check-exercise ==')
c = Client()
c.force_login(u)
r = c.post('/api/generate-exercise-multi/',
           data=json.dumps({'orthogram_ids': ['1400']}),
           content_type='application/json')
check(r.status_code == 200, f'генерация 200 (got {r.status_code})')
sess = c.session['current_exercise']
check(sess['exercise_id'] == 'multi_1400', 'exercise_id multi_1400')
check(len(sess['example_ids']) == 5, '5 предложений')
check(ids['broken'] not in sess['example_ids'], 'битая маска пропущена')
flat_correct = [ch for row in sess['correct_letters'] for ch in row]
check(all(ch in ('|', '/', '-') for ch in flat_correct),
      f'эталоны только из алфавита: {flat_correct}')
check(all(len(row) >= 2 for row in sess['correct_letters']), '>=2 маркеров на строку')

r = c.post('/api/check-exercise/',
           data=json.dumps({'user_words': flat_correct}),
           content_type='application/json')
check(r.status_code == 200 and r.json() == [True] * len(flat_correct),
      'правильные ответы (в т.ч. "|") -> все True')

wrong = list(flat_correct)
wrong[0] = {'|': '/', '/': '-', '-': '|'}[wrong[0]]
r = c.post('/api/check-exercise/',
           data=json.dumps({'user_words': wrong}),
           content_type='application/json')
res = r.json()
check(res[0] is False and all(res[1:]), 'одна ошибка -> False только на её позиции')

# Старые сессии с '\\' в эталоне продолжают проверяться (фикс A).
sess = c.session
sess['current_exercise'] = {'exercise_id': 'multi_1400',
                            'correct_letters': [['\\', '\\']],
                            'example_ids': [], 'orthogram_ids': [1400]}
sess.save()
r = c.post('/api/check-exercise/',
           data=json.dumps({'user_words': ['|', '|']}),
           content_type='application/json')
check(r.json() == [True, True], "старая сессия '\\\\' vs пользователь '|' -> True")

print('== рубеж: generate_task14_lines ==')
for _ in range(10):
    data = generate_task14_lines()
    lines, expected = data['lines'], data['expected_letters']
    n_masks = sum(line.count('*14-') for line in lines)
    check(len(expected) == n_masks and n_masks > 0,
          f'эталонов ровно по маскам ({len(expected)} == {n_masks})')
    check(all(ch in ('|', '/', '-') for ch in expected), 'эталоны из алфавита')
    check(all('*1400' not in line for line in lines), 'сырых масок *1400* в строках нет')
    check(all('*1400(' not in line and ')*1400' not in line.replace('*14-', '')
              for line in lines), 'битые маски не попали')
    if any('НАЧАЛЕ романа' in line for line in lines):
        i = next(i for i, l in enumerate(lines) if 'НАЧАЛЕ романа' in l)
        offs = [sum(l.count('*14-') for l in lines[:i]),
                sum(l.count('*14-') for l in lines[:i + 1])]
        check(expected[offs[0]:offs[1]] == ['|', '|'],
              'строка с \\ в explanation даёт [|,|], а не мусор')

print('== регресс задания 15 ==')
OrthogramExample.objects.create(
    text='стеклянный, оловянный, деревянный',
    masked_word='стекля*1500*ый, оловя*1500*ый, деревя*1500*ый',
    explanation='нн,нн,н', orthogram_id='1500', grades='7', is_active=True)
r = c.post('/api/generate-exercise-multi/',
           data=json.dumps({'orthogram_ids': ['1500']}),
           content_type='application/json')
check(r.status_code == 200, 'генерация 1500 -> 200')
flat15 = [ch for row in c.session['current_exercise']['correct_letters'] for ch in row]
check(flat15 == ['нн', 'нн', 'н'], f'эталоны 1500: {flat15}')
r = c.post('/api/check-exercise/',
           data=json.dumps({'user_words': flat15}),
           content_type='application/json')
check(r.json() == [True, True, True], 'проверка 1500 -> все True')

print()
if fails:
    print(f'❌ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('  -', f)
    raise SystemExit(1)
print('✅ test_task14: все проверки зелёные')
