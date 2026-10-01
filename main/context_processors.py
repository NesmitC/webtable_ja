# -*- coding: utf-8 -*-
"""main/context_processors.py — контакты проекта в одном месте.

Зачем: MAX-ссылку осенью пришлось менять во всех шаблонах вручную. Теперь
адреса живут только здесь, а шаблоны берут их из контекста ({{ CONTACTS.* }},
{{ MESSENGERS }}). Правка контакта = правка одного файла.

Подключено в settings.TEMPLATES -> context_processors как
'main.context_processors.contacts'.
"""

# === ЕДИНСТВЕННЫЙ ИСТОЧНИК КОНТАКТОВ ===
CONTACTS = {
    'phone': '+79167143463',
    'phone_pretty': '+7 916 714-34-63',
    'email': 'a_timof@mail.ru',
    'teacher': 'Александр',
    'telegram': 'https://t.me/sitesprofi',
    'telegram_handle': '@sitesprofi',
    'vk': 'https://vk.ru/alex_serg_ru',
    'vk_handle': 'alex_serg_ru',
    'max': ('https://max.ru/u/f9LHodD0cOLLVtiJEdDhpogsJ-Tzb_y5Djy4P7nrT7qyDJxAqwaoNHVjs5Y'),
}

# Порядок = порядок показа в интерфейсе.
MESSENGERS = (
    {
        'key': 'telegram',
        'label': 'Telegram',
        'handle': CONTACTS['telegram_handle'],
        'url': CONTACTS['telegram'],
        'icon': 'images/socia_telegram.svg',
    },
    {
        'key': 'vk',
        'label': 'ВКонтакте',
        'handle': CONTACTS['vk_handle'],
        'url': CONTACTS['vk'],
        'icon': 'images/socia_vk.svg',
    },
    {
        'key': 'max',
        'label': 'MAX',
        'handle': 'MAX',
        'url': CONTACTS['max'],
        'icon': 'images/socia_max.svg',
    },
)


def contacts(request):
    """Контакты во все шаблоны. Ничего не читает из БД и не обращается наружу."""
    return {'CONTACTS': CONTACTS, 'MESSENGERS': MESSENGERS}
