# -*- coding: utf-8 -*-
"""Отправка «Слова дня» пушем (Web Push/PWA). systemd-таймер: ежедневно 16:00 МСК.

Слово берётся из общего состояния DailyWord (bot_core.get_daily_word_state):
если слово периода ещё не сгенерировано (ученик не заходил на сайт после
12:00) — генерируется здесь, ровно как в bot_daily_broadcast для ботов.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from main import push


class Command(BaseCommand):
    help = 'Разослать «Слово дня» пушем всем активным PWA-подпискам'

    def add_arguments(self, parser):
        parser.add_argument('--user', default=None,
                            help='username или email — тестовая отправка одному')
        parser.add_argument('--dry-run', action='store_true',
                            help='сформировать слова и посчитать, не отправляя')

    def handle(self, *args, **options):
        user = None
        if options['user']:
            User = get_user_model()
            user = (User.objects.filter(username=options['user']).first()
                    or User.objects.filter(email__iexact=options['user']).first())
            if not user:
                raise CommandError(f'пользователь не найден: {options["user"]}')
        stats = push.send_daily_words(user=user, dry_run=options['dry_run'])
        line = (f"Пуш-рассылка: отправлено={stats['sent']} "
                f"пропущено={stats['skipped']} ошибок={stats['failed']} "
                f"деактивировано={stats['deactivated']} "
                f"пользователей={stats['users']}")
        if stats.get('error'):
            line += f" | {stats['error']}"
        self.stdout.write(line)
