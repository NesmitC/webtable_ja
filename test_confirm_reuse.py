# -*- coding: utf-8 -*-
"""Тест идемпотентности ссылки активации: повторный клик (после того как
токен «сгорел» из-за login первого клика — бот предпросмотра, второе
устройство) ведёт на страницу-цель, а не в тупик «недействительна».
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_confirm_reuse.py
"""
import os
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
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from main.models import UserProfile

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()

u = User.objects.create_user(username='pupil', email='p@example.com',
                             password='Zk9mQ2vLp7xR')
u.is_active = False
u.save()
uid = urlsafe_base64_encode(force_bytes(u.pk))
token = default_token_generator.make_token(u)
url = f'/accounts/confirm/{uid}/{token}/'

print('1. Первый клик: активация, триал, страница-цель')
c = Client()
r = c.get(url)
check(r.status_code == 302 and r['Location'] == '/accounts/activated/',
      f'302 на страницу-цель (факт: {r.status_code} {r.get("Location")})')
u.refresh_from_db()
p = UserProfile.objects.get(user=u)
check(u.is_active, 'пользователь активен')
check(p.email_confirmed and p.trial_until, 'почта подтверждена, триал начат')

print('2. Повторный клик тем же токеном: токен сгорел, но ссылка жива')
check(not default_token_generator.check_token(u, token),
      'санити: токен невалиден после первого клика (last_login)')
c2 = Client()
r = c2.get(url)
check(r.status_code == 302 and r['Location'] == '/accounts/activated/',
      f'повторный клик -> 302 на цель (факт: {r.status_code})')

print('3. Мусорный токен по подтверждённому аккаунту: тоже успех')
c3 = Client()
r = c3.get(f'/accounts/confirm/{uid}/dhgt7z-deadbeef/')
check(r.status_code == 302 and r['Location'] == '/accounts/activated/',
      f'старая ссылка из письма -> 302 (факт: {r.status_code})')

print('4. Мусорный токен по НЕподтверждённому аккаунту: страница ошибки')
u2 = User.objects.create_user(username='pupil2', email='p2@example.com',
                              password='Zk9mQ2vLp7xR')
u2.is_active = False
u2.save()
uid2 = urlsafe_base64_encode(force_bytes(u2.pk))
c4 = Client()
r = c4.get(f'/accounts/confirm/{uid2}/dhgt7z-deadbeef/')
body = r.content.decode('utf-8')
check(r.status_code == 200 and 'недействительна' in body,
      'неподтверждённый аккаунт: тупик не открыт')
u2.refresh_from_db()
check(not u2.is_active, 'неподтверждённый аккаунт не активирован мусорным токеном')

print('5. Несуществующий uid: страница ошибки')
r = c4.get('/accounts/confirm/zzzz99/dhgt7z-deadbeef/')
check(r.status_code == 200 and 'недействительна' in r.content.decode('utf-8'),
      'битый uid: страница ошибки')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ ИДЕМПОТЕНТНОЙ АКТИВАЦИИ ПРОЙДЕНЫ')
