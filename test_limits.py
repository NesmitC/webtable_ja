"""Тест месячных квот ИИ в ботах. Запуск: python test_limits.py"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from main import bot_core
from main.models import UserProfile, BotLog

User = get_user_model()
month = timezone.now().strftime('%Y-%m')


def make_user(name, plan=None, ai_used=0, trial=False, vk_id=None):
    u, _ = User.objects.get_or_create(username=name)
    p, _ = UserProfile.objects.get_or_create(user=u)
    p.plan = plan or 'free'
    if plan and plan != 'free':
        p.plan_until = timezone.now() + timedelta(days=30)
    if trial:
        p.trial_until = timezone.now() + timedelta(days=5)
    p.ai_month = month
    p.ai_used = ai_used
    if vk_id:
        p.vk_id = vk_id
    p.save()
    return u, p


print("=== 1. Free, квота исчерпана (10/10) ===")
u, p = make_user('lim_free_full', ai_used=10, vk_id=900001)
before = BotLog.objects.count()
r = bot_core.free_chat('vk', 900001, 'что такое метафора')
print("reply:", r['reply'][:90])
print("оркестратор НЕ вызван:", BotLog.objects.count() == before)

print("\n=== 2. Free, 8/10 → ответ + треккер остатка ===")
u, p = make_user('lim_free_8', ai_used=8, vk_id=900002)
r = bot_core.free_chat('vk', 900002, 'тарифы')   # rule-based, без LLM — быстро
p.refresh_from_db()
print("ai_used после:", p.ai_used)
print("reply хвост:", r['reply'][-90:])

print("\n=== 3. Премиум: счётчик не трогается ===")
u, p = make_user('lim_prem', plan='premium', ai_used=0, vk_id=900003)
r = bot_core.free_chat('vk', 900003, 'тарифы')
p.refresh_from_db()
print("ai_used после:", p.ai_used, "(должно остаться 0)")
print("ответ пришёл:", bool(r['reply']))

print("\n=== 4. Триал = полный доступ ===")
u, p = make_user('lim_trial', trial=True, ai_used=0, vk_id=900004)
r = bot_core.free_chat('vk', 900004, 'тарифы')
print("ответ пришёл:", bool(r['reply']))

# чистим тестовых юзеров
for name in ('lim_free_full', 'lim_free_8', 'lim_prem', 'lim_trial'):
    User.objects.filter(username=name).delete()
print("\nГотово.")
