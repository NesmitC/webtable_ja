"""
Seed OgePunktumExample data for punktogram 8 (Тире между подлежащим и сказуемым).
Run: python manage.py seed_punktum8_examples
"""
from django.core.management.base import BaseCommand
from main.models import OgePunktum, OgePunktumExample


class Command(BaseCommand):
    help = 'Seeds example sentences for OgePunktum 8 (Тире)'

    def handle(self, *args, **options):
        # 1. Update letters for punktum 8
        try:
            p8 = OgePunktum.objects.get(id='8')
            p8.letters = '8.01,8.02,8.03,8.04,8.05,8.06'
            p8.save()
            self.stdout.write(f'Updated letters for punktum 8: {p8.letters}')
        except OgePunktum.DoesNotExist:
            self.stdout.write(self.style.ERROR('OgePunktum 8 not found! Run seed_dash_punktum first.'))
            return

        # 2. Create example
        # Sentences:
        # 1) Бедность ___ не порок.       → 8.04 (тире НЕ ставится: есть "не")
        # 2) Земля ___ наш дом.           → 8.01 (Сущ.И.п. — Сущ.И.п.)
        # 3) Мы ___ участники парада.     → 8.05 (тире НЕ ставится: подл. — местоимение)
        # 4) Жить ___ родине служить.     → 8.02 (Инф. — Инф.)
        # 5) Земля ___ как прекрасный сад. → 8.06 (тире перед "как")

        masked = (
            '1) Бедность *8* не порок. '
            '2) Земля *8* наш дом. '
            '3) Мы *8* участники парада. '
            '4) Жить *8* родине служить. '
            '5) Земля *8* как прекрасный сад.'
        )

        text = (
            '1) Бедность — не порок. '
            '2) Земля — наш дом. '
            '3) Мы — участники парада. '
            '4) Жить — родине служить. '
            '5) Земля — как прекрасный сад.'
        )

        explanation = '8.04,8.01,8.05,8.02,8.06'

        example, created = OgePunktumExample.objects.get_or_create(
            punktum=p8,
            masked_word=masked,
            defaults={
                'text': text,
                'explanation': explanation,
                'is_active': True,
                'is_for_quiz': False,
                'difficulty': 1,
            }
        )

        if not created:
            example.is_for_quiz = False
            example.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created example (id={example.id})'))
        else:
            self.stdout.write(f'Example already exists (id={example.id})')

        self.stdout.write(self.style.SUCCESS('Done! Punktum 8 is ready.'))
