# -*- coding: utf-8 -*-
"""Тест скрытого рубежа cp9 (задания 1–9, скрыт 2026-11-02):
маршрут редиректит на уроки, карточки на странице уроков нет, урок 10 открыт
без рубежа, на странице результата cp9 нет кнопки пересдачи (у cp91/cp92 кнопка
ведёт на свой рубеж — попутный фикс старой ошибки ссылки на cp9).
Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_checkpoint.py
"""
import os
import sys
from datetime import timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main.models import CheckpointAttempt, UserProfile

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()


def make_user(name):
    u = User.objects.create_user(username=name, email=f'{name}@example.com',
                                 password='Zk9mQ2vLp7xR')
    prof, _ = UserProfile.objects.get_or_create(user=u)
    prof.trial_until = timezone.now() + timedelta(days=5)
    prof.save()
    return u


u = make_user('pupil')
c = Client()
c.force_login(u)

print('1. Маршрут скрыт: GET и POST редиректят на уроки')
r = c.get('/ege/checkpoint/9/')
check(r.status_code == 302 and r['Location'] == '/ege/lessons/',
      f"GET /ege/checkpoint/9/ -> 302 на уроки (факт: {r.status_code} {r.get('Location')})")
check('checkpoint_9' not in c.session, 'сессия рубежа не создаётся')
r = c.post('/ege/checkpoint/9/', data='{"answers": {}}',
           content_type='application/json')
check(r.status_code == 302, f'POST -> 302 (факт: {r.status_code})')
check(CheckpointAttempt.objects.count() == 0, 'новые попытки не пишутся')

print('2. Страница уроков: карточки cp9 нет, урок 10 открыт без рубежа')
lb = c.get('/ege/lessons/').content.decode('utf-8')
check('Рубежный тест: задания 1–9' not in lb, 'карточки рубежа 1–9 нет')
check('href="/ege/checkpoint/9/"' not in lb, 'ссылки на скрытый рубеж нет')
i10 = lb.find('Задание 10 (орфография, приставки)')
j10 = lb.rfind('<div class="lesson-card lesson-card--', 0, i10)
check(i10 != -1 and 'lesson-card--locked' in lb[j10:i10],
      'урок 10 закрыт без сдачи финального рубежа задания 9 (cp94)')
check('Откроется после рубежного теста</span>' not in lb,
      'статуса «откроется после рубежа» без суффикса (cp9) нет')

print('3. Страница результата: cp9 без пересдачи, cp91/cp92 на свой рубеж')
a9 = CheckpointAttempt.objects.create(
    user=u, checkpoint_code='cp9', passed=False, total_tasks=6,
    correct_count=0, error_count=6, results_data={'1': {'correct': False}})
vb = c.get(f'/ege/checkpoint/9/result/{a9.id}/').content.decode('utf-8')
check('Что повторить' in vb and 'Пересдать рубеж' not in vb,
      'cp9: рекомендации есть, кнопки пересдачи нет')
a91 = CheckpointAttempt.objects.create(
    user=u, checkpoint_code='cp91', passed=False, total_tasks=6,
    correct_count=5, error_count=1, results_data={'5': {'correct': False}})
vb = c.get(f'/ege/checkpoint/9/result/{a91.id}/').content.decode('utf-8')
check('href="/ege/checkpoint/9-1/"' in vb and 'Пересдать рубеж' in vb,
      'cp91: пересдача ведёт на рубеж 9-1')
a92 = CheckpointAttempt.objects.create(
    user=u, checkpoint_code='cp92', passed=False, total_tasks=10,
    correct_count=9, error_count=1, results_data={'92': {'correct': False}})
vb = c.get(f'/ege/checkpoint/9/result/{a92.id}/').content.decode('utf-8')
check('href="/ege/checkpoint/9-2/"' in vb and 'Пересдать рубеж' in vb,
      'cp92: пересдача ведёт на рубеж 9-2')

print('4. История и статистика остаются')
sb = c.get('/statistic/').content.decode('utf-8')
check('Рубежные тесты: сдано' in sb, 'карточка рубежей на статистике')
check('История прохождений рубежей' in sb, 'таблица прохождений на месте')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВСЕ ПРОВЕРКИ СКРЫТОГО РУБЕЖА CP9 ПРОЙДЕНЫ')
