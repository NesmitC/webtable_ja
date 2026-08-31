# main/management/commands/bot_proactive_tip.py
"""
Проактивные рекомендации в VK и MAX. Запускается ежедневно в 19:00 МСК (cron).
Каждому привязанному ученику — не больше одной рекомендации в день
(кросс-канальный анти-спам через BotLog category='proactive').
"""
import os
import json
import logging

import requests
import vk_api
from vk_api.utils import get_random_id

from django.conf import settings
from django.core.management.base import BaseCommand

from main import bot_core

logger = logging.getLogger(__name__)

MAX_API = 'https://platform-api2.max.ru'


def _send_vk(api, vk_id, text, buttons):
    rows = [[{'action': {'type': 'text', 'label': b['label'], 'payload': b['payload']}}
             for b in row] for row in buttons]
    api.messages.send(
        user_id=vk_id, message=text,
        random_id=get_random_id(),
        keyboard=json.dumps({'inline': True, 'buttons': rows}, ensure_ascii=False),
    )


def _send_max(chat_id, text, buttons, token):
    body = {'text': text}
    if buttons:
        rows = [[{'type': 'callback', 'text': b['text'], 'payload': b['payload']}
                 for b in row] for row in buttons]
        body['attachments'] = [{'type': 'inline_keyboard', 'payload': {'buttons': rows}}]
    ca = settings.BASE_DIR / 'certs' / 'bundle.pem'
    verify = str(ca) if os.path.exists(ca) else True
    requests.post(f'{MAX_API}/messages',
                  headers={'Authorization': token, 'Content-Type': 'application/json'},
                  params={'chat_id': chat_id},
                  json=body, timeout=15, verify=verify)


class Command(BaseCommand):
    help = 'Проактивная рекомендация каждому привязанному ученику (1 раз в день)'

    def handle(self, *args, **options):
        vk = None
        vk_token = os.getenv('VK_GROUP_TOKEN')
        if vk_token:
            try:
                vk = vk_api.VkApi(token=vk_token).get_api()
            except Exception as e:
                logger.error(f'VK init error: {e}')
        max_token = os.getenv('MAX_BOT_TOKEN')

        sent = skipped_no_tip = skipped_sent = 0

        for profile in bot_core.iter_bot_eligible_profiles():
            try:
                if not (profile.vk_id or profile.max_chat_id):
                    continue
                if bot_core.proactive_sent_today(profile.user):
                    skipped_sent += 1
                    continue
                rec = bot_core.recommend_next(profile)
                if not rec:
                    skipped_no_tip += 1
                    continue

                text = rec['text']
                buttons = [[{'label': rec['button'][:40],
                             'payload': json.dumps({'a': rec['mode']}, ensure_ascii=False)}]]

                if vk and profile.vk_id:
                    try:
                        _send_vk(vk, profile.vk_id, text, buttons)
                    except Exception as e:
                        logger.error(f'VK send error user={profile.user_id}: {e}')
                if max_token and profile.max_chat_id:
                    try:
                        _send_max(profile.max_chat_id, text, buttons, max_token)
                    except Exception as e:
                        logger.error(f'MAX send error user={profile.user_id}: {e}')

                bot_core.log_proactive(profile.user, 'push', rec['text'])
                sent += 1
            except Exception as e:
                logger.exception(f'Proactive error user={profile.user_id}: {e}')

        self.stdout.write(
            f'Проактив: отправлено={sent}, без рекомендации={skipped_no_tip}, '
            f'уже показано сегодня={skipped_sent}')
