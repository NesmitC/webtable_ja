#!/usr/bin/env python
"""Обновляет тестовые данные заданий 1-3 текстами с фото ОГЭ."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()
from main.models import (
    OgeTextAnalysisTask, OgeTextQuestion, OgeQuestionOption,
    OgeTaskGrammaticEight, OgeTaskGrammaticEightExample,
)

# Удаляем старые данные для задач 1-2
OgeQuestionOption.objects.filter(question__question_number__in=[1, 2]).delete()
OgeTextQuestion.objects.filter(question_number__in=[1, 2]).delete()
# Удаляем старый текст для 1-2
old = OgeTextAnalysisTask.objects.filter(title__icontains='природе')
old.delete()

# === ТЕКСТ для заданий 1-2 (общий) ===
text_1_2, _ = OgeTextAnalysisTask.objects.update_or_create(
    title="Текст о ягодах (задания 1–2)",
    defaults={
        'text_content': (
            '(1)С незапамятных времён человек употребляет в пищу дикорастущие плоды '
            'и ягоды, обладающие неповторимым ароматом и вкусом. (2)Клюква, брусника, '
            'черника, малина, земляника, калина — настоящие кладовые витаминов. '
            '(3)Собирать плоды и ягоды следует в сухую прохладную погоду, потому что '
            'в жаркую погоду они быстро вянут, так как содержат меньше сока. '
            '(4)Нельзя собирать несозревшие плоды, лучше оставить их дозреть, чтобы они налились '
            'соком, набрав больше витаминов. (5)При сборе будьте осторожны: старайтесь '
            'не топтать плодовые кустики.'
        ),
        'order': 1,
        'is_active': True,
    }
)

# Задание 1: грамматическая основа (чекбоксы)
q1, _ = OgeTextQuestion.objects.update_or_create(
    task=text_1_2, question_number=1,
    defaults={
        'question_type': 'multiple_choice',
        'question_text': (
            'Укажите варианты ответов, в которых верно определена '
            'грамматическая основа в одном из предложений или в одной из частей '
            'сложного предложения текста, кликнув по чек-боксам.'
        ),
        'correct_answer': '15',
    }
)
opts_1 = [
    (1, 'употребляет (предложение 1)', True),
    (2, 'настоящие кладовые (предложение 2)', False),
    (3, 'они быстро вянут (предложение 3)', False),
    (4, 'они налились (предложение 4)', False),
    (5, 'будьте осторожны (предложение 5)', True),
]
OgeQuestionOption.objects.filter(question=q1).delete()
for num, text, correct in opts_1:
    OgeQuestionOption.objects.create(
        question=q1, option_number=num,
        option_text=text, is_correct=correct
    )

# Задание 2: характеристики предложений (чекбоксы)
q2, _ = OgeTextQuestion.objects.update_or_create(
    task=text_1_2, question_number=2,
    defaults={
        'question_type': 'multiple_choice',
        'question_text': (
            'Укажите варианты ответов, в которых даны верные характеристики '
            'предложений текста, кликнув по чек-боксам.'
        ),
        'correct_answer': '35',
    }
)
opts_2 = [
    (1, 'Предложение 1 простое неосложнённое.', False),
    (2, 'В предложении 2 содержится составное глагольное сказуемое.', False),
    (3, 'Предложение 3 сложноподчинённое с последовательным подчинением придаточных.', True),
    (4, 'В составе сложного предложения 4 есть придаточное причины.', False),
    (5, 'Все простые предложения, входящие в состав сложного предложения 5, односоставные определённо-личные.', True),
]
OgeQuestionOption.objects.filter(question=q2).delete()
for num, text, correct in opts_2:
    OgeQuestionOption.objects.create(
        question=q2, option_number=num,
        option_text=text, is_correct=correct
    )

print(f"✓ Задания 1–2: текст «{text_1_2.title}», {OgeQuestionOption.objects.filter(question__task=text_1_2).count()} опций")

# === ЗАДАНИЕ 3: пунктуационные правила ===
OgeTaskGrammaticEightExample.objects.all().delete()
OgeTaskGrammaticEight.objects.all().delete()

# Правила (3 нужных + 2 для базы)
rules = [
    ('8100', True),  # А) В неполном предложении...
    ('8200', True),  # Б) Между подлежащим и сказуемым...
    ('8300', True),  # В) Обстоятельство, выраженное деепричастным оборотом...
    ('8400', True),  # Г)
    ('8500', True),  # Д)
]
for eid, active in rules:
    OgeTaskGrammaticEight.objects.get_or_create(id=eid, defaults={'is_active': active})

# 5 предложений из фото
examples = [
    # 1) Венера — планета (Подлежащее и сказуемое - 8200)
    ('8200', 'Венера — планета Солнечной системы, которая больше всего похожа на нашу Землю.', True),
    # 2) Девушка... скрипнув по снегу полозьями... (Деепричастный оборот - 8300)
    ('8300', 'Девушка была так увлечена зрелищем катающихся на коньках людей, что не заметила, как, скрипнув по снегу полозьями, неподалёку от неё остановились сани.', True),
    # 3) Там, где стоял посёлок... затерявшиеся в пространстве... (Причастный оборот - нет в А,Б,В)
    ('8400', 'Там, где стоял посёлок, сливались две ледяные, затерявшиеся в пространстве реки.', True),
    # 4) Днём ... видим только землю, ночью — весь мир. (Неполное предложение - 8100)
    ('8100', 'Днём, при солнечном свете, мы видим только землю, ночью — весь мир.', True),
    # 5) Пройдёт молодец... (Просто БСП / однородные) - без особой ошибки из списка
    (None, 'Пройдёт молодец — приосанится, пройдёт девица — пригорюнится, а пройдут гусляры — споют песенку.', False),
]

for eid, text, has_error in examples:
    OgeTaskGrammaticEightExample.objects.create(
        text=text, has_error=has_error, error_type_id=eid if has_error else None,
        explanation=f'Правило {eid}' if has_error else '', is_active=True,
    )

print(f"✓ Задание 3: {OgeTaskGrammaticEight.objects.count()} правил, "
      f"{OgeTaskGrammaticEightExample.objects.count()} предложений")

print("\n✅ Данные заданий 1–3 обновлены!")
