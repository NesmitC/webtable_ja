# main/management/commands/bot_daily_broadcast.py
"""
Рассылка «Слово дня» в VK и MAX. Запускается ежедневно в 12:00 МСК (cron).
Слово создаётся в DailyWord — то же состояние, что на сайте и в ботах.
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
    rows = []
    for row in buttons:
        rows.append([
            {'action': {'type': 'text', 'label': b['label'], 'payload': b['payload']}}
            for b in row
        ])
    api.messages.send(
        user_id=vk_id, message=text,
        random_id=get_random_id(),
        keyboard=json.dumps({'inline': True, 'buttons': rows}, ensure_ascii=False),
    )


def _send_max(chat_id, text, buttons, token):
    body = {'text': text}
    if buttons:
        rows = [[{'type': 'callback', 'text': b['label'], 'payload': b['payload']}
                 for b in row] for row in buttons]
        body['attachments'] = [{'type': 'inline_keyboard', 'payload': {'buttons': rows}}]
    ca = settings.BASE_DIR / 'certs' / 'bundle.pem'
    verify = str(ca) if os.path.exists(ca) else True
    requests.post(f'{MAX_API}/messages',
                  headers={'Authorization': token, 'Content-Type': 'application/json'},
                  params={'chat_id': chat_id},
                  json=body, timeout=15, verify=verify)


class Command(BaseCommand):
    help = 'Рассылка «Слово дня» всем привязанным пользователям (VK и MAX)'

    def handle(self, *args, **options):
        vk = None
        vk_token = os.getenv('VK_GROUP_TOKEN')
        if vk_token:
            try:
                vk = vk_api.VkApi(token=vk_token).get_api()
            except Exception as e:
                logger.error(f'VK init error: {e}')
        max_token = os.getenv('MAX_BOT_TOKEN')

        sent_vk = sent_max = skipped = 0

        for profile in bot_core.iter_bot_eligible_profiles():
            try:
                state = bot_core.get_daily_word_state(profile)
                if state.get('state') != 'revealed':
                    skipped += 1
                    continue

                name = profile.first_name or profile.user.first_name or ''
                text = f"⚡ Слово дня{' , ' + name if name else ''}!\n\n{state['question']}"
                buttons = []
                for i, opt in enumerate(state['options']):
                    payload = json.dumps(
                        {'a': 'daily_answer', 'i': i, 'p': state['period_date']},
                        ensure_ascii=False)
                    buttons.append([{'label': str(opt['text'])[:40], 'payload': payload}])

                if vk and profile.vk_id:
                    try:
                        _send_vk(vk, profile.vk_id, text, buttons)
                        sent_vk += 1
                    except Exception as e:
                        logger.error(f'VK send error user={profile.user_id}: {e}')

                if max_token and profile.max_chat_id:
                    try:
                        _send_max(profile.max_chat_id, text, buttons, max_token)
                        sent_max += 1
                    except Exception as e:
                        logger.error(f'MAX send error user={profile.user_id}: {e}')

                if not (profile.vk_id or profile.max_chat_id):
                    skipped += 1
            except Exception as e:
                logger.exception(f'Broadcast error user={profile.user_id}: {e}')

        self.stdout.write(
            f'Рассылка завершена: VK={sent_vk}, MAX={sent_max}, пропущено={skipped}')
