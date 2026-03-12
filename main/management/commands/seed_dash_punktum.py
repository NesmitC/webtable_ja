"""
Django management command to seed OgePunktum records for Dash (Тире).
Run: python manage.py seed_dash_punktum
"""
from django.core.management.base import BaseCommand
from main.models import OgePunktum


class Command(BaseCommand):
    help = 'Seeds OgePunktum records for Dash tasks (ids 8 and 18)'

    def handle(self, *args, **options):
        p8, c8 = OgePunktum.objects.get_or_create(
            id='8',
            defaults={
                'name': 'Тире. Пунктограмма 8',
                'rule': 'Правила постановки тире (пунктограмма 8)',
                'letters': '5,8,8.1,9,10,18,дз',
            }
        )
        self.stdout.write(f'Punktum 8: created={c8}, name={p8.name}')

        p18, c18 = OgePunktum.objects.get_or_create(
            id='18',
            defaults={
                'name': 'Тире. Пунктограмма 18',
                'rule': 'Правила постановки тире (пунктограмма 18)',
                'letters': '5,8,8.1,9,10,18,дз',
            }
        )
        self.stdout.write(f'Punktum 18: created={c18}, name={p18.name}')

        self.stdout.write(self.style.SUCCESS('\nAll OgePunktum records:'))
        for p in OgePunktum.objects.all():
            self.stdout.write(f'  id={p.id}, name={p.name}, letters={p.letters}')
