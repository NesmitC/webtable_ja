# -*- coding: utf-8 -*-
"""Тест: видео урока «Задание 7» (Kinescope) встроено в карточку урока 5
страницы /ege/lessons/ и открывается модальным плеером.

Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.
Запуск: .\\.venv\\Scripts\\python.exe test_lesson7_video.py
"""
import os
import re
import sys
from datetime import timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from main.models import UserProfile

EMBED = 'https://kinescope.io/embed/nT22UFp4rXMQqfgXhgJVzE'
PUBLIC = 'https://kinescope.io/nT22UFp4rXMQqfgXhgJVzE'

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
u = User.objects.create_user(username='pupil', email='pupil@example.com',
                             password='Zk9mQ2vLp7xR')
prof, _ = UserProfile.objects.get_or_create(user=u)
prof.plan = 'premium'
prof.plan_until = timezone.now() + timedelta(days=30)
prof.save()

c = Client()
c.force_login(u)
r = c.get('/ege/lessons/')
check(r.status_code == 200, f'страница уроков отдалась (факт {r.status_code})')
html = r.content.decode('utf-8')

print('1. Вставка в карточку «Задание 7»')
i7 = html.find('Задание 7 (грамматические нормы)')
check(i7 > 0, 'карточка «Задание 7» на странице')
seg = html[i7:i7 + 1200]
btn = re.search(r'<a href="#" class="lesson-card__video-btn"([^>]*)>', seg)
check(btn is not None, 'кнопка «Смотреть видео» в карточке найдена')
if btn:
    check('data-video-src="%s"' % EMBED in btn.group(1),
          f'у кнопки карточки задания 7 стоит embed-ссылка: {btn.group(1).strip()[:80]}')
check(html.count(EMBED) == 1,
      f'embed-ссылка встречается ровно один раз (факт {html.count(EMBED)})')
check(PUBLIC not in html, 'публичная ссылка (не embed) в разметку не попала')

print('2. Остальные карточки не задеты')
srcs = re.findall(r'class="lesson-card__video-btn" data-video-src="([^"]+)"', html)
check(len(srcs) == 6, f'карточек с видео стало 6 (факт {len(srcs)})')
check(sum(1 for s in srcs if 'kinescope.io/embed/' in s) == 3,
      'из них три Kinescope (уроки 2, 5/задание 7, 7)')
check(sum(1 for s in srcs if 'rutube.ru/play/embed/' in s) == 3, 'три Rutube на месте')
empty = html.count('<a href="#" class="lesson-card__video-btn">')
check(empty == 1, f'пустых кнопок осталась одна (урок 6): факт {empty}')

print('3. Модальный плеер')
check('id="videoModal"' in html and 'id="videoModalFrame"' in html, 'модалка на странице')
check('lessons_video.js' in html, 'JS модального плеера подключён')
allow = re.search(r'id="videoModalFrame"[^>]*allow="([^"]+)"', html)
check(allow is not None, 'атрибут allow у iframe найден')
if allow:
    for perm in ('gyroscope', 'accelerometer', 'clipboard-write', 'screen-wake-lock'):
        check(perm in allow.group(1), f'allow включает {perm}')

print('4. Анону страница недоступна (регресс paywall)')
ca = Client()
ra = ca.get('/ege/lessons/')
check(ra.status_code == 302, f'аноним редиректится на вход (факт {ra.status_code})')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('   -', f)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ВИДЕО ЗАДАНИЯ 7 ПРОЙДЕНЫ')
