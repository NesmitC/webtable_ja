# -*- coding: utf-8 -*-
"""Изолированные настройки для прогона тестов. Временный файл.

Ключевое отличие от неудачной прошлой попытки: это ОТДЕЛЬНЫЙ модуль настроек,
который подставляется через DJANGO_SETTINGS_MODULE ДО django.setup().
Боевая PostgreSQL neurostat не затрагивается вообще — используется SQLite
в памяти процесса, которая исчезает вместе с ним.
"""
from main.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Письма не уходят наружу, а складываются в django.core.mail.outbox
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
