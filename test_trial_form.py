# -*- coding: utf-8 -*-
"""Тест секции «Пробное занятие» на индексе и приёма заявок (API).

Проверяет: модель с полем comment, view callback_request (создание записи,
honeypot, обязательность контакта, лимит), рендер индекса (новая секция,
якоря, отсутствие старых CTA-кнопок диагностики), футер.

Изоляция: test_settings_isolated (SQLite в памяти). Боевая БД не трогается.
Запуск: .\\.venv\\Scripts\\python.exe test_trial_form.py
"""
import json
import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'test_settings_isolated'

import django

django.setup()

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client
from django.test.utils import setup_test_environment

assert settings.DATABASES['default']['NAME'] == ':memory:'
setup_test_environment()
call_command('migrate', verbosity=0, run_syncdb=True)

from main.models import CallbackRequest

fails = []


def check(cond, label):
    print(('  ✅ ' if cond else '  ❌ ') + label)
    if not cond:
        fails.append(label)


CALLBACK_URL = '/api/callback-request/'


def post_callback(ip, payload):
    return Client().post(
        CALLBACK_URL,
        data=json.dumps(payload),
        content_type='application/json',
        REMOTE_ADDR=ip,
    )


# ===== 1. Модель =====
print('1. Модель CallbackRequest')
field_names = {f.name for f in CallbackRequest._meta.get_fields()}
check('comment' in field_names, 'поле comment добавлено')
check(CallbackRequest._meta.get_field('comment').blank, 'comment необязательное')

# ===== 2. Приём заявки =====
print('2. Заявка с формы')
n0 = CallbackRequest.objects.count()
resp = post_callback('10.0.0.1', {
    'name': 'Мария', 'contact': '+7 900 123-45-67',
    'comment': '11 класс, хочу 85+, сроки до апреля',
    'source': 'index_trial',
})
check(resp.status_code == 200 and resp.json().get('status') == 'ok', 'успешный ответ 200 ok')
req = CallbackRequest.objects.order_by('-id').first()
check(CallbackRequest.objects.count() == n0 + 1, 'запись создана')
check(req is not None and req.comment.startswith('11 класс'), 'комментарий сохранён')
check(req is not None and req.source == 'index_trial', 'источник index_trial записан')
check(req is not None and req.attempt is None, 'заявка без привязки к диагностике')

# ===== 3. Honeypot =====
print('3. Honeypot от ботов')
n1 = CallbackRequest.objects.count()
resp = post_callback('10.0.0.2', {
    'name': 'Bot', 'contact': '+7 900 000-00-00',
    'hp': 'buy-casino-now', 'source': 'index_trial',
})
check(resp.status_code == 200 and resp.json().get('status') == 'ok',
      'боту тоже «ок» (не понимаем, что отфильтрованы)')
check(CallbackRequest.objects.count() == n1, 'запись бота НЕ создана')

# ===== 4. Валидация и лимит =====
print('4. Валидация и лимит')
resp = post_callback('10.0.0.3', {'name': 'Без контакта', 'contact': ''})
check(resp.status_code == 400, 'пустой контакт -> 400')

cache.clear()
for i in range(3):
    post_callback('10.0.0.4', {'contact': f'+7 900 000-00-0{i}'})
resp = post_callback('10.0.0.4', {'contact': '+7 900 000-00-99'})
check(resp.status_code == 429, '4-я заявка с того же IP -> 429')
cache.clear()

# ===== 5. Рендер индекса =====
print('5. Индекс: заглушка, кнопки и модалка')
html = Client().get('/').content.decode('utf-8')
check('id="trial-lesson"' in html, 'секция с id="trial-lesson" на месте (якорь)')
check('Узнайте свой уровень и получите план сегодня' in html, 'исходный заголовок чёрного блока')
check('847 учеников' in html, 'строка доверия на месте')
check('/#trial-lesson' in html, 'футер ведёт на эту секцию')

# ===== 6. Модальное окно записи =====
print('6. Модалка записи')
check('id="trialModal"' in html, 'модалка #trialModal на странице')
check('data-trial-close' in html, 'крестик/бэкдроп закрывают окно')
check('aria-label="Закрыть окно"' in html, 'крестик с aria-подписью')
check(html.count('data-trial-open') >= 4, 'кнопки «Записаться» открывают модалку (>=4)')
check('tel:+79167143463' in html, 'телефон кликабельный (tel: — звонилка на мобильном)')
check('mailto:a_timof@mail.ru' in html, 'почта кликабельная (mailto:)')
check('tm_name' in html and 'tm_contact' in html, 'поля «Имя» и «Телефон»')
check('tm_comment' in html, 'поле «Комментарий»')
check('tm_hp' in html, 'honeypot в модалке')
check('согласие на обработку персональных' in html, 'согласие на обработку ПДн')
check('trial_modal' in html, 'JS шлёт источник trial_modal')
check('Как к вам обращаться' in html, 'плейсхолдер имени')
check('или сразу в мессенджер' in html, 'строка «или сразу в мессенджер»')
modal_html = html[html.index('id="trialModal"'):html.index('id="trialModal"') + 8000]
check('ВКонтакте' not in modal_html, 'ВК из модалки убран (остались TG и MAX)')
check('Telegram' in modal_html and 'MAX' in modal_html, 'в модалке остались Telegram и MAX')
check('Пройти бесплатную диагностику' not in html, 'заглушка заменена на «Записаться на бесплатное занятие»')
check(html.count('data-trial-open') >= 5, 'все кнопки записи (включая чёрный блок) открывают модалку')
check('#zapis' in html, 'глубинная ссылка #zapis открывает модалку')
check('в ближайшее время' in html, 'обещание «отвечу в ближайшее время»')
check('в течение часа' not in html, 'старой формулировки «в течение часа» нет')
check('replace(/\\D/g' in html, 'маска телефона в JS модалки')
check("goal('TRIAL_MODAL_OPEN')" in html, 'цель Метрики: открытие окна')
check("goal('TRIAL_FORM_START')" in html, 'цель Метрики: начало заполнения')
check("goal('TRIAL_FORM_SUBMIT')" in html, 'цель Метрики: успешная отправка')

# ===== 6. Мобильная sticky-кнопка =====
print('6. Мобильная кнопка')
i = html.find('mobile-sticky-bar')
seg = html[i:i + 400] if i != -1 else ''
check('#trial-lesson' in seg, 'sticky-кнопка ведёт на #trial-lesson')
check('Записаться' in seg, 'sticky-кнопка переименована')

print()
if fails:
    print(f'❌ ПРОВАЛЕНО: {len(fails)}')
    for f in fails:
        print('   -', f)
    raise SystemExit(1)
print('✅ Все проверки пройдены')
