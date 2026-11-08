# -*- coding: utf-8 -*-
"""Тест сброса пароля (/accounts/password/reset/):
ссылка на логине, письмо со ссылкой, превью-бот не сжигает токен (GET безопасен),
смена пароля, одноразовость ссылки, без утечки существования аккаунта,
лимит 5 запросов в час с IP. Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_password_reset.py
"""
import os
import re
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core import mail
from django.test import Client
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

User = get_user_model()
fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


OLD = 'OldPass123!'
NEW = 'NewPass456!'
u = User.objects.create_user(username='sasha', email='lohovs549@example.com',
                             password=OLD)
mail.outbox.clear()  # сигнал регистрации шлёт письмо владельцу — оно не про сброс

LINK_RE = re.compile(r'(http://[^/\s]+/accounts/password/reset/confirm/[^/\s]+/[^/\s]+/)')

print('1. Вход и форма запроса')
c = Client()
login_html = c.get('/accounts/login/', HTTP_HOST='localhost').content.decode('utf-8')
check('/accounts/password/reset/' in login_html, 'на логине ссылка «Забыли пароль?»')
r = c.get('/accounts/password/reset/', HTTP_HOST='localhost')
check(r.status_code == 200, f'GET формы сброса -> 200 (факт: {r.status_code})')

print('2. Запись письма и ссылка')
r = c.post('/accounts/password/reset/', data={'email': 'lohovs549@example.com'},
           HTTP_HOST='localhost')
check(r.status_code == 302 and '/accounts/password/reset/done/' in r['Location'],
      f'POST -> редирект на «письмо отправлено» (факт: {r.status_code})')
check(len(mail.outbox) == 1, f'одно письмо в outbox (факт: {len(mail.outbox)})')
body = mail.outbox[0].body
m = LINK_RE.search(body)
check(m is not None, 'в письме ссылка на подтверждение')
link = m.group(1) if m else ''
check('Нейростат' in mail.outbox[0].subject, 'тема письма с именем проекта')

print('3. Превью-бот кликает ссылку: токен не сгорает')
r1 = c.get(link, HTTP_HOST='localhost')
r2 = c.get(link, HTTP_HOST='localhost')
check(r1.status_code == 302 and r2.status_code == 302
      and '/set-password/' in r1['Location'],
      'GET ссылки -> 302 на форму без токена в URL (токен в сессию)')
form_url = r1['Location']
r3 = c.get(form_url, HTTP_HOST='localhost')
check(r3.status_code == 200 and 'Новый пароль' in r3.content.decode('utf-8'),
      'форма нового пароля открывается (повторный GET тоже безопасен)')

print('4. Смена пароля')
r = c.post(form_url, data={'new_password1': NEW, 'new_password2': NEW},
           HTTP_HOST='localhost')
check(r.status_code == 302 and '/accounts/password/reset/complete/' in r['Location'],
      f'POST нового пароля -> редирект на «готово» (факт: {r.status_code})')
u.refresh_from_db()
check(u.check_password(NEW) and not u.check_password(OLD),
      'новый пароль работает, старый нет')

print('5. Ссылка одноразовая')
r = c.get(link, HTTP_HOST='localhost')
check('недействительна' in r.content.decode('utf-8'),
      'повторный заход по старой ссылке -> «недействительна»')
r = c.get(form_url, HTTP_HOST='localhost')
check('недействительна' in r.content.decode('utf-8'),
      'и форма без токена в сессии уже не открывается')

print('6. Без утечки существования аккаунта')
n = len(mail.outbox)
r = c.post('/accounts/password/reset/', data={'email': 'net-takogo@example.com'},
           HTTP_HOST='localhost')
check(r.status_code == 302, 'неизвестный email -> та же страница «отправлено»')
check(len(mail.outbox) == n, 'письмо на неизвестный email не уходит')
ghost = User.objects.create_user(username='ghost', email='ghost@example.com',
                                 password=OLD)
ghost.is_active = False
ghost.save()
mail.outbox.clear()
r = c.post('/accounts/password/reset/', data={'email': 'ghost@example.com'},
           HTTP_HOST='localhost')
check(len(mail.outbox) == 0, 'неактивному аккаунту письмо не уходит')

print('7. Лимит: 5 запросов в час с IP')
cache.clear()
ok = 0
for _ in range(5):
    rr = c.post('/accounts/password/reset/', data={'email': 'lohovs549@example.com'},
                HTTP_HOST='localhost')
    ok += rr.status_code == 302
check(ok == 5, f'первые 5 запросов проходят (факт: {ok})')
r = c.post('/accounts/password/reset/', data={'email': 'lohovs549@example.com'},
           HTTP_HOST='localhost')
page = r.content.decode('utf-8')
check(r.status_code == 200 and 'Слишком много запросов' in page,
      'шестой запрос за час отклонён с понятной ошибкой')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ СБРОСА ПАРОЛЯ ПРОЙДЕНЫ')
