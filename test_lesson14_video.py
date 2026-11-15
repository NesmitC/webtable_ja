# -*- coding: utf-8 -*-
"""Видео урока 14 (kinescope 3j3Zr4645Mf4RMkJajfXbx) в карточке урока.
Изоляция: test_settings_isolated (SQLite в памяти).

Запуск: .\\.venv\\Scripts\\python.exe test_lesson14_video.py
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

from main.models import UserProfile

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
u = User.objects.create_user(username='pupil', email='pupil@example.com',
                             password='Zk9mQ2vLp7xR')
prof, _ = UserProfile.objects.get_or_create(user=u)
prof.trial_until = timezone.now() + timedelta(days=5)
prof.save()

c = Client()
c.force_login(u)
lb = c.get('/ege/lessons/', HTTP_HOST='localhost').content.decode('utf-8')

i14 = lb.find('Задание 14 (орфография, слитно / раздельно / дефис)')
j14 = lb.find('Задание 15', i14)
check(i14 != -1 and j14 != -1, 'карточки 14 и 15 на странице')
seg = lb[i14:j14]
check('data-video-src="https://kinescope.io/embed/3j3Zr4645Mf4RMkJajfXbx"' in seg,
      'кнопка видео урока 14 на месте')
check('lesson-card__video-btn' in seg and 'Смотреть видео' in seg,
      'оформление кнопки как у прежних уроков')

print()
if fails:
    print(f'⚠️ ПРОВАЛЕНО: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('🎉 ВИДЕО УРОКА 14 НА МЕСТЕ')
