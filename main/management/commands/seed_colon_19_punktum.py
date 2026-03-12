"""
Django management command to seed OgePunktum record for Colon (Двоеточие), punktogram 19.
Run: python manage.py seed_colon_19_punktum
"""
from django.core.management.base import BaseCommand
from main.models import OgePunktum


class Command(BaseCommand):
    help = 'Seeds OgePunktum records for Colon task (id 19)'

    def handle(self, *args, **options):
        p19, c19 = OgePunktum.objects.get_or_create(
            id='19',
            defaults={
                'name': 'Двоеточие. Пунктограмма 19',
                'rule': 'Правила постановки двоеточия (пунктограмма 19)',
                'letters': '1,2,3,4,5,6',  # placeholder letters, admin can edit
            }
        )
        self.stdout.write(self.style.SUCCESS(f'Punktum 19: created={c19}, name={p19.name}'))

        self.stdout.write(self.style.SUCCESS('Done! Punktum 19 is ready.'))
