import json
from pathlib import Path

from django import template
from django.core.cache import cache

register = template.Library()

PAPONIMS_PATH = Path(__file__).resolve().parents[1] / 'fixtures' / 'paponims.json'
CACHE_KEY = 'paponim_cards'


def _normalize(card):
    """Новый формат (cols) и старый (word1/word2) — оба работают."""
    if 'cols' in card:
        return card['cols']
    return [
        {'word': card.get('word1', ''), 'meaning': card.get('meaning1', '')},
        {'word': card.get('word2', ''), 'meaning': card.get('meaning2', '')},
    ]


def _group_by_letter(cards):
    """Группирует карточки по первой букве первого слова (порядок появления)."""
    order = []
    by_letter = {}
    for cols in cards:
        first = (cols[0].get('word') or '').strip()
        letter = first[0].upper() if first else '?'
        if letter not in by_letter:
            by_letter[letter] = []
            order.append(letter)
        by_letter[letter].append(cols)
    return [
        {
            'letter': letter,
            'cards': sorted(
                by_letter[letter],
                key=lambda cols: (cols[0].get('word') or '').strip().lower(),
            ),
        }
        for letter in sorted(order)
    ]



@register.simple_tag
def paponim_groups():
    raw = cache.get(CACHE_KEY)
    if raw is None:
        try:
            with open(PAPONIMS_PATH, encoding='utf-8') as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            raw = []
        cache.set(CACHE_KEY, raw, 3600)
    return _group_by_letter([_normalize(c) for c in raw])
