# main/management/commands/daily_word_watch.py
"""Оповещения владельцу «кто не ответил на Слово дня».

Два запуска в день (cron на сервере, время МСК):
  19:00  python manage.py daily_word_watch            — через 7 ч после открытия слова (12:00)
  20:30  python manage.py daily_word_watch --recheck  — только те, кто ТАК И НЕ ответил

Письмо на каждого молчуна отдельно (не сводка) на OWNER_NOTIFY_EMAIL:
учеников мало, владелец работает с каждым адресно. Любой ответ, даже
неправильный, считается активностью — тревога только за полное молчание.
Отслеживаются только РЕАЛЬНЫЕ получатели слова: привязан бот (VK/MAX/TG),
есть активная пуш-подписка или ученик сам открыл карточку (запись DailyWord
за период). «Только сайтовые», кто карточку не открывал, в отчёт не попадают.

БД только читается: записи не создаются, LLM не вызывается.
"""
import logging
from datetime import date, datetime, time as dtime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone

from main import bot_core
from main.models import DailyWord, PushSubscription, UserProfile

logger = logging.getLogger(__name__)

# предел истории молчания: запрос ограничен даже для старых аккаунтов
STREAK_WINDOW_DAYS = 60


def current_period_date(now: datetime | None = None) -> date:
    """Период слова: 12:00 МСК -> следующие 12:00 (формула bot_core.get_daily_word_state)."""
    n = now if now is not None else bot_core.now_msk()
    reveal = datetime.combine(n.date(), dtime(hour=bot_core.REVEAL_HOUR), tzinfo=bot_core.MSK)
    return n.date() if n >= reveal else n.date() - timedelta(days=1)


def delivery_channels(profile: UserProfile, push_user_ids: set) -> str:
    """Каналы, по которым ученик получает слово: для письма владельцу."""
    channels = []
    if profile.vk_id:
        channels.append('VK-бот')
    if profile.max_id or profile.max_chat_id:
        channels.append('MAX-бот')
    if profile.telegram_id:
        channels.append('Telegram-бот')
    if profile.user_id in push_user_ids:
        channels.append('Web Push')
    return ', '.join(channels) if channels else 'только сайт (открывает карточку сам)'


def silent_streak(user_id: int, period_date: date, joined: date) -> int:
    """Дни молчания подряд, включая period_date.

    День с ответом прерывает серию; день без записи считается молчанием
    (слово не открывали), но не раньше даты регистрации. Окно — 60 дней.
    """
    start = max(period_date - timedelta(days=STREAK_WINDOW_DAYS - 1), joined)
    answered = dict(
        DailyWord.objects.filter(
            user_id=user_id, period_date__gte=start, period_date__lte=period_date,
        ).values_list('period_date', 'answered')
    )
    streak = 0
    day = period_date
    while day >= start:
        if answered.get(day):
            break
        streak += 1
        day -= timedelta(days=1)
    return streak


def receives_daily(profile: UserProfile, push_user_ids: set,
                   has_record: bool) -> bool:
    """Ученик реально получает слово дня: бот-рассылка 12:00 (привязан
    мессенджер), пуш 16:00 (активная подписка) или сам открыл карточку."""
    bot_linked = bool(profile.vk_id or profile.max_chat_id or profile.telegram_id)
    return bot_linked or profile.user_id in push_user_ids or has_record


def collect_silent(period_date: date) -> list:
    """Платные + триал (level>=1), кто получает слово и не ответил.

    Исключаем staff/superuser (владелец), деактивированные аккаунты
    и тех, кому слово не доставляется и кто его не открывал.
    """
    push_user_ids = set(
        PushSubscription.objects.filter(active=True).values_list('user_id', flat=True)
    )
    items = []
    profiles = UserProfile.objects.select_related('user').filter(
        user__is_active=True, user__is_staff=False, user__is_superuser=False,
    )
    for profile in profiles:
        if not bot_core.user_can_use_bot(profile):
            continue
        user = profile.user
        daily = DailyWord.objects.filter(user_id=user.id, period_date=period_date).first()
        if daily is not None and daily.answered:
            continue
        if not receives_daily(profile, push_user_ids, daily is not None):
            continue
        joined = timezone.localtime(user.date_joined, bot_core.MSK).date()
        info = profile.subscription_info()
        plan_text = info['plan_name']
        if info.get('expiry_date'):
            plan_text += f", до {info['expiry_date']}"
        items.append({
            'profile': profile,
            'name': profile.first_name or user.first_name or user.username,
            'username': user.username,
            'email': user.email or '—',
            'plan_text': plan_text,
            'channels': delivery_channels(profile, push_user_ids),
            'question': daily.question if daily else '',
            'opened': daily is not None,
            # молчит сегодня по определению — серия не может быть нулевой
            'streak': max(1, silent_streak(user.id, period_date, joined)),
            'period_date': period_date,
        })
    return items


def build_mail(item: dict, recheck: bool, check_time: str) -> tuple:
    """Тема и текст письма владельцу об одном молчуне."""
    name = item['name']
    period = item['period_date']
    if recheck:
        subject = f'Слово дня: {name} всё ещё молчит (8,5 ч)'
        stage_line = (f'Перепроверка {check_time} МСК: ответа нет уже 8,5 часов. '
                      f'Первое оповещение было в 19:00 — ученик так и не ответил.')
    else:
        subject = f'Слово дня: {name} молчит 7 часов'
        stage_line = f'Проверка {check_time} МСК: ответа нет уже 7 часов.'
    streak_line = f'Молчит подряд: {UserProfile._ru_days(item["streak"])}'
    if item['streak'] > 1:
        since = period - timedelta(days=item['streak'] - 1)
        streak_line += f' (с {since:%d.%m})'
    word_line = item['question'] if item['opened'] else 'не открывал — записи за этот период нет'
    message = (
        f'Слово дня за {period:%d.%m.%Y} (открылось в 12:00 МСК).\n\n'
        f'Ученик: {name} (логин {item["username"]})\n'
        f'Почта ученика: {item["email"]}\n'
        f'Тариф: {item["plan_text"]}\n'
        f'Канал доставки: {item["channels"]}\n'
        f'Слово дня: {word_line}\n\n'
        f'{streak_line}\n'
        f'{stage_line}\n\n'
        f'Ответ засчитывается любой, даже неправильный: важна активность.\n'
        f'Профиль в админке: {settings.SITE_URL}/admin/main/userprofile/'
        f'{item["profile"].pk}/change/\n'
    )
    return subject, message


class Command(BaseCommand):
    help = 'Оповещения владельцу о учениках, не ответивших на Слово дня (19:00 и 20:30 МСК)'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--recheck', action='store_true',
                            help='вторая проверка 20:30: только те, кто так и не ответил')
        parser.add_argument('--dry-run', action='store_true',
                            help='показать отчёт без отправки писем')
        parser.add_argument('--period-date', default='',
                            help='дата периода YYYY-MM-DD (по умолчанию — текущий период слова)')

    def handle(self, *args, **options) -> None:
        if options['period_date']:
            try:
                period = date.fromisoformat(options['period_date'])
            except ValueError as e:
                raise CommandError(
                    f'--period-date: ожидалась дата YYYY-MM-DD, получено {options["period_date"]!r}'
                ) from e
        else:
            period = current_period_date()
        recheck = options['recheck']
        dry_run = options['dry_run']
        check_time = bot_core.now_msk().strftime('%H:%M')
        stage = 'Перепроверка 20:30' if recheck else 'Проверка 19:00'

        items = collect_silent(period)
        if not items:
            self.stdout.write(
                f'{stage} (период {period:%d.%m.%Y}): молчунов среди получателей нет, писем нет.')
            return

        sent = failed = 0
        for item in items:
            subject, message = build_mail(item, recheck, check_time)
            if dry_run:
                self.stdout.write(f'--- {subject}\n{message}')
                continue
            try:
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL,
                          [settings.OWNER_NOTIFY_EMAIL], fail_silently=False)
                sent += 1
            except Exception as e:  # noqa: BLE001 — сбой одного письма не останавливает остальные
                failed += 1
                logger.error(f'daily_word_watch: письмо о {item["username"]} не отправлено: {e}')

        if dry_run:
            self.stdout.write(
                f'{stage} (период {period:%d.%m.%Y}): молчунов {len(items)}, '
                f'dry-run — письма не отправлялись.')
        else:
            self.stdout.write(
                f'{stage} (период {period:%d.%m.%Y}): молчунов {len(items)}, '
                f'отправлено {sent}, ошибок {failed}.')