# -*- coding: utf-8 -*-
"""Тест мобильных ссылок меню: в мобильном меню ЕГЭ нет мёртвых href="#",
все пункты ведут на живые маршруты; десктопное меню не задето.

Изоляция: test_settings_isolated. Запуск: python test_mobile_links.py
"""
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
from django.urls import reverse

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


c = Client()
r = c.get('/')
check(r.status_code == 200, f'главная отдалась (факт {r.status_code})')
html = r.content.decode('utf-8')

print('1. Мобильное меню ЕГЭ')
m = re.search(r'<ul class="mobile-menu__list">(.*?)</nav>', html, re.S)
check(m is not None, 'мобильный блок меню найден')
menu = m.group(1) if m else ''
check('href="#"' not in menu, 'в мобильном меню нет мёртвых href="#"')

expect = {
    'Диагностики': reverse('diagnostics_ege'),
    'Демо, досрок': reverse('test_fixdemo_ege', args=['demo-2026']),
    'Тренажеры, планинги': reverse('trainers_ege'),
    'Квизы': reverse('quizzes_ege'),
    'Уроки': reverse('lessons_ege'),
}
for label, url in expect.items():
    check(f'href="{url}"' in menu, f'пункт «{label}» -> {url}')
check('href="/#pricing"' in menu, 'пункт «Тарифы» -> /#pricing (работает с любой страницы)')

print('2. Каждый маршрут мобильного меню отвечает (аноним)')
for label, url in expect.items():
    rr = c.get(url)
    ok = rr.status_code in (200, 302)
    check(ok, f'{url} -> {rr.status_code} (200 или редирект на вход)')

print('3. Десктопное меню не задето')
check(html.count(reverse('quizzes_ege')) >= 2,
      f'ссылка на квизы встречается и в десктопе, и в мобильном меню '
      f'({html.count(reverse("quizzes_ege"))} раз)')
check(reverse('lessons_ege') in html, 'уроки в меню на месте')

print('4. Регресс: мёртвые ссылки допустимы только там, где их ловит JS')
dead = re.findall(r'<a href="#"[^>]*>', html)
allowed = all('data-video-src' in d for d in dead)
check(allowed, f'все оставшиеся href="#" на главной — видеокнопки с data-video-src '
               f'({len(dead)} шт.)')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('   -', f)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ МОБИЛЬНЫХ ССЫЛОК ПРОЙДЕНЫ')
