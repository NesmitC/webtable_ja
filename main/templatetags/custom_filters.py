from django import template
import re

register = template.Library()

@register.filter
def bold_words(text):
    """Заменяет *слово* на <strong>слово</strong>"""
    if not text:
        return text
    # Заменяем *текст* на <strong>текст</strong>
    return re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', text)