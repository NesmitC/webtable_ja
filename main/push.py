# -*- coding: utf-8 -*-
"""main/push.py — Web Push (PWA): доставка «Слова дня» на телефон.

Канал: Push API браузера (FCM у Android/Chrome, APNs у iPhone, Mozilla у
Firefox) через СОБСТВЕННЫЕ VAPID-ключи — внешних сервисов и посредников нет.
Подписки браузеров хранятся в PushSubscription; само слово берётся из общего
состояния DailyWord (bot_core.get_daily_word_state), поэтому сайт, боты и пуш
всегда показывают одно и то же слово периода.
"""
import json
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

PUSH_TITLE = 'Нейростат: слово дня'
# тап по уведомлению открывает карточку слова дня на сайте
PUSH_URL_PATH = '/ege/quizzes/#daily-word'


def push_enabled() -> bool:
    """Пуш настроен: в .env есть оба VAPID-ключа."""
    return bool(getattr(settings, 'VAPID_PRIVATE_KEY', '')
                and getattr(settings, 'VAPID_PUBLIC_KEY', ''))


def detect_platform(user_agent: str) -> str:
    """ios/android/desktop/other — для статистики доставляемости по каналам."""
    ua = (user_agent or '').lower()
    if 'iphone' in ua or 'ipad' in ua or ('macintosh' in ua and ' touch' in ua):
        return 'ios'
    if 'android' in ua:
        return 'android'
    if any(t in ua for t in ('windows', 'macintosh', 'linux', 'x11')):
        return 'desktop'
    return 'other'


def daily_payload(state: dict) -> dict:
    """Payload уведомления: текст задания виден сразу (как в карточке сайта)."""
    return {
        'title': PUSH_TITLE,
        'body': state.get('question', ''),
        'url': f'{settings.SITE_URL}{PUSH_URL_PATH}',
        'icon': '/static/images/pwa/icon-192.png',
        'badge': '/static/images/pwa/badge-72.png',
        'tag': f"daily-{state.get('period_date', '')}",
    }


def send_push(sub, payload: dict) -> tuple:
    """Один пуш в подписку. Возвращает (ok, reason).

    reason='dead' — браузер/FCM/APNs сообщил, что подписки больше нет
    (404/410): такую деактивируем, чтобы не слать в пустоту.
    """
    from pywebpush import webpush, WebPushException

    info = {'endpoint': sub.endpoint,
            'keys': {'p256dh': sub.p256dh, 'auth': sub.auth}}
    try:
        webpush(subscription_info=info,
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': settings.VAPID_CLAIMS_EMAIL},
                timeout=15)
        return True, ''
    except WebPushException as e:
        status = getattr(getattr(e, 'response', None), 'status_code', 0)
        if status in (404, 410):
            return False, 'dead'
        return False, f'http {status}' if status else str(e)[:180]
    except Exception as e:  # сеть/таймаут: не роняем всю рассылку
        return False, str(e)[:180]


def send_daily_words(user=None, dry_run: bool = False) -> dict:
    """Рассылка «Слова дня» по всем активным подпискам (cron 16:00 МСК).

    user — отправить только одному пользователю (тест на своём телефоне);
    dry_run — слово формируется и считается, но не отправляется.
    Пропускаем: бесплатный тариф (слово дня — платная фича) и тех, кто уже
    ответил сегодня (не дёргаем зря).
    """
    from . import bot_core
    from .models import PushSubscription, UserProfile

    stats = {'sent': 0, 'skipped': 0, 'failed': 0, 'deactivated': 0, 'users': 0}
    subs = PushSubscription.objects.filter(active=True).select_related('user')
    if user is not None:
        subs = subs.filter(user=user)
    subs = list(subs)
    stats['users'] = len({s.user_id for s in subs})

    if not subs:
        return stats
    if not dry_run and not push_enabled():
        stats['error'] = 'нет VAPID-ключей: выполните manage.py generate_vapid_keys'
        return stats

    for sub in subs:
        try:
            profile, _ = UserProfile.objects.get_or_create(user=sub.user)
            if not bot_core.user_can_use_bot(profile):
                stats['skipped'] += 1
                continue
            state = bot_core.get_daily_word_state(profile)
            if state.get('state') != 'revealed':
                stats['skipped'] += 1
                continue
            payload = daily_payload(state)
            if dry_run:
                stats['sent'] += 1
                continue
            ok, reason = send_push(sub, payload)
            if ok:
                sub.last_sent_at = timezone.now()
                sub.last_error = ''
                sub.save(update_fields=['last_sent_at', 'last_error'])
                stats['sent'] += 1
            elif reason == 'dead':
                sub.active = False
                sub.save(update_fields=['active'])
                stats['deactivated'] += 1
            else:
                sub.last_error = reason
                sub.save(update_fields=['last_error'])
                stats['failed'] += 1
                logger.error(f'push failed user={sub.user_id}: {reason}')
        except Exception as e:
            stats['failed'] += 1
            logger.exception(f'push error user={sub.user_id}: {e}')
    return stats
