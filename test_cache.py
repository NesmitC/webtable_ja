"""Проверка кэша LLM и журнала диалогов. Запуск: python test_cache.py"""
import os
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
import django
django.setup()

from main.llm_utils import cached_llm
from main.models import LLMCache, BotLog

SYSTEM = ("Ты — репетитор русского языка. Объясни термин в 2 предложения, "
          "без маркдауна.")

print("=== 1. Первый вызов (пишет в кэш) ===")
t = time.time()
a1 = cached_llm('test', 'что такое эпитет', SYSTEM, max_tokens=200)
print(f"   {time.time() - t:.1f} с | {a1[:120]}")

print("=== 2. Второй вызов (должен быть мгновенным и без ** ) ===")
t = time.time()
a2 = cached_llm('test', 'Что такое ЭПИТЕТ?!', SYSTEM, max_tokens=200)
dt = time.time() - t
print(f"   {dt:.2f} с | {a2[:120]}")
print("   из кэша:", dt < 0.5 and a1 == a2)
print("   без markdown:", '**' not in a2)
row = LLMCache.objects.filter(category='test').first()
print("   hits:", row.hits if row else None)

print("=== 3. Оркестратор пишет журнал ===")
from main.assistant import get_orchestrator
orch = get_orchestrator()
t = time.time()
res = orch.get_response(None, 'что такое метонимия?', platform='site')
print(f"   {time.time() - t:.1f} с | категория: {res['intent']}")
t = time.time()
res2 = orch.get_response(None, 'что такое метонимия?', platform='site')
print(f"   повтор {time.time() - t:.1f} с | категория: {res2['intent']}")
print("   ответ без markdown:", '**' not in res2['reply'])

log = BotLog.objects.order_by('-created_at').first()
print("   последний лог:", log.platform, '|', log.category, '|', log.question[:40])
print("   всего логов:", BotLog.objects.count())

# уборка тестового кэша
LLMCache.objects.filter(category='test').delete()
print("\nГотово.")
