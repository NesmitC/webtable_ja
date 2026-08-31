"""Сквозной тест free_chat (общий мозг ботов). Запуск: python test_freechat.py"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()

from main import bot_core

print("=== Гость (не привязан) ===")
r = bot_core.free_chat('vk', 999000111, 'что такое метафора')
print("allowed:", r['allowed'], "| linked:", r['linked'])
print("reply:", r['reply'][:150])

print("\n=== Гость: лимит 10/час ===")
for i in range(12):
    r = bot_core.free_chat('vk', 999000222, 'привет')
last = r['reply']
print("после 12 быстрых сообщений:", last[:80])

print("\n=== Логи бота с платформой vk ===")
from main.models import BotLog
for log in BotLog.objects.filter(platform='vk').order_by('-created_at')[:3]:
    print("  ", log.category, '|', log.question[:40])

print("\nГотово.")
