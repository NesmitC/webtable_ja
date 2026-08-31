"""Тест «объясни проще». Запуск: python test_simple.py"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()

from main.assistant import get_orchestrator

orch = get_orchestrator()
q = 'что такое причастный оборот?'

print("=== Обычный ответ ===")
r1 = orch.get_response(None, q, platform='test')
print("simplifiable:", r1.get('simplifiable'))
print("ответ:", r1['reply'][:180].replace('\n', ' | '))

print("\n=== Упрощённый ответ ===")
r2 = orch.get_response(None, q, platform='test', simplify=True)
print("simplifiable:", r2.get('simplifiable'))
print("ответ:", r2['reply'][:180].replace('\n', ' | '))

print("\n=== Ответы разные? ===", r1['reply'] != r2['reply'])

print("\n=== Повтор упрощённого (кэш) ===")
r3 = orch.get_response(None, q, platform='test', simplify=True)
print("совпал с первым упрощённым:", r3['reply'] == r2['reply'])

from main.models import BotLog
n, _ = BotLog.objects.filter(platform='test').delete()
print('logs cleaned:', n)
