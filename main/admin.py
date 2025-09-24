# main/admin.py
from django.contrib import admin
from .models import CorrectAnswer


@admin.register(CorrectAnswer)
class CorrectAnswerAdmin(admin.ModelAdmin):
    list_display = ['orthogram_number', 'correct_word', 'description']
    list_filter = ['orthogram_number']
    search_fields = ['correct_word', 'description']
    ordering = ['orthogram_number', 'correct_word']
