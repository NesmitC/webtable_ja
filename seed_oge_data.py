#!/usr/bin/env python
"""Заполняет OGE-таблицы тестовыми данными для проверки 11 заданий."""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from main.models import (
    OgeTextAnalysisTask, OgeTextQuestion, OgeQuestionOption,
    OgeTaskGrammaticEight, OgeTaskGrammaticEightExample,
    OgePunktum, OgePunktumExample,
    OgeOrthogram, OgeOrthogramExample,
    OgeCorrectionExercise, OgeWordOk,
)

print("=== Заполняем OGE тестовыми данными ===\n")

# =====================================================================
# ТЕКСТ 1: для заданий 1, 2
# =====================================================================
text1, _ = OgeTextAnalysisTask.objects.get_or_create(
    title="Текст о природе (задания 1–2)",
    defaults={
        'text_content': (
            "(1) Осенний лес **поражает** своей красотой. "
            "(2) Листья деревьев окрашиваются в золотые, багряные и оранжевые тона. "
            "(3) Тихий ветер **срывает** последние листья с ветвей. "
            "(4) Птицы собираются в стаи и готовятся к долгому перелёту на юг. "
            "(5) Воздух наполняется свежестью и **прохладой**."
        ),
        'order': 1,
        'is_active': True,
    }
)

# Задание 1 — free_text (подобрать слово)
q1, _ = OgeTextQuestion.objects.get_or_create(
    task=text1, question_number=1,
    defaults={
        'question_type': 'missing_word',
        'question_text': 'Какое слово пропущено в предложении: «Осенний лес ___ своей красотой»?',
        'correct_answer': 'поражает/удивляет',
    }
)

# Задание 2 — multiple_choice (чекбоксы)
q2, _ = OgeTextQuestion.objects.get_or_create(
    task=text1, question_number=2,
    defaults={
        'question_type': 'multiple_choice',
        'question_text': 'Укажите варианты ответов, в которых верно определена тема текста.',
        'correct_answer': '13',
    }
)
options_2 = [
    (1, 'Красота осеннего леса', True),
    (2, 'Жизнь городских жителей', False),
    (3, 'Подготовка природы к зиме', True),
    (4, 'История возникновения лесов', False),
    (5, 'Промышленная вырубка деревьев', False),
]
for num, text, correct in options_2:
    OgeQuestionOption.objects.get_or_create(
        question=q2, option_number=num,
        defaults={'option_text': text, 'is_correct': correct}
    )

print(f"✓ Задания 1–2: текст «{text1.title}»")

# =====================================================================
# ЗАДАНИЕ 3: Выпадающие списки (нужно 5+ типов ошибок + примеры)
# =====================================================================
error_types_data = [
    ('8100', True),
    ('8200', True),
    ('8300', True),
    ('8400', True),
    ('8500', True),
    ('8600', True),
    ('8700', True),
]
for eid, active in error_types_data:
    OgeTaskGrammaticEight.objects.get_or_create(id=eid, defaults={'is_active': active})

# Примеры с ошибками (по 1 на каждый тип)
erroneous_examples = [
    ('8100', 'Те, кто пришли на экзамен, были готовы к нему.'),
    ('8200', 'Задание, выполняющееся студентами, было несложным.'),
    ('8300', 'Подъезжая к станции, у меня слетела шляпа.'),
    ('8400', 'Он любил и увлекался спортом.'),
    ('8500', 'Он вышел из дома и садится в машину.'),
    ('8600', 'В романе «Войне и мире» описаны события 1812 года.'),
    ('8700', 'Он скучал за домом и родными.'),
]
for eid, text in erroneous_examples:
    OgeTaskGrammaticEightExample.objects.get_or_create(
        text=text,
        defaults={
            'has_error': True,
            'error_type_id': eid,
            'explanation': f'Грамматическая ошибка типа {eid}',
            'is_active': True,
        }
    )

# Примеры БЕЗ ошибок (нужно минимум 4)
correct_sentences = [
    'Прочитав книгу, я задумался о смысле жизни.',
    'Те, кто пришёл на экзамен, были готовы к нему.',
    'Он не только читал книги, но и смотрел фильмы.',
    'В романе «Война и мир» описаны события 1812 года.',
    'Задание, выполненное студентами, оказалось несложным.',
    'Мы восхищались и гордились нашими спортсменами.',
]
for text in correct_sentences:
    OgeTaskGrammaticEightExample.objects.get_or_create(
        text=text,
        defaults={
            'has_error': False,
            'error_type': None,
            'explanation': '',
            'is_active': True,
        }
    )

print(f"✓ Задание 3: {OgeTaskGrammaticEight.objects.count()} типов ошибок, "
      f"{OgeTaskGrammaticEightExample.objects.count()} примеров")

# =====================================================================
# ЗАДАНИЕ 4: Пунктуация — смайлики (тире, двоеточие, запятая, кавычки)
# =====================================================================
punktum_data = [
    ('2100', 'Тире между подлежащим и сказуемым', 'Постановка тире', '!, ?, —, :, «»'),
    ('2101', 'Двоеточие в бессоюзном предложении', 'Постановка двоеточия', '!, ?, —, :, «»'),
    ('2102', 'Запятая при однородных членах', 'Постановка запятой', '!, ?, —, :, «»'),
    ('2103', 'Кавычки при прямой речи', 'Постановка кавычек', '!, ?, —, :, «»'),
]
for pid, name, rule, letters in punktum_data:
    OgePunktum.objects.get_or_create(
        id=pid,
        defaults={'name': name, 'rule': rule, 'letters': letters}
    )

# Примеры пунктуации
punkt_examples = [
    ('2100', 'Москва *2100* столица России.', 'Москва *2100* столица России.', '—'),
    ('2101', 'Я знал *2101* она придёт.', 'Я знал *2101* она придёт.', ':'),
    ('2102', 'Мы купили яблоки *2102* груши и сливы.', 'Мы купили яблоки *2102* груши и сливы.', '!'),
    ('2103', 'Он сказал *2103* Пойдём домой.', 'Он сказал *2103* Пойдём домой.', '«»'),
]
for pid, text, masked, explanation in punkt_examples:
    OgePunktumExample.objects.get_or_create(
        punktum_id=pid,
        text=text,
        defaults={
            'masked_word': masked,
            'explanation': explanation,
            'is_active': True,
        }
    )

print(f"✓ Задание 4: {OgePunktum.objects.count()} пунктограмм, "
      f"{OgePunktumExample.objects.count()} примеров")

# =====================================================================
# ТЕКСТ 2: для задания 5
# =====================================================================
text5, _ = OgeTextAnalysisTask.objects.get_or_create(
    title="Текст о языке (задание 5)",
    defaults={
        'text_content': (
            "(1) Русский язык — один из **богатейших** языков мира. "
            "(2) Он обладает огромным словарным запасом. "
            "(3) Каждое поколение вносит свой **вклад** в развитие языка. "
            "(4) Новые слова появляются, а устаревшие уходят из употребления. "
            "(5) Язык — это живой **организм**, который постоянно развивается."
        ),
        'order': 2,
        'is_active': True,
    }
)

q5, _ = OgeTextQuestion.objects.get_or_create(
    task=text5, question_number=5,
    defaults={
        'question_type': 'multiple_choice',
        'question_text': 'Укажите варианты ответов, в которых средством выразительности является метафора.',
        'correct_answer': '15',
    }
)
options_5 = [
    (1, '«Язык — это живой организм»', True),
    (2, '«Он обладает огромным словарным запасом»', False),
    (3, '«Новые слова появляются»', False),
    (4, '«Каждое поколение вносит свой вклад»', False),
    (5, '«Русский язык — один из богатейших языков мира»', True),
]
for num, text, correct in options_5:
    OgeQuestionOption.objects.get_or_create(
        question=q5, option_number=num,
        defaults={'option_text': text, 'is_correct': correct}
    )

print(f"✓ Задание 5: текст «{text5.title}»")

# =====================================================================
# ЗАДАНИЕ 6: Орфография — смайлики букв
# =====================================================================
orth_data = [
    ('101', 'Безударная гласная в корне', 'Проверяемая безударная в корне', 'а,о,е,и,я'),
    ('102', 'Чередующаяся гласная', 'Чередование в корне', 'а,о'),
    ('103', 'Непроверяемая гласная', 'Непроверяемая в корне', 'а,о,е,и'),
]
for oid, name, rule, letters in orth_data:
    OgeOrthogram.objects.get_or_create(
        id=oid,
        defaults={'name': name, 'rule': rule, 'letters': letters}
    )

orth_examples = [
    ('101', 'В*101*да хранит тайны глубин.', 'В*101*да хранит тайны глубин.', 'о'),
    ('102', 'Заг*102*рать на солнце полезно.', 'Заг*102*рать на солнце полезно.', 'о'),
    ('103', 'С*103*бака — верный друг человека.', 'С*103*бака — верный друг человека.', 'о'),
]
for oid, text, masked, correct in orth_examples:
    OgeOrthogramExample.objects.get_or_create(
        orthogram_id=oid,
        text=text,
        defaults={
            'masked_word': masked,
            'correct_letters': correct,
            'is_active': True,
        }
    )

print(f"✓ Задание 6: {OgeOrthogram.objects.count()} орфограмм, "
      f"{OgeOrthogramExample.objects.count()} примеров")

# =====================================================================
# ЗАДАНИЕ 7: Исправь ошибку (инпут)
# =====================================================================
correction_data = [
    ('ложить', 'класть', 'Правильно: класть (без приставки)', '711'),
    ('ихний', 'их', 'Правильно: их', '711'),
    ('звОнит', 'звонИт', 'Правильно: звонИт', '711'),
    ('обоих сестёр', 'обеих сестёр', 'Правильно: обеих сестёр', '711'),
    ('ездиют', 'ездят', 'Правильно: ездят', '711'),
    ('красивше', 'красивее', 'Правильно: красивее', '711'),
]
for wrong, right, expl, eid in correction_data:
    OgeCorrectionExercise.objects.get_or_create(
        incorrect_text=wrong,
        defaults={
            'correct_text': right,
            'explanation': expl,
            'exercise_id': eid,
            'is_active': True,
        }
    )

print(f"✓ Задание 7: {OgeCorrectionExercise.objects.count()} упражнений")

# =====================================================================
# ЗАДАНИЕ 8: Лексические нормы (инпут)
# =====================================================================
wordok_data = [
    ('6100', 'Он поднялся вверх по лестнице на самый последний этаж.', 'вверх'),
    ('6200', 'Мальчик одел тёплую куртку и вышел на улицу.', 'надел'),
    ('6100', 'В мае месяце начинается цветение садов.', 'месяце'),
    ('6200', 'Она сыграла заглавную роль в этом фильме.', 'главную'),
]
for task_type, text, correct in wordok_data:
    OgeWordOk.objects.get_or_create(
        text=text,
        defaults={
            'task_type': task_type,
            'correct_variants': correct,
            'is_active': True,
        }
    )

print(f"✓ Задание 8: {OgeWordOk.objects.count()} заданий")

# =====================================================================
# ТЕКСТ 3: для заданий 9, 10
# =====================================================================
text9, _ = OgeTextAnalysisTask.objects.get_or_create(
    title="Текст о дружбе (задания 9–10)",
    defaults={
        'text_content': (
            "(1) Дружба — одно из самых важных чувств в жизни человека. "
            "(2) Настоящий друг всегда придёт на помощь в трудную минуту. "
            "(3) Верность и преданность — главные качества настоящего друга. "
            "(4) К сожалению, не все люди умеют ценить дружбу. "
            "(5) Иногда мы понимаем ценность друга только тогда, когда теряем его. "
            "(6) Дружба требует постоянной заботы и внимания."
        ),
        'order': 3,
        'is_active': True,
    }
)

q9, _ = OgeTextQuestion.objects.get_or_create(
    task=text9, question_number=9,
    defaults={
        'question_type': 'multiple_choice',
        'question_text': 'Укажите варианты ответов, в которых содержится мысль о ценности дружбы.',
        'correct_answer': '125',
    }
)
options_9 = [
    (1, '«Дружба — одно из самых важных чувств в жизни человека»', True),
    (2, '«Иногда мы понимаем ценность друга только тогда, когда теряем его»', True),
    (3, '«К сожалению, не все люди умеют ценить дружбу»', False),
    (4, '«Верность и преданность — главные качества»', False),
    (5, '«Дружба требует постоянной заботы и внимания»', True),
]
for num, text, correct in options_9:
    OgeQuestionOption.objects.get_or_create(
        question=q9, option_number=num,
        defaults={'option_text': text, 'is_correct': correct}
    )

q10, _ = OgeTextQuestion.objects.get_or_create(
    task=text9, question_number=10,
    defaults={
        'question_type': 'multiple_choice',
        'question_text': 'Укажите номера предложений, в которых есть тире.',
        'correct_answer': '13',
    }
)
options_10 = [
    (1, 'Предложение 1', True),
    (2, 'Предложение 2', False),
    (3, 'Предложение 3', True),
    (4, 'Предложение 4', False),
    (5, 'Предложение 5', False),
]
for num, text, correct in options_10:
    OgeQuestionOption.objects.get_or_create(
        question=q10, option_number=num,
        defaults={'option_text': text, 'is_correct': correct}
    )

print(f"✓ Задания 9–10: текст «{text9.title}»")

# =====================================================================
# ТЕКСТ 4: для задания 11
# =====================================================================
text11, _ = OgeTextAnalysisTask.objects.get_or_create(
    title="Текст о книгах (задание 11)",
    defaults={
        'text_content': (
            "(1) Книги — это окна в другие миры. "
            "(2) Читая, мы путешествуем во времени и пространстве. "
            "(3) Хорошая книга способна изменить человека. "
            "(4) Она учит нас сочувствию, доброте и справедливости."
        ),
        'order': 4,
        'is_active': True,
    }
)

q11, _ = OgeTextQuestion.objects.get_or_create(
    task=text11, question_number=11,
    defaults={
        'question_type': 'free_text',
        'question_text': 'Выпишите из предложения 1 слово, образованное путём метафорического переноса.',
        'correct_answer': 'окна/окно',
    }
)

print(f"✓ Задание 11: текст «{text11.title}»")

# =====================================================================
print(f"\n✅ Все тестовые данные загружены!")
print(f"   Текстов: {OgeTextAnalysisTask.objects.count()}")
print(f"   Вопросов: {OgeTextQuestion.objects.count()}")
print(f"   Вариантов ответов: {OgeQuestionOption.objects.count()}")
print(f"   Типов ошибок (зад.3): {OgeTaskGrammaticEight.objects.count()}")
print(f"   Примеров ошибок (зад.3): {OgeTaskGrammaticEightExample.objects.count()}")
print(f"   Пунктограмм (зад.4): {OgePunktum.objects.count()}")
print(f"   Примеров пунктуации (зад.4): {OgePunktumExample.objects.count()}")
print(f"   Орфограмм (зад.6): {OgeOrthogram.objects.count()}")
print(f"   Примеров орфограмм (зад.6): {OgeOrthogramExample.objects.count()}")
print(f"   Исправь ошибку (зад.7): {OgeCorrectionExercise.objects.count()}")
print(f"   Лексика (зад.8): {OgeWordOk.objects.count()}")
