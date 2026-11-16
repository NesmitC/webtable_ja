# -*- coding: utf-8 -*-
"""Разбор рубежа для преподавателя (/staff/checkpoint/<id>/):
хедер как на всех страницах (adaptive.css + main.js), выжимка без сырых
масок *9-N* — слова с буквами ученика: верно зелёным, ошибка красным
(верная буква рядом), пропуск серым; вердикт из results_data попытки.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint_review.py
"""
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

import main.views as views
from main.models import CheckpointAttempt

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
teacher = User.objects.create_user('t_review', password='x', is_staff=True)
pupil = User.objects.create_user('p_review', password='x')

TD = {
    '9': {
        'lines': [
            'к*9-1*сание, к*9-2*медия, экстр*9-3*мальный',
            'оз*9-4*риться, фраз*9-5*ологический, нас*9-6*комые',
        ],
        'expected': ['а', 'о', 'е', 'а', 'е', 'е'],
    },
    '5': {
        'sentences': ['Он надел (ПРАЗДНИЧНЫЙ/ПРАЗДНЫЙ) костюм.'],
        'correct': 'праздничный',
    },
}
ANS = {'9-1': 'а', '9-2': 'а', '9-3': 'е', '9-4': 'о', '9-5': 'е',
       '9-6': '😊', '5': 'праздный'}
RES = {f'9-{i}': {'correct': v} for i, v in
       enumerate([True, False, True, False, True, False], 1)}
RES.update({'9': {'correct': False}, '5': {'correct': False}})

attempt = CheckpointAttempt.objects.create(
    user=pupil, checkpoint_code='cp9', correct_count=0, error_count=2,
    passed=False, total_tasks=2, answers_data=ANS, results_data=RES,
    test_data=TD)

print('== helper: слова с буквами ученика ==')
lines, ok_n, total_n = views._checkpoint_task9_lines_html(TD['9'], ANS, RES)
check(ok_n == 3 and total_n == 6, f'счётчики верно/всего = {ok_n}/{total_n} (жду 3/6)')
check('к<span class="cp-letter cp-letter--ok">а</span>сание' in lines[0],
      'верная буква а зелёная внутри слова')
check('cp-letter--bad" title="верно: о">а</span><span class="cp-letter-fix" title="верная буква">о</span>' in lines[0],
      'ошибка а красная + верная о рядом')
check('cp-letter--skip" title="нет ответа, верно: е">…</span>' in lines[1],
      'смайлик-пропуск → серое … с подсказкой')
check('*9-' not in ''.join(lines), 'масок *9-N* в словах не осталось')

res_bad = dict(RES)
res_bad['9-1'] = {'correct': False}
lines2, ok2, _ = views._checkpoint_task9_lines_html(TD['9'], ANS, res_bad)
check('cp-letter--bad" title="верно: а">а</span>' in lines2[0] and ok2 == 2,
      'вердикт берётся из results_data, а не пересчёта')

lines3, ok3, _ = views._checkpoint_task9_lines_html(TD['9'], ANS, {})
check(ok3 == 3, 'старая попытка без results: сравнение как при зачёте')
ans_up = dict(ANS)
ans_up['9-1'] = 'А'
_, ok4, _ = views._checkpoint_task9_lines_html(TD['9'], ans_up, {})
check(ok4 == 3, 'регистр и пробелы не ломают сравнение')

td_esc = {'9': {'lines': ['<b>к*9-1*сание</b>'], 'expected': ['а']}}
esc_lines, _, _ = views._checkpoint_task9_lines_html(td_esc['9'], {'9-1': 'а'}, {})
check('&lt;b&gt;' in esc_lines[0] and '<b>' not in esc_lines[0],
      'текст слов экранируется')

print('== читаемая выжимка ==')
fact_html = views._checkpoint_fact_html(attempt)
check('*9-' not in fact_html, 'в выжимке нет сырых масок')
check('эталон по маскам' not in fact_html, 'нет перечня букв через запятую')
check('cp-words' in fact_html and 'cp-letter--ok' in fact_html,
      'слова с подсветкой в выжимке')
check('<b>Итог</b>' in fact_html, 'итог сохранён')
check('Задание 5' in fact_html and 'праздничный' in fact_html,
      'остальные задания как текст с эталоном')

print('== страница /staff/checkpoint/<id>/ ==')
views.cached_llm = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('no llm'))
c = Client()
c.force_login(teacher)
r = c.get(f'/staff/checkpoint/{attempt.id}/', HTTP_HOST='localhost')
html = r.content.decode('utf-8')
check(r.status_code == 200, '200 для staff')
check('css/adaptive.css' in html, 'подключён adaptive.css (хедер не вертикалится)')
check('js/main.js' in html, 'подключён main.js (бургер/меню)')
check('<body class="test_fix_ege">' in html, 'body как на страницах тестов')
check('Выжимка методиста' in html, 'заголовок выжимки на месте')
check('*9-' not in html, 'на странице нет сырых масок')
check('эталон по маскам' not in html, 'на странице нет перечней букв')
check('cp-letter--bad' in html and 'cp-letter-fix' in html, 'подсветка ошибок на странице')
check('planning_style.css?v=20261116a' in html, 'css с версией против кэша')
check(html.count('cp-words__line') == 2, 'строки показаны один раз, без второго блока')
check('<h4' not in html, 'второго блока «Задание 9: ошибка» нет')
check('Блоков для показа нет' not in html, 'нет пустой заглушки блоков')
check('<b>Итог</b>' in html, 'Итог в выжимке')

attempt.digest = 'ИИ-комментарий: тренировать корни с чередованием.'
attempt.save(update_fields=['digest'])
r2 = c.get(f'/staff/checkpoint/{attempt.id}/', HTTP_HOST='localhost')
html2 = r2.content.decode('utf-8')
check('ИИ-комментарий' in html2, 'LLM-выжимка показывается, если есть')
check(html2.count('cp-words__line') == 2, 'строки с подсветкой один раз и при LLM-выжимке')
check('cp-letter--ok' in html2, 'подсветка остаётся при LLM-выжимке')
check('<b>Итог</b>' in html2, 'Итог остаётся при LLM-выжимке')
check('<b>Задание 5' in html2, 'остальные задания остаются в выжимке при LLM-комментарии')

views.cached_llm = lambda *a, **k: 'ИИ: слабое место — безударные гласные в корне.'
attempt.digest = ''
attempt.save(update_fields=['digest'])
r3 = c.get(f'/staff/checkpoint/{attempt.id}/', HTTP_HOST='localhost')
attempt.refresh_from_db()
check('ИИ: слабое место' in r3.content.decode('utf-8') and attempt.digest,
      'LLM-выжимка генерится и кэшируется в попытке')

r4 = Client().get(f'/staff/checkpoint/{attempt.id}/', HTTP_HOST='localhost')
check(r4.status_code == 302, 'аноним → логин')
cp = Client()
cp.force_login(pupil)
check(cp.get(f'/staff/checkpoint/{attempt.id}/', HTTP_HOST='localhost').status_code == 403,
      'ученику без прав staff — 403')
rl = c.get('/staff/checkpoints/', HTTP_HOST='localhost')
check(rl.status_code == 200 and 'css/adaptive.css' in rl.content.decode('utf-8'),
      'реестр попыток: 200 + adaptive.css')

print()
if fails:
    print(f'ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print(' -', f)
    raise SystemExit(1)
print('ВСЕ ПРОВЕРКИ ЗЕЛЁНЫЕ')
