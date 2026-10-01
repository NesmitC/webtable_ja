# -*- coding: utf-8 -*-
"""Тест снятия платного доступа в админке (revoke_premium).

Проверяет: тариф по plan_until, активный триал (главная ловушка), роль
репетитора (доступ должен остаться), обязательность причины, журнал
админки, сохранность данных ученика и paywall после снятия.

Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.

Запуск: .\\.venv\\Scripts\\python.exe test_revoke_premium.py
"""
import os
import sys
from datetime import timedelta

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment
from django.utils import timezone

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from main.models import UserProfile, UserWord

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


User = get_user_model()
ADMIN_URL = '/admin/main/userprofile/'


def make_user(name, email=None):
    u = User.objects.create_user(
        username=name, email=email or f'{name}@example.com',
        password='Zk9mQ2vLp7xR')
    prof, _ = UserProfile.objects.get_or_create(user=u)
    return u, prof


def post_revoke(client, profiles, reason='не оплатил'):
    data = {
        'action': 'revoke_premium',
        'select_across': '0',
        'index': '0',
        '_selected_action': [str(p.pk) for p in profiles],
    }
    if reason is not None:
        data['reason'] = reason
    data['apply'] = 'Снять доступ'
    return client.post(ADMIN_URL, data)


admin = User.objects.create_superuser('boss', 'boss@example.com', 'Zk9mQ2vLp7xR')
client = Client()
client.force_login(admin)

# ===== 1. Премиум по тарифу =====
print('1. Премиум по тарифу (plan=premium, plan_until в будущем)')
u1, p1 = make_user('premium_paid')
p1.plan = 'premium'
p1.plan_until = timezone.now() + timedelta(days=30)
p1.save()
check(p1.level == 3, f'до снятия level=3 (факт {p1.level})')
post_revoke(client, [p1])
p1.refresh_from_db()
check(p1.plan == 'free', f'plan сброшен в free (факт {p1.plan})')
check(p1.plan_until is None, 'plan_until очищен')
check(p1.trial_until is None, 'trial_until очищен')
check(p1.level == 0, f'level=0 (факт {p1.level})')
check(not p1.has_access('lessons'), 'доступ к урокам закрыт')

# ===== 2. Активный триал — главная ловушка =====
print('2. Активный триал при plan=free (должен быть снят)')
u2, p2 = make_user('trial_only')
p2.plan = 'free'
p2.trial_until = timezone.now() + timedelta(days=3)
p2.save()
check(p2.level == 3, f'до снятия level=3 за счёт триала (факт {p2.level})')
post_revoke(client, [p2])
p2.refresh_from_db()
check(p2.trial_until is None, 'триал снят')
check(p2.level == 0, f'level=0 (факт {p2.level})')

# ===== 3. Триал + тариф одновременно =====
print('3. Триал и тариф одновременно')
u3, p3 = make_user('both')
p3.plan = 'premium'
p3.plan_until = timezone.now() + timedelta(days=10)
p3.trial_until = timezone.now() + timedelta(days=2)
p3.save()
post_revoke(client, [p3])
p3.refresh_from_db()
check(p3.plan == 'free' and p3.plan_until is None and p3.trial_until is None,
      'оба источника закрыты')
check(p3.level == 0, f'level=0 (факт {p3.level})')

# ===== 4. Репетитор: доступ должен остаться =====
print('4. Роль репетитора (tutor_active=True)')
u4, p4 = make_user('tutor_one')
p4.role = 'tutor'
p4.tutor_active = True
p4.plan = 'premium'
p4.plan_until = timezone.now() + timedelta(days=30)
p4.save()
r = post_revoke(client, [p4])
p4.refresh_from_db()
check(p4.plan == 'free', 'тариф сброшен')
check(p4.level == 3, f'level остался 3 (факт {p4.level})')
check(p4.has_access('lessons'), 'доступ к урокам сохранён')

# ===== 5. Причина обязательна =====
print('5. Причина обязательна')
u5, p5 = make_user('no_reason')
p5.plan = 'premium'
p5.plan_until = timezone.now() + timedelta(days=30)
p5.save()
r5 = post_revoke(client, [p5], reason='')
p5.refresh_from_db()
check(p5.plan == 'premium', f'без причины тариф НЕ тронут (факт {p5.plan})')
check(p5.plan_until is not None, 'plan_until сохранён')
check(r5.status_code == 200, f'вернули форму с ошибкой (факт {r5.status_code})')

# ===== 6. Страница подтверждения ничего не меняет (GET) =====
print('6. Страница подтверждения (без apply)')
u6, p6 = make_user('confirm_page')
p6.plan = 'premium'
p6.plan_until = timezone.now() + timedelta(days=30)
p6.trial_until = timezone.now() + timedelta(days=1)
p6.save()
r6 = client.post(ADMIN_URL, {
    'action': 'revoke_premium', 'select_across': '0',
    '_selected_action': [str(p6.pk)],
})
p6.refresh_from_db()
check(r6.status_code == 200, f'форма подтверждения показана (факт {r6.status_code})')
check('revoke_premium' in r6.content.decode('utf-8', 'replace'),
      'в ответе — наше действие')
check(p6.plan == 'premium' and p6.plan_until is not None and p6.trial_until is not None,
      'данные не изменены до подтверждения')

# ===== 7. Журнал админки с причиной =====
print('7. Журнал админки')
post_revoke(client, [p6], reason='выдан по ошибке')
entry = LogEntry.objects.filter(
    object_id=str(p6.pk), change_message__icontains='Снят платный доступ').first()
check(entry is not None, 'запись в журнале есть')
if entry:
    check('выдан по ошибке' in entry.change_message,
          f'причина в журнале: {entry.change_message[:80]}')
    check('тариф' in entry.change_message or 'триал' in entry.change_message,
          'в журнале видно, что именно было снято')

# ===== 8. Данные ученика не удаляются =====
print('8. Данные ученика сохраняются')
u8, p8 = make_user('with_words')
p8.plan = 'premium'
p8.plan_until = timezone.now() + timedelta(days=30)
p8.save()
for i in range(20):
    UserWord.objects.create(user=u8, field_name='f1', text=f'слово{i}', is_active=True)
post_revoke(client, [p8])
check(UserWord.objects.filter(user=u8).count() == 20,
      f'слова летописи на месте ({UserWord.objects.filter(user=u8).count()}/20)')
check(p8.ai_used == 0, 'квота ИИ не обнулена и не начислена')

# ===== 9. Массовое снятие =====
print('9. Массовое снятие нескольких профилей')
batch = []
for name in ('b1', 'b2', 'b3'):
    u, p = make_user(name)
    p.plan = 'premium'
    p.plan_until = timezone.now() + timedelta(days=30)
    p.save()
    batch.append(p)
post_revoke(client, batch, reason='группа закрыта')
for p in batch:
    p.refresh_from_db()
check(all(p.plan == 'free' and p.plan_until is None for p in batch),
      'все три сброшены')

# ===== 10. Paywall в реальном представлении =====
print('10. Paywall после снятия')
student = Client()
student.force_login(u1)
r10 = student.get('/ege/lessons/')
check(r10.status_code == 403, f'урок отдаёт 403 (факт {r10.status_code})')

# ===== 11. Выдача премиума по-прежнему работает (регресс) =====
print('11. Регресс: выдача премиума')
r11 = client.post(ADMIN_URL, {
    'action': 'grant_premium', 'select_across': '0',
    '_selected_action': [str(p1.pk)], 'days': '30', 'apply': 'Выдать',
})
p1.refresh_from_db()
check(p1.plan == 'premium', f'тариф выдан (факт {p1.plan})')
check(p1.plan_until is not None, 'plan_until установлен')
check(p1.level == 3, f'level=3 (факт {p1.level})')
check(LogEntry.objects.count() > 0, 'журнал пишется')

# ===== 12. Действие видно в списке =====
print('12. Действие зарегистрировано в админке')
r12 = client.get(ADMIN_URL)
html = r12.content.decode('utf-8', 'replace')
check('Снять платный доступ' in html, 'действие в выпадающем списке')
check('Выдать премиум-доступ' in html, 'выдача на месте')

print()
if fails:
    print(f'❌ ПРОВАЛЕНО {len(fails)}:')
    for f in fails:
        print('   -', f)
    sys.exit(1)
print('✅ Все проверки пройдены')
