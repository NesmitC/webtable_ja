"""
Django management command to seed ALL OgePunktum + OgePunktumExample records.
Reads data from punktum_seed_data.json (same directory).

Run:  python manage.py seed_punktum_all
"""
import json
import os

from django.core.management.base import BaseCommand
from main.models import OgePunktum, OgePunktumExample


class Command(BaseCommand):
    help = 'Seeds all OgePunktum and OgePunktumExample from punktum_seed_data.json'

    def handle(self, *args, **options):
        json_path = os.path.join(os.path.dirname(__file__), 'punktum_seed_data.json')

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # 1. Seed OgePunktum
        punktums = data.get('punktums', [])
        for p in punktums:
            obj, created = OgePunktum.objects.update_or_create(
                id=p['id'],
                defaults={
                    'name': p['name'],
                    'rule': p['rule'],
                    'letters': p['letters'],
                    'grades': p.get('grades', ''),
                }
            )
            status = 'Created' if created else 'Updated'
            self.stdout.write(f'  Punktum {p["id"]}: {status} — {p["name"]}')

        # 2. Seed OgePunktumExample
        examples = data.get('examples', [])
        created_count = 0
        skipped_count = 0
        for ex in examples:
            _, created = OgePunktumExample.objects.get_or_create(
                punktum_id=ex['punktum_id'],
                text=ex['text'],
                defaults={
                    'masked_word': ex['masked_word'],
                    'explanation': ex['explanation'],
                    'difficulty': ex.get('difficulty', 1),
                    'is_active': ex.get('is_active', True),
                    'is_for_quiz': ex.get('is_for_quiz', False),
                }
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! {len(punktums)} punktums processed. '
            f'{created_count} examples created, {skipped_count} already existed.'
        ))
