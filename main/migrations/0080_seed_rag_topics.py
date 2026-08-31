# Generated manually: seed RagTopic registry (Фаза 4)

from django.db import migrations

TOPICS = [
    # (code, name, description, source, order, is_ready)
    ('task3_analysis', 'Задание 3. Анализ текста',
     'Средства выразительности, стилистическая специфика текста. Отвечает по базе знаний base_ru.md.',
     'main/assistants/knowledge_bases/russian/base_ru.md', 3, True),
    ('task4_stress', 'Задание 4. Ударения (орфоэпический словарь ФИПИ)',
     'Орфоэпические нормы: ударения в словах из кодификатора ФИПИ.',
     'OrthoepyWord', 4, True),
    ('task5_paronyms', 'Задание 5. Паронимы',
     'Паронимы из списка ФИПИ со значениями.',
     'main/fixtures/paponims.json', 5, True),
    ('task6_lexical', 'Задание 6. Лексические нормы',
     'Лексические ошибки: плеоназм, тавтология, несочетаемость.',
     'WordOk', 6, True),
    ('task7_morphological', 'Задание 7. Морфологические нормы',
     'Морфологические нормы: правильное образование форм слов.',
     'CorrectionExercise', 7, True),
    ('task9_1_vowels', 'Задание 9.1. Проверяемые гласные в корне',
     'Правописание проверяемых безударных гласных в корне слова (орфограмма 1).',
     'OrthogramExample (orthogram_id=1)', 9, True),
]


def seed_topics(apps, schema_editor):
    RagTopic = apps.get_model('main', 'RagTopic')
    for code, name, description, source, order, is_ready in TOPICS:
        RagTopic.objects.update_or_create(
            code=code,
            defaults={
                'name': name,
                'description': description,
                'source': source,
                'order': order,
                'is_ready': is_ready,
            },
        )


def unseed_topics(apps, schema_editor):
    RagTopic = apps.get_model('main', 'RagTopic')
    RagTopic.objects.filter(code__in=[t[0] for t in TOPICS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0079_ragtopic'),
    ]

    operations = [
        migrations.RunPython(seed_topics, unseed_topics),
    ]
