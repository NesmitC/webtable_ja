#!/usr/bin/env python
"""Обновляет данные заданий 7 и 8 — точный текст с фото."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()
from main.models import OgeCorrectionExercise, OgeWordOk

# Задание 8
OgeCorrectionExercise.objects.all().delete()
OgeCorrectionExercise.objects.create(
    incorrect_text='вишня',                                        # слово в скобках
    correct_text='вишен',                                          # правильный ответ
    explanation='Для украшения десерта вам потребуется несколько (вишня).',  # предложение
    exercise_id='711',
    is_active=True,
)
print('✓ Задание 8 обновлено')

# Задание 9
OgeWordOk.objects.all().delete()
OgeWordOk.objects.create(
    task_type='6200',
    text='Замените словосочетание «турецкий кофе», построенное на основе согласования, синонимичным словосочетанием со связью примыкание. Напишите получившееся словосочетание, соблюдая нормы современного русского литературного языка.',
    correct_variants='кофе по-турецки',
    is_active=True,
)
print('✓ Задание 9 обновлено')
print('✅ Готово!')
