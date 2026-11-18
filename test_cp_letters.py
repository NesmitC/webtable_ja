# -*- coding: utf-8 -*-
"""Рубежи cp10/cp12/cp13/cp14/cp15/cp16/cp17/cp18/cp19/cp20: алфавит ответов покрывает все буквы пула.
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
from main.models import Orthogram, OrthogramExample, Punktum, PunktumExample

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
    '1': 'Проверяемые гласные', '25': 'Личные окончания глаголов',
    '621': 'Наречия слитно', '64': 'Производные предлоги (наречия)',
    '65': 'Производные предлоги', '67': 'Союзы также/тоже/чтобы',
    '68': 'Частицы бы/ли/же', '69': 'Частица -КА',
    '691': 'Частица -ТО', '692': 'Частица -ТАКИ', '70': 'Повторные междометия',
    '1500': 'Задание 15: Н и НН',
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
    ('1', 'гора', 'г*1*ра'),
    ('1', 'вода', 'в*1*да'),
    ('1', 'мясо', 'м*1*со'),
    ('25', 'борется', 'бор*25*тся'),
    ('25', 'видит', 'вид*25*т'),
    ('25', 'клеит', 'кле*25*т'),
    ('621', 'в/миг', 'в*621*миг'),
    ('621', 'На\\миг', 'На*621*миг'),
    ('64', 'в/переди', 'в*64*переди'),
    ('64', 'в\\место', 'в*64*место'),
    ('65', 'в/следствии', 'в*65*следствии'),
    ('65', 'в\\течение', 'в*65*течение'),
    ('67', 'что/бы', 'что*67*бы'),
    ('67', 'так\\же', 'так*67*же'),
    ('68', 'что\\бы', 'что*68*бы'),
    ('68', 'то/же', 'то*68*же'),
    ('69', 'иди-ка', 'иди*69*ка'),
    ('691', 'был-то', 'был*691*то'),
    ('692', 'всё-таки', 'всё*692*таки'),
    ('692', 'он\\таки', 'он*692*таки'),
    ('70', 'ох-ох', 'ох*70*ох'),
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

print('=== Задание 14 рубежа cp15: маркеры слитно/раздельно/дефис ===')
random.seed(7)
res14 = views._cp_mixed_lines(pupil, ('14',), blocks=2)
lines14 = res14['lines']
check(len(lines14) == 10, f'10 строк (2 блока x 5), получено {len(lines14)}')
bad14 = [(ln['display_line'], l) for ln in lines14
         for l in ln['expected_letters'] if l not in ln['available_letters']]
check(not bad14, f'все эталоны в алфавите (нарушений: {len(bad14)})')
letters14 = {l for ln in lines14 for l in ln['expected_letters']}
check(letters14 <= {'|', '/', '-'}, f'только маркеры | / -, got {letters14}')
check(letters14 == {'|', '/', '-'}, 'все три маркера встречаются')
check(res14['subgroup_letters']['b14-1'] == ['|', '/', '-'],
      'алфавит блока 14 = | / -')
titles14 = [ln['unit_title'] for ln in lines14]
check(titles14[:5] == ['Задание 14 (1)'] * 5
      and titles14[5:] == ['Задание 14 (2)'] * 5,
      'заголовки блоков: Задание 14 (1) / (2)')
# маска + эталон восстанавливают исходный текст владельца
# ('\' в текстах нормализуется в '|' — оба маркера раздельности)
texts14 = {t.replace('\\', '|') for oid, t, _ in WORDS if oid in
           ('621', '64', '65', '67', '68', '69', '691', '692', '70')}
recon14 = []
for ln in lines14:
    for part, letter in zip(ln['display_line'].split(', '),
                            ln['expected_letters']):
        m = re.search(r'\*(9-\d+)\*', part)
        if not m:
            recon14.append((part, 'нет маски'))
            continue
        rebuilt = part[:m.start()] + letter + part[m.end():]
        if rebuilt not in texts14:
            recon14.append((part, f'эталон {letter!r} -> {rebuilt!r}'))
check(not recon14, f'маска+эталон дают исходное слово (нарушений: {len(recon14)})')
for b in recon14[:5]:
    print('     ', b)

print('=== Рубеж cp15 целиком: 12 блоков по 5 строк по 3 слова ===')
random.seed(7)
res15 = views._cp_mixed_lines(pupil, ('9', '10', '11', '12', '13', '14'),
                             blocks=2)
lines15 = res15['lines']
check(len(lines15) == 60, f'60 строк (12 блоков x 5), получено {len(lines15)}')
check(all(len(ln['expected_letters']) == 3 for ln in lines15),
      'в каждой строке ровно 3 слова')
units15 = list(dict.fromkeys(ln['unit'] for ln in lines15))
check(units15 == views.CHECKPOINT_META['cp15']['tasks'],
      f'блоки совпадают с meta cp15: {units15}')
bad15 = [(ln['display_line'], l) for ln in lines15
         for l in ln['expected_letters'] if l not in ln['available_letters']]
check(not bad15, f'все эталоны в алфавитах своих блоков (нарушений: {len(bad15)})')
check(len(res15['letter_groups']) == 180, '180 масок = 180 эталонов')
check(views.CHECKPOINT_MAX_ERRORS['cp15'] == 2, 'допуск cp15 = 2 ошибки')
rows15 = dict(views._task_rows('cp15'))
check(rows15.get('14b1') == 'Задание 14 (1)'
      and rows15.get('14b2') == 'Задание 14 (2)',
      'подписи строк разбора для блоков 14')
check(all(t in views.CHECKPOINT_TASK_LINKS['cp15']
          for t in views.CHECKPOINT_META['cp15']['tasks']),
      'ссылки рекомендаций есть для всех блоков cp15')

print('=== Рубеж cp16: по 1 блоку 9–14 + 3 предложения Н/НН ===')
# Предложения задания 15 (орфограмма 1500): эталон в explanation
NN_SENTENCES = [
    ('Старинный кожаный или серебряный бар',
     'Стари*1500*ый кожа*1500*ый или серебря*1500*ый бар', 'нн,н,н'),
    ('Доставлена и одобрена, торжественная церемония',
     'Доставле*1500*а и одобре*1500*а, торжестве*1500*ая церемония', 'н,н,нн'),
    ('Глиняный кувшин и песчаная коса',
     'Глиня*1500*ый кувшин и песча*1500*ая коса', 'н,н'),
]
for text, masked, expl in NN_SENTENCES:
    OrthogramExample.objects.create(orthogram_id='1500', text=text,
                                    masked_word=masked, explanation=expl)
# Битый пример: 2 маски, 1 буква в эталоне — должен быть пропущен
OrthogramExample.objects.create(orthogram_id='1500', text='раненый боец',
                                masked_word='ране*1500*ый бое*1500*',
                                explanation='н')
random.seed(7)
res16w = views._cp_mixed_lines(pupil, ('9', '10', '11', '12', '13', '14'),
                              blocks=1)
check(len(res16w['lines']) == 30,
      f"словесная часть: 30 строк (6 блоков x 5), получено {len(res16w['lines'])}")
titles16 = [ln['unit_title'] for ln in res16w['lines']]
check(titles16 == [f'Задание {k}' for k in ('9', '10', '11', '12', '13', '14')
                   for _ in range(5)],
      'одиночные блоки без (1): Задание 9 ... Задание 14')
nn = views._cp_nn_sentences(blocks=3, start_flat=91)
check(len(nn['lines']) == 3, f"3 предложения Н/НН, получено {len(nn['lines'])}")
check([ln['unit'] for ln in nn['lines']] == ['15b1', '15b2', '15b3'],
      'блоки 15b1/15b2/15b3')
check([ln['unit_title'] for ln in nn['lines']]
      == ['Задание 15 (1)', 'Задание 15 (2)', 'Задание 15 (3)'],
      'заголовки Задание 15 (1..3)')
nn_letters = {l for ln in nn['lines'] for l in ln['expected_letters']}
check(nn_letters == {'н', 'нн'}, f'эталон только н/нн, got {nn_letters}')
check(all(ln['available_letters'] == ['н', 'нн'] for ln in nn['lines']),
      'алфавит предложений = н/нн')
check(not any('бое' in ln['display_line'] for ln in nn['lines']),
      'битый пример (2 маски, 1 буква) пропущен')
check(nn['next_flat'] == 91 + sum(len(ln['expected_letters'])
                                 for ln in nn['lines']),
      'сквозная нумерация масок продолжается после 90')
# маска + эталон восстанавливают исходное предложение
nn_texts = {t for t, _, _ in NN_SENTENCES}
recon_nn = []
for ln in nn['lines']:
    rebuilt = ln['display_line']
    for letter in ln['expected_letters']:
        rebuilt = re.sub(r'\*9-\d+\*', letter, rebuilt, count=1)
    if rebuilt not in nn_texts:
        recon_nn.append(rebuilt)
check(not recon_nn, f'маска+эталон дают исходное предложение ({len(recon_nn)})')
# малый пул: блоков больше, чем примеров — повтор по кругу, без пропаж
nn5 = views._cp_nn_sentences(blocks=5, start_flat=1)
check(len(nn5['lines']) == 5, 'малый пул: 5 блоков из 3 примеров (повтор)')
# слияние как в _checkpoint_build
merged = res16w['lines'] + nn['lines']
units16 = list(dict.fromkeys(ln['unit'] for ln in merged))
check(units16 == views.CHECKPOINT_META['cp16']['tasks'],
      f'блоки cp16 совпадают с meta: {units16}')
all_groups = dict(res16w['letter_groups'])
all_groups.update(nn['letter_groups'])
check(len(all_groups) == sum(len(ln['expected_letters']) for ln in merged),
      'каждая маска имеет группу')
all_sub = dict(res16w['subgroup_letters'])
all_sub.update(nn['subgroup_letters'])
# проверка по сквозному индексу масок
idx = 1
bad16 = []
for ln in merged:
    for l in ln['expected_letters']:
        if l not in all_sub[all_groups[f'9-{idx}']]:
            bad16.append((idx, l))
        idx += 1
check(not bad16, f'все эталоны cp16 в алфавитах своих блоков ({len(bad16)})')
check(views.CHECKPOINT_MAX_ERRORS['cp16'] == 2, 'допуск cp16 = 2 ошибки')
rows16 = dict(views._task_rows('cp16'))
check(rows16.get('9b1') == 'Задание 9' and rows16.get('15b3') == 'Задание 15 (3)',
      'подписи строк разбора cp16')
check(all(t in views.CHECKPOINT_TASK_LINKS['cp16']
          for t in views.CHECKPOINT_META['cp16']['tasks']),
      'ссылки рекомендаций есть для всех блоков cp16')

print('=== Рубеж cp17: блок 14 + Н/НН + 2 блока по 5 предложений с запятыми ===')
Punktum.objects.create(id='1600', name='Задание 16', rule='-')
COMMA_SENTENCES = [
    ('Пленяющая красота русских пейзажей поразительна и надолго остаётся в памяти.',
     'Пленяющая красота русских пейзажей поразительна *1600* и надолго остаётся в памяти.',
     '?'),
    ('Романтики обращали внимание на внутренний мир личности, и текст стал зоной эксперимента.',
     'Романтики обращали внимание на внутренний мир личности *1600* и текст стал зоной *1600* эксперимента.',
     '!,?'),
    ('Герой не мог быть подлым, или злобным, или нерешительным.',
     'Герой не мог быть подлым *1600* или злобным *1600* или нерешительным.',
     '!,!'),
    ('Большой товарный поезд.',
     'Большой *1600* товарный поезд.', '?'),
    ('Иван да Марья.', 'Иван *1600* да Марья.', '?'),
]
for text, masked, expl in COMMA_SENTENCES:
    PunktumExample.objects.create(punktum_id='1600', text=text,
                                  masked_word=masked, explanation=expl)
# Битый пример: 2 маски, 1 знак — должен быть пропущен
PunktumExample.objects.create(punktum_id='1600', text='Битый пример',
                              masked_word='Слово *1600* и слово *1600*',
                              explanation='!')
random.seed(11)
res17w = views._cp_mixed_lines(pupil, ('14',), blocks=1)
check(len(res17w['lines']) == 5,
      f"блок 14: 5 строк, получено {len(res17w['lines'])}")
check(all(ln['unit_title'] == 'Задание 14' for ln in res17w['lines']),
      'заголовок без (1): Задание 14')
nn17 = views._cp_nn_sentences(blocks=1, start_flat=16)
check(len(nn17['lines']) == 1 and nn17['lines'][0]['unit_title'] == 'Задание 15',
      'одиночный блок Н/НН: заголовок Задание 15 без (1)')
pk = views._cp_punktum_sentences('1600', blocks=2, per_block=5,
                                 start_flat=nn17['next_flat'])
check(len(pk['lines']) == 10,
      f"2 блока по 5 предложений, получено {len(pk['lines'])}")
check([ln['unit'] for ln in pk['lines']] == ['16b1'] * 5 + ['16b2'] * 5,
      'блоки 16b1/16b2 по 5 строк')
check([ln['unit_title'] for ln in pk['lines']]
      == ['Задание 16 (1)'] * 5 + ['Задание 16 (2)'] * 5,
      'заголовки Задание 16 (1)/(2)')
check(len({ln['display_line'] for ln in pk['lines'][:5]}) == 5
      and len({ln['display_line'] for ln in pk['lines'][5:]}) == 5,
      'внутри блока предложения не повторяются (пул 5 >= 5)')
pk_letters = {l for ln in pk['lines'] for l in ln['expected_letters']}
check(pk_letters == {'!', '?'}, f'эталон только !/?, got {pk_letters}')
check(all(ln['available_letters'] == [',', 'х'] for ln in pk['lines']),
      'кнопки ученика: , и х')
check(all(s == [',', 'х'] for s in pk['subgroup_letters'].values()),
      'алфавит подгрупп = ,/х')
check(not any('Битый' in ln['display_line'] for ln in pk['lines']),
      'битый пример (2 маски, 1 знак) пропущен')
# маска + эталон восстанавливают исходное предложение (! -> ',', ? -> '')
pk_texts = {t for t, _, _ in COMMA_SENTENCES}
recon_pk = []
for ln in pk['lines']:
    rebuilt = ln['display_line']
    for letter in ln['expected_letters']:
        repl = ',' if letter == '!' else ''
        rebuilt = re.sub(r'\*9-\d+\*', repl, rebuilt, count=1)
    # в БД маска стоит после пробела: запятая прилипает к предыдущему слову
    rebuilt = rebuilt.replace(' ,', ',')
    rebuilt = re.sub(r' {2,}', ' ', rebuilt)
    if rebuilt not in pk_texts:
        recon_pk.append(rebuilt)
check(not recon_pk, f'маска+эталон дают исходное предложение ({len(recon_pk)})')
# слияние как в _checkpoint_build
merged17 = res17w['lines'] + nn17['lines'] + pk['lines']
units17 = list(dict.fromkeys(ln['unit'] for ln in merged17))
check(units17 == views.CHECKPOINT_META['cp17']['tasks'],
      f'блоки cp17 совпадают с meta: {units17}')
groups17 = dict(res17w['letter_groups'])
groups17.update(nn17['letter_groups'])
groups17.update(pk['letter_groups'])
sub17 = dict(res17w['subgroup_letters'])
sub17.update(nn17['subgroup_letters'])
sub17.update(pk['subgroup_letters'])
check(len(groups17) == sum(len(ln['expected_letters']) for ln in merged17),
      'каждая маска cp17 имеет группу')
idx = 1
bad17 = []
for ln in merged17:
    for l in ln['expected_letters']:
        alphabet = sub17[groups17[f'9-{idx}']]
        # для запятых эталон !/? соответствует кнопкам ,/х
        shown = {'!': ',', '?': 'х'}.get(l, l)
        if shown not in alphabet:
            bad17.append((idx, l))
        idx += 1
check(not bad17, f'все эталоны cp17 представимы кнопками ({len(bad17)})')
check(views.CHECKPOINT_MAX_ERRORS['cp17'] == 2, 'допуск cp17 = 2 ошибки')
rows17 = dict(views._task_rows('cp17'))
check(rows17.get('14b1') == 'Задание 14' and rows17.get('16b2') == 'Задание 16 (2)',
      'подписи строк разбора cp17')
check(all(t in views.CHECKPOINT_TASK_LINKS['cp17']
          for t in views.CHECKPOINT_META['cp17']['tasks']),
      'ссылки рекомендаций есть для всех блоков cp17')

print('=== Рубеж cp18: Н/НН + 5 предложений (16) + 3x1 предложение (17) ===')
Punktum.objects.create(id='1700', name='Задание 17', rule='-')
COMMA17_SENTENCES = [
    ('И вот приходит этот жаркий час, самый счастливый для деревьев.',
     'И вот *1700* приходит этот жаркий час *1700* самый счастливый для деревьев.',
     '?,!'),
    ('В опере, написанной Прокофьевым, есть сцены бала.',
     'В опере *1700* написанной Прокофьевым *1700* есть сцены бала.',
     '!,!'),
    ('Он улыбнулся и кивнул.', 'Он улыбнулся *1700* и кивнул.', '?'),
]
for text, masked, expl in COMMA17_SENTENCES:
    PunktumExample.objects.create(punktum_id='1700', text=text,
                                  masked_word=masked, explanation=expl)
random.seed(7)
nn18 = views._cp_nn_sentences(blocks=1, start_flat=1)
check(len(nn18['lines']) == 1 and nn18['lines'][0]['unit_title'] == 'Задание 15',
      'cp18: одиночный блок Н/НН без (1)')
p16 = views._cp_punktum_sentences('1600', blocks=1, per_block=5,
                                  start_flat=nn18['next_flat'])
check(len(p16['lines']) == 5
      and all(ln['unit'] == '16b1' for ln in p16['lines'])
      and all(ln['unit_title'] == 'Задание 16' for ln in p16['lines']),
      'cp18: блок 16 = 5 предложений, заголовок без (1)')
p17 = views._cp_punktum_sentences('1700', blocks=3, per_block=1,
                                  start_flat=p16['next_flat'])
check([ln['unit'] for ln in p17['lines']] == ['17b1', '17b2', '17b3'],
      'cp18: блоки 17b1/17b2/17b3')
check([ln['unit_title'] for ln in p17['lines']]
      == ['Задание 17 (1)', 'Задание 17 (2)', 'Задание 17 (3)'],
      'cp18: заголовки Задание 17 (1..3)')
check(len({ln['display_line'] for ln in p17['lines']}) == 3,
      'cp18: 3 разных предложения задания 17')
merged18 = nn18['lines'] + p16['lines'] + p17['lines']
units18 = list(dict.fromkeys(ln['unit'] for ln in merged18))
check(units18 == views.CHECKPOINT_META['cp18']['tasks'],
      f'блоки cp18 совпадают с meta: {units18}')
groups18 = dict(nn18['letter_groups'])
groups18.update(p16['letter_groups'])
groups18.update(p17['letter_groups'])
sub18 = dict(nn18['subgroup_letters'])
sub18.update(p16['subgroup_letters'])
sub18.update(p17['subgroup_letters'])
check(len(groups18) == sum(len(ln['expected_letters']) for ln in merged18),
      'каждая маска cp18 имеет группу')
idx = 1
bad18 = []
for ln in merged18:
    for l in ln['expected_letters']:
        alphabet = sub18[groups18[f'9-{idx}']]
        shown = {'!': ',', '?': 'х'}.get(l, l)
        if shown not in alphabet:
            bad18.append((idx, l))
        idx += 1
check(not bad18, f'все эталоны cp18 представимы кнопками ({len(bad18)})')
# восстановление предложений 17
pk17_texts = {t for t, _, _ in COMMA17_SENTENCES}
recon17 = []
for ln in p17['lines']:
    rebuilt = ln['display_line']
    for letter in ln['expected_letters']:
        repl = ',' if letter == '!' else ''
        rebuilt = re.sub(r'\*9-\d+\*', repl, rebuilt, count=1)
    rebuilt = rebuilt.replace(' ,', ',')
    rebuilt = re.sub(r' {2,}', ' ', rebuilt)
    if rebuilt not in pk17_texts:
        recon17.append(rebuilt)
check(not recon17, f'маска+эталон дают исходное предложение 17 ({len(recon17)})')
check(views.CHECKPOINT_MAX_ERRORS['cp18'] == 2, 'допуск cp18 = 2 ошибки')
rows18 = dict(views._task_rows('cp18'))
check(rows18.get('16b1') == 'Задание 16' and rows18.get('17b3') == 'Задание 17 (3)',
      'подписи строк разбора cp18')
check(all(t in views.CHECKPOINT_TASK_LINKS['cp18']
          for t in views.CHECKPOINT_META['cp18']['tasks']),
      'ссылки рекомендаций есть для всех блоков cp18')

print('=== Рубеж cp19: 5 предложений (16) + 2x1 (17) + 3x1 (18) ===')
Punktum.objects.create(id='1800', name='Задание 18', rule='-')
COMMA18_SENTENCES = [
    ('Он, кажется, уже ушёл.',
     'Он *1800* кажется *1800* уже ушёл.', '!,!'),
    ('Ты что же не ешь, Максимка? Ешь, глупый!',
     'Ты что же не ешь *1800* Максимка? Ешь *1800* глупый!', '!,!'),
]
for text, masked, expl in COMMA18_SENTENCES:
    PunktumExample.objects.create(punktum_id='1800', text=text,
                                  masked_word=masked, explanation=expl)
# Битый пример: 2 маски, 1 знак — должен быть пропущен
PunktumExample.objects.create(punktum_id='1800', text='Битый пример 18',
                              masked_word='Слово *1800* и слово *1800*',
                              explanation='!')
random.seed(7)
p16_19 = views._cp_punktum_sentences('1600', blocks=1, per_block=5,
                                     start_flat=1)
check(len(p16_19['lines']) == 5
      and all(ln['unit'] == '16b1' for ln in p16_19['lines'])
      and all(ln['unit_title'] == 'Задание 16' for ln in p16_19['lines']),
      'cp19: блок 16 = 5 предложений, заголовок без (1)')
check(len({ln['display_line'] for ln in p16_19['lines']}) == 5,
      'cp19: внутри блока 16 предложения не повторяются (пул 5 >= 5)')
p17_19 = views._cp_punktum_sentences('1700', blocks=2, per_block=1,
                                     start_flat=p16_19['next_flat'])
check([ln['unit'] for ln in p17_19['lines']] == ['17b1', '17b2'],
      'cp19: блоки 17b1/17b2')
check([ln['unit_title'] for ln in p17_19['lines']]
      == ['Задание 17 (1)', 'Задание 17 (2)'],
      'cp19: заголовки Задание 17 (1)/(2)')
check(len({ln['display_line'] for ln in p17_19['lines']}) == 2,
      'cp19: 2 разных предложения задания 17')
p18_19 = views._cp_punktum_sentences('1800', blocks=3, per_block=1,
                                     start_flat=p17_19['next_flat'])
check([ln['unit'] for ln in p18_19['lines']] == ['18b1', '18b2', '18b3'],
      'cp19: блоки 18b1/18b2/18b3')
check([ln['unit_title'] for ln in p18_19['lines']]
      == ['Задание 18 (1)', 'Задание 18 (2)', 'Задание 18 (3)'],
      'cp19: заголовки Задание 18 (1..3)')
check(not any('Битый' in ln['display_line'] for ln in p18_19['lines']),
      'cp19: битый пример 18 пропущен')
check(len(p18_19['lines']) == 3,
      'cp19: малый пул 18 (2 примера) — 3 блока по кругу, без пропаж')
merged19 = p16_19['lines'] + p17_19['lines'] + p18_19['lines']
check(len(merged19) == 10, f'cp19: 10 строк, получено {len(merged19)}')
units19 = list(dict.fromkeys(ln['unit'] for ln in merged19))
check(units19 == views.CHECKPOINT_META['cp19']['tasks'],
      f'блоки cp19 совпадают с meta: {units19}')
groups19 = dict(p16_19['letter_groups'])
groups19.update(p17_19['letter_groups'])
groups19.update(p18_19['letter_groups'])
sub19 = dict(p16_19['subgroup_letters'])
sub19.update(p17_19['subgroup_letters'])
sub19.update(p18_19['subgroup_letters'])
check(len(groups19) == sum(len(ln['expected_letters']) for ln in merged19),
      'каждая маска cp19 имеет группу')
check(all(s == [',', 'х'] for s in sub19.values()),
      'cp19: алфавит всех подгрупп = ,/х')
idx = 1
bad19 = []
for ln in merged19:
    for l in ln['expected_letters']:
        alphabet = sub19[groups19[f'9-{idx}']]
        shown = {'!': ',', '?': 'х'}.get(l, l)
        if shown not in alphabet:
            bad19.append((idx, l))
        idx += 1
check(not bad19, f'все эталоны cp19 представимы кнопками ({len(bad19)})')
# восстановление предложений 18
pk18_texts = {t for t, _, _ in COMMA18_SENTENCES}
recon18 = []
for ln in p18_19['lines']:
    rebuilt = ln['display_line']
    for letter in ln['expected_letters']:
        repl = ',' if letter == '!' else ''
        rebuilt = re.sub(r'\*9-\d+\*', repl, rebuilt, count=1)
    rebuilt = rebuilt.replace(' ,', ',')
    rebuilt = re.sub(r' {2,}', ' ', rebuilt)
    if rebuilt not in pk18_texts:
        recon18.append(rebuilt)
check(not recon18, f'маска+эталон дают исходное предложение 18 ({len(recon18)})')
check(views.CHECKPOINT_MAX_ERRORS['cp19'] == 2, 'допуск cp19 = 2 ошибки')
rows19 = dict(views._task_rows('cp19'))
check(rows19.get('16b1') == 'Задание 16'
      and rows19.get('17b2') == 'Задание 17 (2)'
      and rows19.get('18b3') == 'Задание 18 (3)',
      'подписи строк разбора cp19')
check(all(t in views.CHECKPOINT_TASK_LINKS['cp19']
          for t in views.CHECKPOINT_META['cp19']['tasks']),
      'ссылки рекомендаций есть для всех блоков cp19')
check(views.CHECKPOINT_META['cp19']['unlock_lesson'] == '19–20',
      'cp19 открывает урок 19–20')

print('=== Рубеж cp20: 5 (16) + 1 (17) + 1 (18) + 2x1 (19) + 2x1 (20) ===')
Punktum.objects.create(id='1900', name='Задание 19', rule='-')
Punktum.objects.create(id='2000', name='Задание 20', rule='-')
COMMA19_SENTENCES = [
    ('Чтобы различать виды птиц, орнитологи составляют определители.',
     'Чтобы различать виды птиц *1900* орнитологи составляют определители.',
     '!'),
    ('Мы пошли домой, когда стемнело.',
     'Мы пошли домой *1900* когда стемнело.', '!'),
]
for text, masked, expl in COMMA19_SENTENCES:
    PunktumExample.objects.create(punktum_id='1900', text=text,
                                  masked_word=masked, explanation=expl)
PunktumExample.objects.create(punktum_id='1900', text='Битый пример 19',
                              masked_word='Слово *1900* и слово *1900*',
                              explanation='!')
COMMA20_SENTENCES = [
    ('Я знаю, что он придёт и что мы поговорим.',
     'Я знаю *2000* что он придёт *2000* и что мы поговорим.', '!,?'),
    ('Если пойдёт дождь, мы останемся дома.',
     'Если пойдёт дождь *2000* мы останемся дома.', '!'),
]
for text, masked, expl in COMMA20_SENTENCES:
    PunktumExample.objects.create(punktum_id='2000', text=text,
                                  masked_word=masked, explanation=expl)
PunktumExample.objects.create(punktum_id='2000', text='Битый пример 20',
                              masked_word='Слово *2000* и слово *2000*',
                              explanation='!')
random.seed(7)
p16_20 = views._cp_punktum_sentences('1600', blocks=1, per_block=5,
                                     start_flat=1)
check(len(p16_20['lines']) == 5
      and all(ln['unit_title'] == 'Задание 16' for ln in p16_20['lines']),
      'cp20: блок 16 = 5 предложений, заголовок без (1)')
flat = p16_20['next_flat']
p17_20 = views._cp_punktum_sentences('1700', blocks=1, per_block=1,
                                     start_flat=flat)
check(len(p17_20['lines']) == 1
      and p17_20['lines'][0]['unit'] == '17b1'
      and p17_20['lines'][0]['unit_title'] == 'Задание 17',
      'cp20: одиночный блок 17 без (1)')
p18_20 = views._cp_punktum_sentences('1800', blocks=1, per_block=1,
                                     start_flat=p17_20['next_flat'])
check(len(p18_20['lines']) == 1
      and p18_20['lines'][0]['unit'] == '18b1'
      and p18_20['lines'][0]['unit_title'] == 'Задание 18',
      'cp20: одиночный блок 18 без (1)')
p19_20 = views._cp_punktum_sentences('1900', blocks=2, per_block=1,
                                     start_flat=p18_20['next_flat'])
check([ln['unit'] for ln in p19_20['lines']] == ['19b1', '19b2'],
      'cp20: блоки 19b1/19b2')
check([ln['unit_title'] for ln in p19_20['lines']]
      == ['Задание 19 (1)', 'Задание 19 (2)'],
      'cp20: заголовки Задание 19 (1)/(2)')
check(len({ln['display_line'] for ln in p19_20['lines']}) == 2,
      'cp20: 2 разных предложения задания 19')
check(not any('Битый' in ln['display_line'] for ln in p19_20['lines']),
      'cp20: битый пример 19 пропущен')
p20_20 = views._cp_punktum_sentences('2000', blocks=2, per_block=1,
                                     start_flat=p19_20['next_flat'])
check([ln['unit'] for ln in p20_20['lines']] == ['20b1', '20b2'],
      'cp20: блоки 20b1/20b2')
check([ln['unit_title'] for ln in p20_20['lines']]
      == ['Задание 20 (1)', 'Задание 20 (2)'],
      'cp20: заголовки Задание 20 (1)/(2)')
check(len({ln['display_line'] for ln in p20_20['lines']}) == 2,
      'cp20: 2 разных предложения задания 20')
check(not any('Битый' in ln['display_line'] for ln in p20_20['lines']),
      'cp20: битый пример 20 пропущен')
merged20 = (p16_20['lines'] + p17_20['lines'] + p18_20['lines']
            + p19_20['lines'] + p20_20['lines'])
check(len(merged20) == 11, f'cp20: 11 строк, получено {len(merged20)}')
units20 = list(dict.fromkeys(ln['unit'] for ln in merged20))
check(units20 == views.CHECKPOINT_META['cp20']['tasks'],
      f'блоки cp20 совпадают с meta: {units20}')
groups20 = {}
sub20 = {}
for part in (p16_20, p17_20, p18_20, p19_20, p20_20):
    groups20.update(part['letter_groups'])
    sub20.update(part['subgroup_letters'])
check(len(groups20) == sum(len(ln['expected_letters']) for ln in merged20),
      'каждая маска cp20 имеет группу')
check(all(s == [',', 'х'] for s in sub20.values()),
      'cp20: алфавит всех подгрупп = ,/х')
idx = 1
bad20 = []
for ln in merged20:
    for l in ln['expected_letters']:
        alphabet = sub20[groups20[f'9-{idx}']]
        shown = {'!': ',', '?': 'х'}.get(l, l)
        if shown not in alphabet:
            bad20.append((idx, l))
        idx += 1
check(not bad20, f'все эталоны cp20 представимы кнопками ({len(bad20)})')
# восстановление предложений 19 и 20
for pid, part, sents in (('19', p19_20, COMMA19_SENTENCES),
                         ('20', p20_20, COMMA20_SENTENCES)):
    texts = {t for t, _, _ in sents}
    recon = []
    for ln in part['lines']:
        rebuilt = ln['display_line']
        for letter in ln['expected_letters']:
            repl = ',' if letter == '!' else ''
            rebuilt = re.sub(r'\*9-\d+\*', repl, rebuilt, count=1)
        rebuilt = rebuilt.replace(' ,', ',')
        rebuilt = re.sub(r' {2,}', ' ', rebuilt)
        if rebuilt not in texts:
            recon.append(rebuilt)
    check(not recon,
          f'маска+эталон дают исходное предложение {pid} ({len(recon)})')
check(views.CHECKPOINT_MAX_ERRORS['cp20'] == 2, 'допуск cp20 = 2 ошибки')
rows20 = dict(views._task_rows('cp20'))
check(rows20.get('16b1') == 'Задание 16'
      and rows20.get('17b1') == 'Задание 17'
      and rows20.get('19b2') == 'Задание 19 (2)'
      and rows20.get('20b2') == 'Задание 20 (2)',
      'подписи строк разбора cp20')
check(all(t in views.CHECKPOINT_TASK_LINKS['cp20']
          for t in views.CHECKPOINT_META['cp20']['tasks']),
      'ссылки рекомендаций есть для всех блоков cp20')
check(views.CHECKPOINT_META['cp20']['unlock_lesson'] == '21',
      'cp20 открывает урок 21')

print()
if fails:
    print(f'ПРОВАЛЕНО ПРОВЕРОК: {len(fails)}')
    raise SystemExit(1)
print('ВСЕ ПРОВЕРКИ ЗЕЛЁНЫЕ')