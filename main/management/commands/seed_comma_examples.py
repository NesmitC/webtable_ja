"""
Django management command to seed OgePunktum and OgePunktumExample records for Commas (Запятые).
Run: python manage.py seed_comma_examples
"""
from django.core.management.base import BaseCommand
from main.models import OgePunktum, OgePunktumExample

class Command(BaseCommand):
    help = 'Seeds OgePunktum records and examples for Comma tasks (ids 2-7, 11-15)'

    def handle(self, *args, **options):
        comma_ids = ['2', '3', '4', '5', '6', '7', '11', '12', '13', '14', '15']
        
        for p_id in comma_ids:
            # 1. Create or get OgePunktum
            punktum, p_created = OgePunktum.objects.get_or_create(
                id=p_id,
                defaults={
                    'name': f'Запятые. Пунктограмма {p_id}',
                    'rule': f'Правила постановки запятой (пунктограмма {p_id})',
                    'letters': f'{p_id}.1,{p_id}.2,{p_id}.3,0', # placeholder dummy choices
                }
            )
            
            p_status = "created" if p_created else "exists"
            self.stdout.write(f'Punktum {p_id}: {p_status}')
            
            # 2. Create one dummy example for each so the "Общее упр." doesn't crash
            text = f'Тестовое предложение для пункта {p_id}, в котором нужна запятая.'
            masked_word = f'Тестовое предложение для пункта {p_id} *{p_id}* в котором нужна запятая.'
            
            example, e_created = OgePunktumExample.objects.get_or_create(
                punktum=punktum,
                masked_word=masked_word,
                defaults={
                    'text': text,
                    'explanation': f'{p_id}.1',
                    'is_active': True,
                    'is_for_quiz': False,
                    'difficulty': 1,
                }
            )
            
            e_status = "created" if e_created else "exists"
            self.stdout.write(f'  Example for {p_id}: {e_status} (id={example.id})')

        self.stdout.write(self.style.SUCCESS('\nDone! Comma punctograms are ready for testing.'))
