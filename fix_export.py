# fix_export.py
import json
import sys
import os
import django

sys.stdout.reconfigure(encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from django.core import serializers
from main.models import Orthogram, OrthogramExample

print("🔍 Экспорт данных с правильной кодировкой...")

# Получаем все данные
orthograms = Orthogram.objects.all()
examples = OrthogramExample.objects.all()

print(f"📊 Найдено орфограмм: {orthograms.count()}")
print(f"📊 Найдено примеров: {examples.count()}")

# Сериализуем с правильной кодировкой
data = serializers.serialize('json', list(orthograms) + list(examples))

# Сохраняем без ASCII экранирования
parsed_data = json.loads(data)
with open('orthogram_fixed.json', 'w', encoding='utf-8') as f:
    json.dump(parsed_data, f, ensure_ascii=False, indent=2, default=str)

print("✅ Данные экспортированы в orthogram_fixed.json")