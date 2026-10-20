# -*- coding: utf-8 -*-
"""Тест уникальности email при регистрации: 1 адрес — 1 аккаунт.

Проверяет: первая регистрация успешна и email нормализуется; повторная
регистрация на тот же адрес (в т.ч. другим регистром и с пробелами)
отклоняется с сообщением «уже зарегистрирован» и не создаёт аккаунт;
email обязателен; другой email регистрируется как обычно.

Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.
Запуск: .\\.venv\\Scripts\\python.exe test_register_email_unique.py
"""
import os
import sys
import time

# Консоль Windows по умолчанию cp1251 — эмодзи отчёта её роняют.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

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

from django.contrib.auth.models import User

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


REGISTER_URL = '/accounts/register/'
PASSWORD = 'Str0ng!Passw0rd'


def post_register(username, email, ip='10.0.0.7'):
    """POST регистрации в обход антибот-ловушек (honeypot пуст, форма «заполнена» за 10 c)."""
    return Client().post(
        REGISTER_URL,
        data={
            'username': username,
            'email': email,
            'password1': PASSWORD,
            'website': '',
            'form_timestamp': int(time.time()) - 10,
        },
        REMOTE_ADDR=ip,
    )


def email_errors(response):
    return list(response.context['form'].errors.get('email', []))


# ===== 1. Первая регистрация — успешна =====
print('1. Первая регистрация на адрес')
r = post_register('first_user', 'Dup@Test.ru')
check(r.status_code == 302, f'успех → редирект (получен {r.status_code})')
u = User.objects.filter(username='first_user').first()
check(u is not None and u.email == 'dup@test.ru', 'email сохранён нормализованным (нижний регистр)')
check(u is not None and not u.is_active, 'аккаунт неактивен до подтверждения почты')

# ===== 2. Повторная регистрация на тот же адрес — отклон =====
print('2. Повторная регистрация на тот же email')
r2 = post_register('second_user', 'dup@test.ru')
check(r2.status_code == 200, 'форма перерисована с ошибкой')
errs = email_errors(r2)
check(any('уже зарегистрирован' in e for e in errs),
      f'сообщение «уже зарегистрирован» в ошибке поля email: {errs}')
check(not User.objects.filter(username='second_user').exists(), 'второй аккаунт НЕ создан')

# ===== 3. Другой регистр и пробелы — тоже отклон =====
print('3. Варианты регистра и пробелов')
for i, variant in enumerate(('DUP@TEST.RU', '  dup@test.ru  '), start=1):
    name = f'variant_user_{i}'
    rv = post_register(name, variant)
    check(rv.status_code == 200 and email_errors(rv), f'{variant!r} отклонён')
    check(not User.objects.filter(username=name).exists(), f'{variant!r} аккаунт НЕ создан')

# ===== 4. Email обязателен =====
print('4. Регистрация без email')
r4 = post_register('no_email_user', '')
check(r4.status_code == 200 and email_errors(r4), 'пустой email отклонён')
check(not User.objects.filter(username='no_email_user').exists(), 'аккаунт без email НЕ создан')

# ===== 5. Другой адрес — регистрация как обычно =====
print('5. Другой email регистрируется')
r5 = post_register('other_user', 'other@test.ru')
check(r5.status_code == 302, f'успех → редирект (получен {r5.status_code})')
check(User.objects.filter(username='other_user').exists(), 'аккаунт на другой адрес создан')

print()
if fails:
    print(f'❌ ПРОВАЛЕНО проверок: {len(fails)}')
    sys.exit(1)
print('✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ')
