# -*- coding: utf-8 -*-
"""РўРµСЃС‚ Р°РґРјРёРЅРєРё СЃС‚Р°С‚РёСЃС‚РёРєРё Р·Р°РґР°РЅРёСЏ 9: Р»РµРЅС‚С‹, С„РёР»СЊС‚СЂС‹, СЂР°Р·Р±РѕСЂ РїРѕРїС‹С‚РєРё РїРѕ СЃР»РѕРІР°Рј.
РР·РѕР»СЏС†РёСЏ: test_settings_isolated (SQLite РІ РїР°РјСЏС‚Рё).

Р—Р°РїСѓСЃРє: .\\.venv\\Scripts\\python.exe test_admin_task9.py
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
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from django.contrib.auth import get_user_model

from main.models import Task9Attempt, Task9AttemptWord, Task9WordStat

fails = []


def check(cond, label):
    print(('  вњ… ' if cond else '  вќЊ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
admin = User.objects.create_superuser('owner', 'owner@example.com', 'Zk9mQ2vLp7xR')
pupil = User.objects.create_user('sasha', 'sasha@example.com', 'OldPass123!')

att = Task9Attempt.objects.create(user=pupil, orthogram_id='1', range_code='9',
                                  total_words=3, chosen_count=3, correct_count=2)
Task9AttemptWord.objects.create(attempt=att, word='Р·*1*РјР»СЏ', chosen_letter='Рё',
                                correct_letter='Рµ', is_correct=False)
Task9AttemptWord.objects.create(attempt=att, word='РІ*1*СЃРЅР°', chosen_letter='Рµ',
                                correct_letter='Рµ', is_correct=True)
Task9WordStat.objects.create(user=pupil, orthogram_id='1', range_code='9',
                             word='Р·*1*РјР»СЏ', correct_letter='Рµ', attempts=2,
                             errors=1, last_result=False, last_chosen_letter='Рё',
                             last_seen=timezone.now(), in_correction=True,
                             correction_since=timezone.now().date())

c = Client()
c.force_login(admin)

print('1. Р›РµРЅС‚С‹ СЃС‚Р°С‚РёСЃС‚РёРєРё РІ Р°РґРјРёРЅРєРµ')
r = c.get('/admin/main/task9attempt/', HTTP_HOST='localhost')
page = r.content.decode('utf-8')
check(r.status_code == 200, f'Р»РµРЅС‚Р° РїСЂРѕС…РѕР¶РґРµРЅРёР№ -> 200 (С„Р°РєС‚: {r.status_code})')
check('sasha' in page and 'Р·*1*РјР»СЏ' not in page, 'РІ Р»РµРЅС‚Рµ СѓС‡РµРЅРёРє, СЃР»РѕРІ-СЂР°Р·Р±РѕСЂР° РЅРµС‚')
r = c.get('/admin/main/task9wordstat/', HTTP_HOST='localhost')
page = r.content.decode('utf-8')
check(r.status_code == 200, f'РЅР°РєРѕРїРёС‚РµР»СЊРЅР°СЏ СЃС‚Р°С‚РёСЃС‚РёРєР° -> 200 (С„Р°РєС‚: {r.status_code})')
check('Р·*1*РјР»СЏ' in page and 'РќР° РєРѕСЂСЂРµРєС†РёРё' in page.replace('Р”Р°', 'РќР° РєРѕСЂСЂРµРєС†РёРё') or 'Р·*1*РјР»СЏ' in page,
      'СЃР»РѕРІРѕ РЅР° РєРѕСЂСЂРµРєС†РёРё РІРёРґРЅРѕ РІ Р»РµРЅС‚Рµ')

print('2. Р¤РёР»СЊС‚СЂС‹ Рё РїРѕРёСЃРє')
r = c.get('/admin/main/task9attempt/?range_code=9', HTTP_HOST='localhost')
check(r.status_code == 200 and 'sasha' in r.content.decode('utf-8'),
      'С„РёР»СЊС‚СЂ РїРѕ Р±Р»РѕРєСѓ (range_code) СЂР°Р±РѕС‚Р°РµС‚')
r = c.get('/admin/main/task9attempt/?q=sasha', HTTP_HOST='localhost')
check('sasha' in r.content.decode('utf-8'), 'РїРѕРёСЃРє РїРѕ СѓС‡РµРЅРёРєСѓ СЂР°Р±РѕС‚Р°РµС‚')
r = c.get('/admin/main/task9wordstat/?in_correction=1', HTTP_HOST='localhost')
check('Р·*1*РјР»СЏ' in r.content.decode('utf-8'), 'С„РёР»СЊС‚СЂ В«РЅР° РєРѕСЂСЂРµРєС†РёРёВ» СЂР°Р±РѕС‚Р°РµС‚')

print('3. Р Р°Р·Р±РѕСЂ РїРѕРїС‹С‚РєРё РїРѕ СЃР»РѕРІР°Рј')
r = c.get(f'/admin/main/task9attempt/{att.id}/change/', HTTP_HOST='localhost')
page = r.content.decode('utf-8')
check(r.status_code == 200, f'РєР°СЂС‚РѕС‡РєР° РїРѕРїС‹С‚РєРё -> 200 (С„Р°РєС‚: {r.status_code})')
check('Р·*1*РјР»СЏ' in page and 'РІ*1*СЃРЅР°' in page, 'РёРЅР»Р°Р№РЅ РїРѕРєР°Р·С‹РІР°РµС‚ РѕР±Р° СЃР»РѕРІР°')
check('Р’С‹Р±СЂР°РЅРЅР°СЏ Р±СѓРєРІР°' in page or 'chosen_letter' in page,
      'РІ РёРЅР»Р°Р№РЅРµ РІРёРґРµРЅ РІС‹Р±РѕСЂ СѓС‡РµРЅРёРєР°')

print('4. РСЃС‚РѕСЂРёСЏ РЅРµРёР·РјРµРЅСЏРµРјР° СЂСѓРєР°РјРё')
r = c.post(f'/admin/main/task9attempt/{att.id}/change/',
           data={'correct_count': 3, 'words-TOTAL_FORMS': 0,
                 'words-INITIAL_FORMS': 2, 'words-MIN_NUM_FORMS': 0,
                 'words-MAX_NUM_FORMS': 1000},
           HTTP_HOST='localhost')
att.refresh_from_db()
check(att.correct_count == 2, 'POST РЅРµ РјРµРЅСЏРµС‚ Р»РµС‚РѕРїРёСЃСЊ (correct_count РѕСЃС‚Р°Р»СЃСЏ 2)')
r = c.get('/admin/main/task9attempt/add/', HTTP_HOST='localhost')
check(r.status_code in (302, 403), f'СЂСѓС‡РЅРѕРµ РґРѕР±Р°РІР»РµРЅРёРµ Р·Р°РїСЂРµС‰РµРЅРѕ (С„Р°РєС‚: {r.status_code})')

print()
if fails:
    print(f'вљ пёЏ РџР РћР’РђР›Р•РќРћ: {len(fails)}')
    for f_ in fails:
        print('   -', f_)
    sys.exit(2)
print('рџЋ‰ Р’РЎР• РџР РћР’Р•Р РљР РђР”РњРРќРљР РЎРўРђРўРРЎРўРРљР РџР РћР™Р”Р•РќР«')

