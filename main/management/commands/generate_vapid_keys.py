# -*- coding: utf-8 -*-
"""Генерирует пару VAPID-ключей для Web Push и дописывает их в .env.

Приватный ключ НЕ печатается и НЕ логируется. Идемпотентно: если в .env уже
есть VAPID_PRIVATE_KEY — ничего не делает. После генерации нужен перезапуск
gunicorn (systemctl kill -s HUP gunicorn), чтобы settings подхватили ключи.

Запуск: python manage.py generate_vapid_keys [--env-file PATH]
"""
import base64

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Сгенерировать VAPID-ключи Web Push и дописать в .env (идемпотентно)'

    def add_arguments(self, parser):
        parser.add_argument('--env-file', default=None,
                            help='Путь к .env (по умолчанию — корень проекта)')

    def handle(self, *args, **options):
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat)

        env_path = options['env_file'] or (settings.BASE_DIR / '.env')
        with open(env_path, encoding='utf-8') as f:
            content = f.read()
        if 'VAPID_PRIVATE_KEY=' in content:
            self.stdout.write('VAPID-ключи уже есть в .env — делать нечего.')
            return

        # VAPID: приватный — скаляр кривой P-256 (32 байта), публичный —
        # несжатая точка (65 байт), оба в base64url. Формат понимает pywebpush.
        key = ec.generate_private_key(ec.SECP256R1())
        priv = base64.urlsafe_b64encode(
            key.private_numbers().private_value.to_bytes(32, 'big')).decode()
        pub = base64.urlsafe_b64encode(key.public_key().public_bytes(
            Encoding.X962, PublicFormat.UncompressedPoint)).decode()

        prefix = '' if (not content or content.endswith('\n')) else '\n'
        with open(env_path, 'a', encoding='utf-8') as f:
            f.write(f'{prefix}\n'
                    '# Web Push (PWA): VAPID-ключи (manage.py generate_vapid_keys)\n'
                    f'VAPID_PUBLIC_KEY={pub}\n'
                    f'VAPID_PRIVATE_KEY={priv}\n')
        self.stdout.write(self.style.SUCCESS(
            'VAPID-ключи дописаны в .env (приватный не печатается). '
            'Перезапустите gunicorn: systemctl kill -s HUP gunicorn. '
            'Публичный ключ сайт отдаёт на /api/push/config/.'))
