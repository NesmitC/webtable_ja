"""
Django management command to seed OgePunktum and OgePunktumExample records for all Task 5 rules.
"""
from django.core.management.base import BaseCommand
from main.models import OgePunktum, OgePunktumExample

class Command(BaseCommand):
    help = 'Seeds OgePunktum records and examples for Comma, Dash and Colon tasks'

    def handle(self, *args, **options):
        # Commas
        comma_ids = ['2', '3', '4', '5', '6', '7', '11', '12', '13', '14', '15']
        for p_id in comma_ids:
            self._seed_punktum(p_id, 'Запятые', 'запятая')

        # Dash
        dash_ids = ['8', '18']
        for p_id in dash_ids:
            self._seed_punktum(p_id, 'Тире', 'тире')

        # Colon
        colon_ids = ['19']
        for p_id in colon_ids:
            self._seed_punktum(p_id, 'Двоеточие', 'двоеточие')

        self.stdout.write(self.style.SUCCESS('\nУспешно! Все пунктограммы созданы и заполнены тестовыми примерами.'))

    def _seed_punktum(self, p_id, group_name, sign_name):
        punktum, p_created = OgePunktum.objects.get_or_create(
            id=p_id,
            defaults={
                'name': f'{group_name}. Пунктограмма {p_id}',
                'rule': f'Правила постановки {sign_name} (пунктограмма {p_id})',
                'letters': f'{p_id}.1 {p_id}.2 {p_id}.3 0', 
            }
        )
        
        p_status = "created" if p_created else "exists"
        self.stdout.write(f'Punktum {p_id}: {p_status}')
        
        # Create one dummy example for each so the "Общее упр." doesn't crash empty
        text = f'Тестовое предложение для пункта {p_id}, в котором нужно {sign_name}.'
        masked_word = f'Тестовое предложение для пункта {p_id} *{p_id}* в котором нужно {sign_name}.'
        
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
