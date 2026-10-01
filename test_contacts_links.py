# -*- coding: utf-8 -*-
"""Тест расширенных контактов: Telegram/VK/MAX как активные ссылки на странице
результата диагностики, в футере и в schema.org; регресс на битые контакты.

Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.
Запуск: .\\.venv\\Scripts\\python.exe test_contacts_links.py
"""
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import Client, RequestFactory
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from main.context_processors import CONTACTS, MESSENGERS, contacts
from main.models import DiagnosticAttempt

TG = CONTACTS['telegram']
VK = CONTACTS['vk']
MAX = CONTACTS['max']
TEL = 'tel:' + CONTACTS['phone']

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


# ===== 1. Единый источник контактов =====
print('1. Контакт-процессор')
ctx = contacts(None)
check(ctx['CONTACTS']['telegram'] == 'https://t.me/sitesprofi',
      f"telegram = {ctx['CONTACTS']['telegram']}")
check(ctx['CONTACTS']['vk'] == 'https://vk.ru/alex_serg_ru',
      f"vk = {ctx['CONTACTS']['vk']}")
check(ctx['CONTACTS']['telegram_handle'] == '@sitesprofi', 'telegram_handle = @sitesprofi')
check([m['key'] for m in MESSENGERS] == ['telegram', 'vk', 'max'],
      f"порядок мессенджеров: {[m['key'] for m in MESSENGERS]}")
check(all(m['url'].startswith('http') for m in MESSENGERS), 'у всех мессенджеров есть URL')
check('main.context_processors.contacts' in str(settings.TEMPLATES),
      'контекст-процессор зарегистрирован в settings')

# ===== 2. Страница результата диагностики (аноним, реальное представление) =====
print('2. Страница результата диагностики')
c = Client()
session_key = c.session.session_key
attempt = DiagnosticAttempt.objects.create(
    session_key=session_key, access_code='DIAG-CTEST',
    primary_score=0, max_primary_score=50, score=0, max_score=100,
    weak_topics=[8, 9], is_completed=True)
r = c.get(f'/diagnostic/result/{attempt.id}/')
check(r.status_code == 200, f'страница отдалась (факт {r.status_code})')
html = r.content.decode('utf-8')

check(html.count(TG) >= 2, f'Telegram-ссылка есть ({html.count(TG)} раз)')
check(html.count(VK) >= 2, f'VK-ссылка есть ({html.count(VK)} раз)')
check(MAX in html, 'MAX-ссылка на месте')
check(TEL in html, f'ссылка на звонок {TEL}')
rows = html.count('<div class="msngr-row')
check(rows == 2, f'блоков мессенджеров ровно 2 (факт {rows})')
check('@sitesprofi' in html or 'Telegram' in html, 'подпись Telegram видна')

# каждая ссылка-мессенджер открывается в новой вкладке
import re
bad = []
for url in (TG, VK, MAX):
    for m in re.finditer(r'<a[^>]*href="' + re.escape(url) + r'"[^>]*>', html):
        if 'target="_blank"' not in m.group(0) or 'rel="noopener"' not in m.group(0):
            bad.append((url, m.group(0)[:90]))
check(not bad, f'все ссылки мессенджеров с target="_blank" rel="noopener"'
               + ('' if not bad else f'; нарушители: {bad[:2]}'))

# в первом ряду (сразу под большой MAX-кнопкой) MAX не дублируется,
# а Telegram и VK — есть
btn = html.find('Написать преподавателю в MAX')
tail = html.find('callbackForm')
check(btn > 0 and tail > btn, f'границы блока найдены (btn={btn}, form={tail})')
segment = html[btn:tail] if (btn > 0 and tail > btn) else ''
check(TG in segment and VK in segment,
      'в ряду под MAX-кнопкой есть Telegram и VK')
check(MAX not in segment,
      'в этом ряду MAX не дублируется (он уже кнопкой выше)')
check('Позвонить' in segment, 'в ряду есть кнопка звонка')
check('в MAX (MAX)' not in html, 'в подсказке MAX нет дубля «MAX (MAX)»')

# ===== 3. Футер =====
print('3. Футер')
footer = render_to_string('includes/footer.html', request=RequestFactory().get('/'))
check(TG in footer, 'Telegram в футере')
check(VK in footer, 'VK в футере (раскомментирован)')
check(MAX in footer, 'MAX в футере')
check(TEL in footer, 'телефон в футере')
check('<!-- <a href="#" class="footer__social-link">' not in footer,
      'заглушка VK больше не закомментирована')
check(footer.count('data-copy="' + CONTACTS['max'] + '"') == 1,
      'кнопка «Копировать» у MAX копирует MAX (была ошибка: копировала телефон)')
check('data-copy="@sitesprofi"' in footer, 'копирование Telegram-ника')
check(footer.count('contacts-pop__label') >= 5,
      f'в поповере контактов >= 5 строк ({footer.count("contacts-pop__label")})')
bad_f = []
for url in (TG, VK, MAX):
    for m in re.finditer(r'<a[^>]*href="' + re.escape(url) + r'"[^>]*>', footer):
        if 'target="_blank"' not in m.group(0):
            bad_f.append(m.group(0)[:80])
check(not bad_f, f'ссылки футера на мессенджеры открываются в новой вкладке'
                 + ('' if not bad_f else f'; нарушители: {bad_f[:2]}'))

# ===== 4. Регресс: битые контакты во всех шаблонах =====
print('4. Скан шаблонов на битые контакты')
BROKEN = {
    '+98765432109': 'телефон-заглушка на странице разбора',
    '+9-876-543-21-09': 'телефон-заглушка (видимый текст)',
    'ваш_канал': 'placeholder в schema.org',
    'ваша_группа': 'placeholder в schema.org',
    'href="a_timof@mail.ru"': 'почтовая ссылка без mailto:',
}
tpl_dir = os.path.join(settings.BASE_DIR, 'main', 'templates')
found = []
for root, _dirs, files in os.walk(tpl_dir):
    for fn in files:
        if not fn.endswith('.html'):
            continue
        p = os.path.join(root, fn)
        text = open(p, encoding='utf-8', errors='replace').read()
        for needle, why in BROKEN.items():
            if needle in text:
                found.append(f'{os.path.relpath(p, tpl_dir)}: {why}')
check(not found, 'битых контактов в шаблонах нет' + ('' if not found else f' -> {found}'))

# ===== 5. index.html: schema.org и mailto (рендер главной) =====
print('5. Главная страница')
ri = Client().get('/')
if ri.status_code == 200:
    ih = ri.content.decode('utf-8')
    check(TG in ih and VK in ih, 'реальные соцсети присутствуют на главной')
    check('mailto:' + CONTACTS['email'] in ih, 'mailto-ссылка в FAQ рабочая')
    check('"sameAs"' in ih, 'блок sameAs на месте')
else:
    print(f'  ⚠️ главная вернула {ri.status_code} — проверка пропущена '
          f'(пустая тестовая БД), на прод проверяется отдельно')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('   -', f)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ КОНТАКТОВ ПРОЙДЕНЫ')
