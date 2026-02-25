#!/usr/bin/env python
"""Обновляет задание 6 — правописание с фото ОГЭ."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()
from main.models import OgeTextAnalysisTask, OgeTextQuestion, OgeQuestionOption

# Удаляем старое задание 6
OgeQuestionOption.objects.filter(question__question_number=6).delete()
OgeTextQuestion.objects.filter(question_number=6).delete()
OgeTextAnalysisTask.objects.filter(title__icontains='язык').delete()

# Задание 6 — без текста, только вопрос с чекбоксами
text_6, _ = OgeTextAnalysisTask.objects.update_or_create(
    title="Правописание (задание 6)",
    defaults={
        'text_content': '',  # пустой — текст не нужен
        'order': 2,
        'is_active': True,
    }
)

q6, _ = OgeTextQuestion.objects.update_or_create(
    task=text_6, question_number=6,
    defaults={
        'question_type': 'multiple_choice',
        'question_text': 'Укажите варианты ответов, в которых дано верное объяснение написания выделенного слова, кликнув по чек-боксам.',
        'correct_answer': '235',
    }
)

opts = [
    (1, 'ССЫЛКА (в Сибирь) — на конце приставки перед буквой, обозначающей глухой согласный, пишется буква С.', False, '11'),
    (2, 'НЕЖНО-ЗЕЛЁНЫЙ — сложное имя прилагательное, обозначающее оттенок цвета, пишется через дефис.', True, '39'),
    (3, '(о высокой) ЦЕЛИ — в форме дательного падежа единственного числа имени существительного 3-го склонения пишется окончание -И.', True, '17'),
    (4, 'РАССЕЯВШИЙ (сомнения) — выбор гласной перед суффиксом -вш- действительного причастия прошедшего времени зависит от принадлежности к спряжению глагола, от основы которого оно образовано.', False, '25, 49.1'),
    (5, 'СЕРДЦЕ — непроизносимый согласный в корне слова проверяется словом сердечко, в котором он слышится отчётливо.', True, '4'),
]

OgeQuestionOption.objects.filter(question=q6).delete()
for num, text, correct, orth_num in opts:
    OgeQuestionOption.objects.create(question=q6, option_number=num, option_text=text, is_correct=correct, orthogram_numbers=orth_num)

print(f"✓ Задание 6: {len(opts)} опций")
print("✅ Готово!")
