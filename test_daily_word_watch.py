# -*- coding: utf-8 -*-
"""Оповещения владельцу «Слово дня: кто молчит» (daily_word_watch).

19:00 МСК — письмо на каждого молчуна (7 ч после открытия слова в 12:00);
20:30 — перепроверка, только те, кто ТАК И НЕ ответил. Любой ответ, даже
неправильный, = активность, письма нет. Бесплатный тариф, staff/superuser
и деактивированные аккаунты не отслеживаются. Ученик без записи за период
(«только сайт», не открывал) — тоже молчит. БД команда не пишет.
Изоляция: test_settings_isolated (SQLite в памяти, письма в outbox).

Запуск: .\\.venv\\Scripts\\python.exe test_daily_word_watch.py
"""
import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

import io
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management.base import CommandError
from django.utils import timezone

from main import bot_core
from main.management.commands.daily_word_watch import current_period_date
from main.models import DailyWord, PushSubscription

User = get_user_model()
MSK = bot_core.MSK
# фиксированное «сейчас»: тесты не зависят от времени и даты запуска
NOW = datetime(2026, 11, 16, 19, 0, tzinfo=MSK)
NOW_UTC = NOW.astimezone(dt_timezone.utc)
PERIOD = NOW.date()
JOINED = datetime(2026, 11, 1, 9, 0, tzinfo=MSK)
QUESTION = 'Как пишется правильно:\nорг😊единица'

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


def make_user(username, plan='self', email='', staff=False, active=True,
              joined=JOINED, **profile_kwargs):
    u = User.objects.create_user(username, email=email, password='x', is_staff=staff)
    u.date_joined = joined
    u.is_active = active
    u.save()
    p = u.profile  # создаётся сигналом post_save
    p.plan = plan
    if plan != 'free':
        p.plan_until = NOW + timedelta(days=10)
    for k, v in profile_kwargs.items():
        setattr(p, k, v)
    p.save()
    return u


def make_word(user, day, answered=False, correctly=None):
    return DailyWord.objects.create(
        user=user, period_date=day, question=QUESTION,
        answered=answered, answered_correctly=correctly,
        answered_at=NOW if answered else None)


def run_watch(*extra):
    out = io.StringIO()
    call_command('daily_word_watch', *extra, stdout=out)
    return out.getvalue()


def daily_mails():
    # письма о регистрациях (сигналы) отсеиваем по теме
    return [m for m in mail.outbox if m.subject.startswith('Слово дня')]


def bodies():
    return '\n'.join(m.body for m in daily_mails())


with mock.patch('main.bot_core.now_msk', return_value=NOW), \
        mock.patch('django.utils.timezone.now', return_value=NOW_UTC):

    print('=== Подготовка учеников ===')
    silent = make_user('masha_silent', email='masha@example.com',
                       first_name='Маша', vk_id=111)
    PushSubscription.objects.create(user=silent, endpoint='https://push.example/1',
                                    p256dh='k', auth='a', platform='android')
    make_word(silent, PERIOD)                          # сегодня молчит
    make_word(silent, PERIOD - timedelta(days=1))      # вчера молчит
    make_word(silent, PERIOD - timedelta(days=2))      # позавчера молчит
    make_word(silent, PERIOD - timedelta(days=3), answered=True, correctly=True)

    wrong = make_user('petya_wrong', plan='free')      # триал = полный доступ
    wrong.profile.trial_until = NOW + timedelta(days=3)
    wrong.profile.save()
    make_word(wrong, PERIOD, answered=True, correctly=False)  # неправильно, но ответил

    right = make_user('olya_right', plan='premium')
    make_word(right, PERIOD, answered=True, correctly=True)

    noopen = make_user('sasha_noopen')                 # записи за сегодня нет — «только сайт»
    make_word(noopen, PERIOD - timedelta(days=1))
    make_word(noopen, PERIOD - timedelta(days=2), answered=True, correctly=True)

    make_user('free_user', plan='free')                # тариф «0» — слова дня нет
    make_user('boss', staff=True)                      # владелец
    su = User.objects.create_superuser('root', email='root@example.com', password='x')
    su.profile.plan = 'self'
    su.profile.plan_until = NOW + timedelta(days=10)
    su.profile.save()
    make_user('gone_user', active=False)               # деактивирован

    late = make_user('late_user')                      # ответит в 19:30 — между проверками
    make_word(late, PERIOD)
    still = make_user('still_user')                    # молчит на обеих проверках
    make_word(still, PERIOD)
    newbie = make_user('newbie', joined=NOW - timedelta(hours=1))  # зарегистрировался сегодня

    words_before = DailyWord.objects.count()

    print('=== Первая проверка 19:00 ===')
    mail.outbox.clear()
    out1 = run_watch()
    mails1 = daily_mails()
    b1 = bodies()

    check(len(mails1) == 5, f'писем ровно по числу молчунов: 5 (получено {len(mails1)})')
    check(all(m.to == [settings.OWNER_NOTIFY_EMAIL] for m in mails1),
          'все письма на OWNER_NOTIFY_EMAIL')
    check(settings.OWNER_NOTIFY_EMAIL == 'a_timof@mail.ru', 'адрес владельца = a_timof@mail.ru')
    check(len({m.subject for m in mails1}) == 5, 'отдельное письмо на каждого, не сводка')
    check('16.11.2026' in out1, 'период по умолчанию = сегодня (после 12:00 МСК)')

    check('petya_wrong' not in b1, 'неправильный ответ = активность, письма нет')
    check('olya_right' not in b1, 'правильный ответ — письма нет')
    check('free_user' not in b1, 'бесплатный тариф «0» не отслеживается')
    check('boss' not in b1 and 'root' not in b1, 'staff и superuser исключены')
    check('gone_user' not in b1, 'деактивированный аккаунт исключён')

    masha_mail = next(m for m in mails1 if 'masha_silent' in m.body)
    check(masha_mail.subject == 'Слово дня: Маша молчит 7 часов',
          'тема 19:00: имя + «молчит 7 часов»')
    check('логин masha_silent' in masha_mail.body and 'masha@example.com' in masha_mail.body,
          'в письме логин и почта ученика')
    check('VK-бот' in masha_mail.body and 'Web Push' in masha_mail.body,
          'каналы доставки: VK-бот + Web Push')
    check('орг😊единица' in masha_mail.body, 'само слово дня в письме')
    check('«Я сам», до 26.11.2026' in masha_mail.body, 'тариф и срок действия')
    check('Молчит подряд: 3 дня (с 14.11)' in masha_mail.body,
          'серия молчания 3 дня, ответ 13.11 прервал серию')
    check(f'/admin/main/userprofile/{silent.profile.pk}/change/' in masha_mail.body,
          'ссылка на профиль в админке')

    noopen_mail = next(m for m in mails1 if 'sasha_noopen' in m.body)
    check('не открывал' in noopen_mail.body and 'только сайт' in noopen_mail.body,
          'без записи за период: «не открывал», канал «только сайт»')
    check('Молчит подряд: 2 дня (с 15.11)' in noopen_mail.body,
          'серия для «не открывавшего»: сегодня + вчера')

    newbie_mail = next(m for m in mails1 if 'newbie' in m.body)
    check('Молчит подряд: 1 день' in newbie_mail.body and '(с ' not in newbie_mail.body,
          'новичок: серия 1 день, не раньше регистрации')

    check(DailyWord.objects.count() == words_before, 'команда не создаёт записей в БД (read-only)')

    print('=== dry-run ===')
    mail.outbox.clear()
    out_dry = run_watch('--dry-run')
    check(len(daily_mails()) == 0, 'dry-run: письма не отправляются')
    check('молчунов 5' in out_dry and 'dry-run' in out_dry, 'dry-run: отчёт в stdout')
    check('Слово дня: Маша молчит 7 часов' in out_dry, 'dry-run показывает темы и тексты')

    print('=== Период и аргументы ===')
    check(current_period_date(NOW.replace(hour=10)) == PERIOD - timedelta(days=1),
          'до 12:00 МСК период = вчерашний')
    out_past = run_watch('--period-date', '2026-11-15')
    check('15.11.2026' in out_past, '--period-date задаёт период явно')
    try:
        run_watch('--period-date', 'не-дата')
        check(False, 'битая дата --period-date → CommandError')
    except CommandError:
        check(True, 'битая дата --period-date → CommandError')

    print('=== Перепроверка 20:30 ===')
    # late отвечает в 19:30 — неправильно, но отвечает
    dw = DailyWord.objects.get(user=late, period_date=PERIOD)
    dw.answered = True
    dw.answered_correctly = False
    dw.answered_at = NOW + timedelta(minutes=30)
    dw.save()

    mail.outbox.clear()
    with mock.patch('main.bot_core.now_msk', return_value=NOW.replace(hour=20, minute=30)):
        out2 = run_watch('--recheck')
    mails2 = daily_mails()
    b2 = bodies()

    check(len(mails2) == 4, f'второе письмо только про так и не ответивших: 4 (получено {len(mails2)})')
    check('late_user' not in b2, 'ответил между 19:00 и 20:30 (пусть неправильно) — второго письма нет')
    still_mail = next(m for m in mails2 if 'still_user' in m.body)
    check(still_mail.subject == 'Слово дня: still_user всё ещё молчит (8,5 ч)',
          'тема 20:30: «всё ещё молчит (8,5 ч)»')
    check('Первое оповещение было в 19:00' in still_mail.body,
          'в письме 20:30 упомянуто первое оповещение')
    check('Перепроверка 20:30' in out2, 'в stdout стадия перепроверки')

    print('=== Все ответили ===')
    for u in (silent, noopen, still, newbie):
        # у «только сайтовых» записи за период может не быть — создаём отвеченную
        DailyWord.objects.update_or_create(
            user=u, period_date=PERIOD,
            defaults={'question': QUESTION, 'answered': True,
                      'answered_correctly': True, 'answered_at': NOW})
    mail.outbox.clear()
    out3 = run_watch('--recheck')
    check(len(daily_mails()) == 0 and 'все ответили' in out3,
          'все ответили — писем нет')

print()
if fails:
    print(f'ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print(' -', f)
    raise SystemExit(1)
print('ВСЕ ПРОВЕРКИ ЗЕЛЁНЫЕ')