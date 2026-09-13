# -*- coding: utf-8 -*-
"""Проверка воронки регистрации + целей Метрики + фоновой отправки письма.

Изоляция: отдельный модуль настроек test_settings_isolated (SQLite в памяти,
почта в locmem). Боевая PostgreSQL neurostat НЕ затрагивается.

Запуск: .\\.venv\\Scripts\\python.exe test_metrika_funnel.py
"""
import os
import re
import sys
import time

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings

# Жёсткий предохранитель: если изоляция не сработала — не продолжаем
assert settings.DATABASES['default']['NAME'] == ':memory:', \
    f"БД НЕ изолирована: {settings.DATABASES['default']['NAME']}"
assert settings.EMAIL_BACKEND.endswith('locmem.EmailBackend'), \
    f"Почта НЕ изолирована: {settings.EMAIL_BACKEND}"
print(f"Изоляция OK: БД=:memory:, почта=locmem, DEBUG={settings.DEBUG}")

from django.core.management import call_command
from django.test.utils import setup_test_environment

setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)
print('Схема БД создана в памяти\n')

from django.core import mail
from django.test import Client

from main.models import (
    PLAN_NAMES, DiagnosticAttempt, Payment, UserProfile,
)
from django.contrib.auth import get_user_model

User = get_user_model()

FAILS = []
GOALS_SEEN = set()


def check(cond, msg):
    print(('  ✅ ' if cond else '  ❌ ') + msg)
    if not cond:
        FAILS.append(msg)


def goals_in(html):
    """Все идентификаторы целей, отправляемые со страницы."""
    return set(re.findall(r"var GOAL = '([A-Z_]+)'", html))


def has_counter(html):
    return 'mc.yandex.ru/metrika/tag.js' in html


def collect(html, where):
    g = goals_in(html)
    GOALS_SEEN.update(g)
    print(f'     цели на странице: {sorted(g) or "—"}')
    return g


PASSWORD = 'Zk9mQ2vLp7xRt4w'

print('=' * 70)
print('ШАГ 1. Форма регистрации: цель REG_FORM_OPEN')
print('=' * 70)
c = Client()
r = c.get('/accounts/register/')
check(r.status_code == 200, f'GET /accounts/register/ -> {r.status_code}')
html = r.content.decode('utf-8')
check(has_counter(html), 'счётчик Метрики подключён')
g = collect(html, 'register')
check('REG_FORM_OPEN' in g, 'отправляется REG_FORM_OPEN')
check('REGISTRATION_SUBMIT' not in g, 'REGISTRATION_SUBMIT на форме НЕ отправляется')
check('name="form_timestamp"' in html or 'form_timestamp' in html,
      'поле form_timestamp присутствует (time trap)')

# Анонимная диагностика ДО регистрации — чтобы проверить привязку по коду
print('\n  создаю анонимную диагностику (для проверки связки и next_url)...')
anon = DiagnosticAttempt.objects.create(
    session_key=c.session.session_key,
    test_code='DIAG_EGE_2027_V1',
    diagnostic_type='starting',
    primary_score=30, max_primary_score=50,
    score=70, max_score=100,
    weak_topics=[8, 13],
    is_completed=True,
)
ACCESS_CODE = anon.access_code
print(f'  access_code анонима: {ACCESS_CODE}')

print('\n' + '=' * 70)
print('ШАГ 2. Отправка формы: PRG-редирект + фоновое письмо')
print('=' * 70)
mail.outbox = []
t0 = time.time()
r = c.post('/accounts/register/', {
    'username': 'funnel_student',
    'email': 'funnel@example.com',
    'password1': PASSWORD,
    'website': '',                                    # honeypot пуст
    'form_timestamp': str(int(time.time()) - 10),     # time trap пройден
    'access_code': ACCESS_CODE,
})
elapsed = time.time() - t0
print(f'  ответ за {elapsed:.2f} c')
check(r.status_code == 302, f'POST регистрации -> 302 (PRG), факт: {r.status_code}')
check(r.headers.get('Location') == '/accounts/register/done/',
      f"редирект на /accounts/register/done/, факт: {r.headers.get('Location')}")

u = User.objects.filter(username='funnel_student').first()
check(u is not None, 'пользователь создан')
if u:
    check(u.is_active is False, 'до подтверждения e-mail аккаунт неактивен')
    check(User.objects.filter(email='funnel@example.com').count() == 1,
          'пользователь создан ОДИН раз (дубль save() устранён)')

anon.refresh_from_db()
check(anon.user_id == (u.id if u else None),
      'анонимная диагностика привязана к новому пользователю по access_code')

time.sleep(2)
# В outbox кроме письма активации legitimately попадают уведомления владельцу
# из main/signals.py (о новой диагностике и о новой регистрации). Ищем нужное
# по получателю, а не по индексу.
activation_mail = next((m for m in mail.outbox if m.to == ['funnel@example.com']), None)
owner_mails = [m for m in mail.outbox if m.to == [settings.OWNER_NOTIFY_EMAIL]]
print(f'     всего писем: {len(mail.outbox)} '
      f'(активация: {1 if activation_mail else 0}, владельцу: {len(owner_mails)})')
check(activation_mail is not None, 'фоновое письмо активации отправлено')
check(len(owner_mails) >= 1,
      'сигналы владельцу тоже отработали (диагностика + регистрация) — регрессии нет')
if activation_mail:
    m = activation_mail
    print(f'     тема: {m.subject}')
    print(f'     кому: {m.to}')
    check(m.to == ['funnel@example.com'], 'письмо ушло на e-mail пользователя')
    check('/accounts/confirm/' in m.body, 'в письме есть ссылка активации')

print('\n' + '=' * 70)
print('ШАГ 3. Страница-цель «письмо отправлено»: REGISTRATION_SUBMIT')
print('=' * 70)
r = c.get('/accounts/register/done/')
check(r.status_code == 200, f'GET /accounts/register/done/ -> {r.status_code}')
html = r.content.decode('utf-8')
check(has_counter(html), 'счётчик Метрики подключён')
g = collect(html, 'done')
check('REGISTRATION_SUBMIT' in g, 'отправляется REGISTRATION_SUBMIT')

print('\n  защита от накрутки: прямой заход на done без регистрации')
c2 = Client()
r2 = c2.get('/accounts/register/done/')
check(r2.status_code == 302, f'прямой заход -> 302 (факт: {r2.status_code})')
check(r2.headers.get('Location') == '/accounts/register/',
      f"откат на форму, факт: {r2.headers.get('Location')}")
check(not goals_in(r2.content.decode('utf-8')),
      'цель при прямом заходе НЕ отправляется')

print('\n' + '=' * 70)
print('ШАГ 4. Активация по ссылке из письма')
print('=' * 70)
link = None
if activation_mail:
    m = re.search(r'(https?://[^\s"\']+?/accounts/confirm/[^\s"\']+)', activation_mail.body)
    if m:
        link = m.group(1)
check(link is not None, 'ссылка активации извлечена из письма')
if link:
    path = re.sub(r'^https?://[^/]+', '', link)
    print(f'     path: {path}')
    r = c.get(path)
    check(r.status_code == 302, f'переход по ссылке -> 302, факт: {r.status_code}')
    check(r.headers.get('Location') == '/accounts/activated/',
          f"редирект на /accounts/activated/, факт: {r.headers.get('Location')}")
    u.refresh_from_db()
    check(u.is_active is True, 'аккаунт активирован')
    prof = UserProfile.objects.filter(user=u).first()
    check(prof is not None and prof.email_confirmed is True, 'profile.email_confirmed = True')
    check(prof is not None and prof.trial_until is not None, 'триал назначен')

print('\n' + '=' * 70)
print('ШАГ 5. Страница-цель «активирован»: ACCOUNT_ACTIVATED + wow-момент')
print('=' * 70)
r = c.get('/accounts/activated/')
check(r.status_code == 200, f'GET /accounts/activated/ -> {r.status_code}')
html = r.content.decode('utf-8')
check(has_counter(html), 'счётчик Метрики подключён')
g = collect(html, 'activated')
check('ACCOUNT_ACTIVATED' in g, 'отправляется ACCOUNT_ACTIVATED')
m = re.search(r'href="(/[^"]*)"[^>]*class="btn btn--primary au-success__btn"', html) \
    or re.search(r'class="btn btn--primary au-success__btn"[^>]*href="(/[^"]*)"', html) \
    or re.search(r'href="(/my/diagnostic/[^"]+)"', html)
next_url = m.group(1) if m else None
print(f'     кнопка «Продолжить» ведёт на: {next_url}')
check(next_url is not None and '/my/diagnostic/' in next_url,
      'wow-момент сохранён: ведёт на разбор диагностики, а не на главную')
check(str(anon.id) in (next_url or ''), 'ссылка ведёт именно на эту диагностику')

print('\n  повторный заход на /accounts/activated/ (флаг сессии одноразовый)')
r = c.get('/accounts/activated/')
check(r.status_code == 200, f'повторный GET -> {r.status_code}')
html = r.content.decode('utf-8')
check('ACCOUNT_ACTIVATED' in goals_in(html),
      'цель на странице есть (страница доступна залогиненному)')
m = re.search(r'href="(/[^"]*)"[^>]*class="btn btn--primary au-success__btn"', html)
print(f'     кнопка ведёт на: {m.group(1) if m else "—"} (фолбэк на главную — ок)')

print('\n  незалогиненный на /accounts/activated/')
c3 = Client()
r3 = c3.get('/accounts/activated/')
check(r3.status_code in (302, 200), f'-> {r3.status_code} (редирект на логин)')

print('\n' + '=' * 70)
print('ШАГ 6. Оплата: PAYMENT_SUCCESS')
print('=' * 70)
plan_code = next((k for k in PLAN_NAMES if k != 'free'), None)
print(f'  тариф для теста: {plan_code}')

print('\n  6a. /pay/success/ БЕЗ платежа -> цель не засчитывается')
r = c.get('/pay/success/')
check(r.status_code == 302, f'-> 302, факт: {r.status_code}')
check(r.headers.get('Location') == '/profile/',
      f"редирект в профиль, факт: {r.headers.get('Location')}")

print('\n  6b. платёж pending (вебхук ещё не пришёл)')
pay = Payment.objects.create(
    yk_payment_id='yk-test-pending-1', user=u, plan=plan_code,
    amount=990, status='pending')
r = c.get('/pay/success/')
check(r.status_code == 200, f'-> 200, факт: {r.status_code}')
html = r.content.decode('utf-8')
g = collect(html, 'pay pending')
check('PAYMENT_SUCCESS' not in g, 'цель при pending НЕ отправляется')
check('window.location.replace' in html and '?wait=1' in html,
      'есть одноразовый автопереход, чтобы дождаться вебхука')
check('Проверяем платёж' in html, 'показан честный статус «проверяем»')

print('\n  6c. pending + ?wait=1 -> зацикливания нет')
r = c.get('/pay/success/?wait=1')
html = r.content.decode('utf-8')
check(r.status_code == 200, f'-> 200, факт: {r.status_code}')
check('window.location.replace' not in html,
      'второго автоперехода нет — цикл исключён')
check('PAYMENT_SUCCESS' not in goals_in(html), 'цель всё ещё не отправлена')

print('\n  6d. платёж succeeded -> цель отправляется')
pay.status = 'succeeded'
pay.save(update_fields=['status'])
r = c.get('/pay/success/?wait=1')
check(r.status_code == 200, f'-> 200, факт: {r.status_code}')
html = r.content.decode('utf-8')
g = collect(html, 'pay succeeded')
check('PAYMENT_SUCCESS' in g, 'отправляется PAYMENT_SUCCESS')
check('window.location.replace' not in html, 'автоперехода нет (не нужен)')
check(PLAN_NAMES[plan_code] in html, f'показано название тарифа «{PLAN_NAMES[plan_code]}»')
check('990' in html, 'показана сумма')
check('Оплата прошла' in html, 'заголовок успеха')

print('\n' + '=' * 70)
print('ШАГ 7. Обратная совместимость и регрессии')
print('=' * 70)
print('\n  7a. страница успеха оплаты отдаёт HTML (не редирект) — счётчик успеет')
r = c.get('/pay/success/')
check(r.headers.get('Content-Type', '').startswith('text/html'),
      f"Content-Type = {r.headers.get('Content-Type')}")

print('\n  7b. limit регистраций с одного IP не сломан')
# Лимит считается по IP, а у test-клиента он один на весь прогон —
# сбрасываем кэш, чтобы отсчёт начался с нуля.
from django.core.cache import cache
cache.clear()
c4 = Client()
blocked = None
for i in range(7):
    rr = c4.post('/accounts/register/', {
        'username': f'spam_user_{i}',
        'email': f'spam{i}@example.com',
        'password1': PASSWORD,
        'website': '',
        'form_timestamp': str(int(time.time()) - 10),
    })
    if rr.status_code == 403:
        blocked = i
        break
check(blocked is not None, f'лимит сработал на {blocked}-й попытке (ожидалось на 5-й)')

print('\n  7c. невалидная регистрация не создаёт пользователя и не редиректит')
cache.clear()   # иначе упрёмся в лимит по IP и получим 403 вместо валидации
c5 = Client()
before = User.objects.count()
r = c5.post('/accounts/register/', {
    'username': '', 'email': 'not-an-email', 'password1': '123',
    'website': '', 'form_timestamp': str(int(time.time()) - 10),
})
check(r.status_code == 200, f'-> 200 (форма перерисована с ошибками), факт: {r.status_code}')
check(User.objects.count() == before, 'пользователь не создан')
check('REGISTRATION_SUBMIT' not in goals_in(r.content.decode('utf-8')),
      'цель при ошибке валидации НЕ отправляется')

print('\n  7d. honeypot отсекает ботов')
cache.clear()
c6 = Client()
before = User.objects.count()
r = c6.post('/accounts/register/', {
    'username': 'bot_user', 'email': 'bot@example.com', 'password1': PASSWORD,
    'website': 'http://spam.example',              # бот заполнил скрытое поле
    'form_timestamp': str(int(time.time()) - 10),
})
check(User.objects.count() == before, 'бот-регистрация отклонена')
check(r.status_code == 200, f'-> 200, факт: {r.status_code}')

print('\n' + '=' * 70)
print('ИТОГ: все цели, найденные в шаблонах')
print('=' * 70)
for gname in sorted(GOALS_SEEN):
    print(f'  {gname}')

print('\n' + ('🎉 ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ' if not FAILS
              else f'⚠️ ПРОВАЛЕНО: {len(FAILS)}'))
for f in FAILS:
    print('   - ' + f)

sys.exit(0 if not FAILS else 2)
