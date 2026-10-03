# -*- coding: utf-8 -*-
"""Тест онлайн-диктантов: парсер (все краевые случаи формата), страница,
проверка, ключи, ссылка с планинга 7 класса.

Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.
Запуск: .\\.venv\\Scripts\\python.exe test_dictation.py
"""
import json
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from main.dictation import parse_dictation, split_answers
from main.models import DictationTask

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()

# ===== 1. Парсер: краевые случаи формата =====
print('1. Парсер')
segs, slots = parse_dictation(
    'Т(е,и)перь (н(е,и))(/,|,-)кому [х ,] и [: -] [« (]а[) »] (тс,тьс) (ъ,ь,/) х')
opts = [s['options'] for s in slots]
check(len(slots) == 9, f'слотов 9 (факт {len(slots)})')
check(opts[0] == ['е', 'и'], f'обычный слот букв: {opts[0]}')
check(opts[1] == ['е', 'и'], f'слот внутри группировки (н(е,и)): {opts[1]}')
check(opts[2] == ['/', '|', '-'], f'слот знаков /|-.: {opts[2]}')
check(opts[3] == ['х', ','], f'[х ,] -> х и запятая: {opts[3]}')
check(opts[4] == [':', '-'], f'[: -] без запятой -> два варианта: {opts[4]}')
check(opts[5] == ['«', '('], f'[« (] -> кавычка и скобка: {opts[5]}')
check(opts[6] == [')', '»'], f'[) »] -> {opts[6]}')
check(opts[7] == ['тс', 'тьс'], f'многосимвольные варианты: {opts[7]}')
check(opts[8] == ['ъ', 'ь', '/'], f'три варианта: {opts[8]}')
texts = ''.join(s['text'] for s in segs if s['type'] == 'text')
check('(н' in texts and ')кому' in texts, 'скобки группировки остались текстом')

segs2, slots2 = parse_dictation('без пропусков просто текст')
check(not slots2, 'текст без пропусков -> 0 слотов')
segs3, slots3 = parse_dictation('открытая ( скобка и ] лишняя')
check(not slots3, 'несбалансированные скобки не ломают парсер')

check(split_answers('и|х|,|ъ') == ['и', 'х', ',', 'ъ'], 'ключи через |')
check(split_answers('') == [], 'пустые ключи -> []')
check(split_answers(' и | , ') == ['и', ','], 'токены стрипятся, запятая цела')

# ===== 2. Настоящий текст «Осень» =====
print('2. Диктант «Осень» (реальный текст)')
OSEN = (
    'Осень [х ,] пр(е,и)ч(у,ю)дл(и,е)вая в(а,о)лшебн(е,и)ца. Пр(е,и)ход(е,и)т она [х ,] '
    'и ра(з,с)ст(е,и)ла(е,и)т ж(ё,о)лтые п(а,о)кр(о,ы)вала на п(а,о)ля [х ,] '
    'ра(з,с)брас(о,ы)ва(е,и)т разн(а,о)цветные лист(ъ,ь,/)я по д(а,о)ро(ж,ш)кам [х ,] '
    'пр(е,и)нос(е,и)т зап(а,о)х свежести [х ,] и ле(г,х)кого м(а,о)ро(з,с)ца.\n'
    'Х(а,о)р(а,о)шо бр(а,о)дить в г(а,о)р(а,о)дском парк(е,и) в такие уд(е,и)вительные дни. '
    'Д(е,и)рев(ъ,ь,/)я об(ъ,ь,/)яты плам(е,и)нем. Т(е,и)перь (н(е,и))(/,|,-)кому '
    'не(/,|,-)ост(а,о)новить осе(н,нн)его п(а,о)жара. Вот заг(а,о)релась осинка '
    'ярко(/,|,-)красными ог(а,о)ньками [х ,] и от нее п(а,о)шел п(а,о)лыхать клен. '
    'Он пр(е,и)к(а,о)снулся к б(е,и)ре(з,с)к(е,и) [х ,] и в(з,с)пыхнула она ж(ё,о)лтым '
    'к(а,о)стром. Обн(а,о)жа(тс,тьс)я д(е,и)рев(ъ,ь,/)я [х ,] и п(а,о)гасн(е,и)т это '
    'разн(а,о)цвет(ъ,ь,/)е.\n'
    'Осень не(/,|,-)хоч(е,и)т ра(з,с)ст(а,о)ваться с людьми [х ,] и часто плач(е,и)т. '
    'П(е,и)чальный дожд(е,и)к капа(е,и)т из туч(ь,_) на землю. Люди смотрят на небо [х ,] '
    'и гру(с,ст)но г(а,о)в(а,о)рят [: -] [« (]Вот и осень [х ,] т(е,и)перь жди з(е,и)мы[) »]. '
    'Если(/,|,-)бы осень умела г(а,о)в(а,о)рить [х ,] она ск(а,о)зала(/,|,-)бы [: -] '
    '[« (] Я не(/,|,-)х(а,о)чу ух(а,о)дить от вас [х ,] люди [х ,] я х(а,о)ч(у,ю) '
    'оста(тс,тьс)я[) »].\n'
    'Мчи(тс,тьс)я бе(з,с)к(а,о)не(чн,чьн)ое время [х ,] и ос(е,и)нь уход(е,и)т.'
)
_segs, slots = parse_dictation(OSEN)
check(len(slots) > 50, f'в «Осени» {len(slots)} слотов')
# все слоты имеют 2+ варианта
check(all(len(s['options']) >= 2 for s in slots), 'у всех слотов минимум 2 варианта')

# шаблон ключей для заполнения владельцем
print()
print('   === ШАБЛОН КЛЮЧЕЙ (заполни токены и вставь в поле «Ключи ответов») ===')
print('   ' + '|'.join('?' for _ in slots))
print('   порядок слотов:')
for s in slots:
    print(f"   {s['index']:>2}: {' / '.join(s['options'])}")
print()

# ===== 3. Модель и ключи =====
print('3. Модель: валидация ключей')
t = DictationTask(title='Мини', grade=7, text='К(а,о)т [х ,] спит.', answers='о|,')
t.full_clean()
check(t.slot_count == 2, f'slot_count=2 (факт {t.slot_count})')
bad = DictationTask(title='Бэд', grade=7, text='К(а,о)т [х ,] спит.', answers='о')
try:
    bad.full_clean()
    check(False, 'несовпадение ключей должна отклонять')
except ValidationError as e:
    check('слотов' in str(e), f'валидатор ловит несовпадение: {str(e)[:80]}')

# ===== 4. Страницы и проверка (аноним — бесплатно) =====
print('4. Вьюхи (аноним)')
task = DictationTask.objects.create(title='Осень', grade=7, text=OSEN, answers='')
c = Client()
r = c.get('/dictations/')
check(r.status_code == 200, f'список диктантов анониму 200 (факт {r.status_code})')
check('Осень' in r.content.decode('utf-8'), 'диктант виден в списке')
r2 = c.get(f'/dictations/{task.pk}/')
html = r2.content.decode('utf-8')
check(r2.status_code == 200, 'страница диктанта анониму 200')
check(html.count('dct-select') >= len(slots),
      f'селектов на странице >= {len(slots)} (факт {html.count("dct-select")})')
check('ещё не загружены' in html, 'без ключей показывается заглушка, не проверка')
r3 = c.post(f'/dictations/{task.pk}/check/',
            data=json.dumps({'answers': {'0': 'х'}}),
            content_type='application/json')
check(r3.status_code == 503, f'проверка без ключей -> 503 (факт {r3.status_code})')

# рабочие ключи: соберём из реальных правильных ответов (первый вариант там,
# где он верен по орфографии — для теста достаточно любого валидного токена)
valid_first = []
for s in slots:
    valid_first.append(s['options'][0])
task.answers = '|'.join(valid_first)
task.save()
r4 = c.post(f'/dictations/{task.pk}/check/',
            data=json.dumps({'answers': {'0': valid_first[0],
                                         '1': 'zzz-не-из-списка',
                                         '2': ''}}),
            content_type='application/json')
check(r4.status_code == 200, f'проверка с ключами 200 (факт {r4.status_code})')
data = r4.json()
check(data['results']['0']['ok'] is True, 'верный токен -> ok')
check(data['results']['1']['ok'] is False, 'неверный токен -> не ok')
check(data['results']['1']['correct'] == valid_first[1], 'пришёл правильный ответ')
check(data['results']['2'].get('skipped') is True, 'пустой ответ -> skipped')
check(data['score']['ok'] == 1 and data['score']['total'] == len(slots),
      f"счёт 1 из {len(slots)} (факт {data['score']})")

# ===== 5. Ссылка с планинга 7 класса =====
print('5. Ссылка на планинге 7')
u = User.objects.create_user('pupil7', 'p7@example.com', 'Zk9mQ2vLp7xR')
c7 = Client()
c7.force_login(u)
r5 = c7.get('/planning/7/')
check(r5.status_code == 200, f'планинг 7 открылся (факт {r5.status_code})')
check('/dictations/' in r5.content.decode('utf-8'), 'ссылка «Диктанты онлайн» на месте')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('   -', f)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ДИКТАНТОВ ПРОЙДЕНЫ')
