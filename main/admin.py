# main/admin.py
from django.contrib import admin
from django import forms
from django.db import models 
from .models import CorrectAnswer, Orthogram, OrthogramExample, Punktum, PunktumExample, TextAnalysisTask, TextQuestion, QuestionOption, OrthoepyWord, CorrectionExercise, TaskGrammaticEight, TaskGrammaticEightExample, TaskGrammaticTwoTwo, TaskGrammaticTwoTwoExample, TaskPaponim, WordOk
from django.contrib.admin.actions import delete_selected


@admin.register(CorrectAnswer)
class CorrectAnswerAdmin(admin.ModelAdmin):
    list_display = ['orthogram_number', 'correct_word', 'description']
    list_filter = ['orthogram_number']
    search_fields = ['correct_word', 'description']
    ordering = ['orthogram_number', 'correct_word']


@admin.register(Orthogram)
class OrthogramAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'letters', 'grades']
    list_editable = ['grades']
    search_fields = ['id', 'name']
    fieldsets = (
        (None, {
            'fields': ('id', 'name', 'rule', 'letters'),
            'description': '<strong>Важно:</strong> Введите буквы через запятую, например: <code>а,о,е,и,я</code> или <code>Ъ,Ь</code>.'
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.extra(select={'id_as_int': "CAST(id AS INTEGER)"}).order_by('id_as_int')
    
    class Media:
        css = {
            'all': ('main/static/css/admin.css',)
        }


@admin.register(OrthogramExample)
class OrthogramExampleAdmin(admin.ModelAdmin):
    list_display = ['text', 'orthogram', 'masked_word', 'grades', 'difficulty', 'is_for_quiz', 'is_active']
    actions = [delete_selected]
    fieldsets = (
        (None, {
            'fields': ('orthogram', 'text', 'masked_word', 'incorrect_variant', 'explanation', 'grades')
        }),
        ('Настройки', {
            'fields': ('difficulty', 'is_for_quiz', 'is_active'),
            'description': '<strong>Важно:</strong> Поле "Grades" указывает, для каких классов предназначен этот пример.'
        }),
    )
    list_filter = ['orthogram', 'difficulty', 'is_for_quiz', 'is_active']
    search_fields = ['text', 'masked_word', 'incorrect_variant', 'grades']
    list_editable = ['grades', 'is_for_quiz', 'is_active']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs
            .extra(select={'orthogram_id_as_int': "CAST(orthogram_id AS INTEGER)"})
            .order_by('orthogram_id_as_int', 'text')
        )
        
    class Media:
        css = {
            'all': ('css/admin.css',)
        }


# ===== ЗАДАНИЯ 16-21 ==================================================
@admin.register(Punktum)
class PunktumAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'rule')
    search_fields = ('id', 'name')


@admin.register(PunktumExample)
class PunktumExampleAdmin(admin.ModelAdmin):
    list_display = ('text', 'punktum', 'is_active', 'added_by', 'created_at')
    list_filter = ('is_active', 'punktum', 'added_by', 'grades')
    search_fields = ('text', 'masked_word')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 5, 'cols': 80})},
    }

    fieldsets = (
        (None, {
            'fields': ('punktum', 'text', 'masked_word', 'explanation', 'difficulty', 'is_active', 'is_user_added', 'added_by', 'source_field', 'grades')
        }),
        ('Дополнительно', {
            'classes': ('collapse',),
            'fields': ('created_at',),
        }),
    )

    class Media:
        css = {
            'all': ('css/admin.css',)
        }

# =======================================================================
class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 1

class TextQuestionInline(admin.TabularInline):
    model = TextQuestion
    extra = 1
    show_change_link = True

@admin.register(TextAnalysisTask)
class TextAnalysisTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    inlines = [TextQuestionInline]
    search_fields = ['title', 'text_content']

@admin.register(TextQuestion)
class TextQuestionAdmin(admin.ModelAdmin):
    list_display = ['task', 'question_number', 'question_type']
    list_filter = ['question_type']
    inlines = [QuestionOptionInline]
    search_fields = ['question_text', 'task__title']



# ===== ЗАДАНИЕ 4 ===================================================
@admin.register(OrthoepyWord)
class OrthoepyWordAdmin(admin.ModelAdmin):
    list_display = ['word', 'lemma', 'is_correct_display', 'is_active', 'grades']
    list_filter = ['is_correct', 'is_active', 'grades']
    search_fields = ['word', 'lemma']
    list_editable = ['is_active']
    
    def is_correct_display(self, obj):
        return "✓ Правильное" if obj.is_correct else "✗ Неправильное"
    is_correct_display.short_description = "Тип"
    is_correct_display.admin_order_field = 'is_correct'


# ===== ЗАДАНИЕ 5 ===================================================
@admin.register(TaskPaponim)
class TaskPaponimAdmin(admin.ModelAdmin):
    list_display = ['preview', 'root', 'has_error', 'is_active', 'is_for_quiz']
    list_editable = ['is_active', 'is_for_quiz']
    list_filter = ['is_active', 'is_for_quiz', 'root']
    search_fields = ['text', 'correct_word', 'root']

    def preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    preview.short_description = "Предложение"

    def has_error(self, obj):
        return obj.has_error
    has_error.boolean = True
    has_error.short_description = "С ошибкой"


# ===== ЗАДАНИЕ 6 ===================================================
@admin.register(WordOk)
class WordOkAdmin(admin.ModelAdmin):
    list_display = ['preview', 'task_type', 'correct_variants', 'is_active', 'is_for_quiz']
    list_editable = ['is_active', 'is_for_quiz']
    list_filter = ['task_type', 'is_active', 'is_for_quiz', 'grades']
    search_fields = ['text', 'correct_variants']

    def preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text


# ===== ЗАДАНИЕ 7 ===================================================
@admin.register(CorrectionExercise)
class CorrectionExerciseAdmin(admin.ModelAdmin):
    list_display = (
        'incorrect_text',
        'correct_text_short',
        'exercise_id',
        'is_active',
        'is_for_quiz',
        'grades'
    )
    list_filter = ('exercise_id', 'is_active', 'is_for_quiz', 'grades')
    search_fields = ('incorrect_text', 'correct_text', 'explanation')
    list_editable = ('is_active', 'is_for_quiz', 'grades')

    fieldsets = (
        ('Ошибка и исправление', {
            'fields': ('incorrect_text', 'correct_text', 'explanation'),
            'description': '''
                <strong>Неправильный текст:</strong> то, что видит ученик (сожгет)<br>
                <strong>Правильный текст:</strong> эталонный ответ (сожжет)<br>
                <strong>Пояснение (опционально):</strong> краткое правило
            '''
        }),
        ('Настройки', {
            'fields': ('exercise_id', 'grades', 'is_active', 'is_for_quiz'),
            'description': '''
                <strong>exercise_id</strong> — например, "711"<br>
                <strong>is_active</strong> — использовать в тестах<br>
                <strong>is_for_quiz</strong> — использовать в квизах<br>
                <strong>grades</strong> — для каких классов (5,6,7)
            '''
        }),
    )

    def correct_text_short(self, obj):
        """Обрезаем длинные ответы в списке"""
        return (obj.correct_text[:30] + '...') if len(obj.correct_text) > 30 else obj.correct_text

    correct_text_short.short_description = 'Правильный ответ'

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('incorrect_text')


# ===== ЗАДАНИЕ 8 ===================================================
@admin.register(TaskGrammaticEight)
class TaskGrammaticEightAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_id_display', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']  # можно добавить ещё filter по id или description
    search_fields = ['id', 'get_id_display']  # поиск по описанию


@admin.register(TaskGrammaticEightExample)
class TaskGrammaticEightExampleAdmin(admin.ModelAdmin):
    list_display = ['preview', 'has_error', 'error_type', 'is_active', 'is_for_quiz']
    list_filter = ['has_error', 'error_type', 'is_active', 'is_for_quiz', 'grades']
    list_editable = ['is_active', 'is_for_quiz']
    
    def preview(self, obj):
        return (obj.text[:60] + '…') if len(obj.text) > 60 else obj.text

# ===== ЗАДАНИЕ 22 ===================================================
@admin.register(TaskGrammaticTwoTwo)
class TaskGrammaticTwoTwoAdmin(admin.ModelAdmin):
    list_display = ['id', 'display_name', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    
    def display_name(self, obj):
        # ИСПРАВЛЕНО: используем dict
        return dict(obj.DEVICE_TYPES).get(obj.id, obj.id)
    display_name.short_description = 'Название'

@admin.register(TaskGrammaticTwoTwoExample)
class TaskGrammaticTwoTwoExampleAdmin(admin.ModelAdmin):
    list_display = ['preview', 'display_device_type', 'author', 'is_active', 'is_for_quiz']
    list_filter = ['is_active', 'is_for_quiz', 'device_type']
    list_editable = ['is_active', 'is_for_quiz']
    
    def preview(self, obj):
        return (obj.text[:60] + '…') if len(obj.text) > 60 else obj.text
    
    def display_device_type(self, obj):
        if obj.device_type:
            return dict(obj.device_type.DEVICE_TYPES).get(obj.device_type.id, obj.device_type.id)
        return '-'
    display_device_type.short_description = 'Средство выразительности'


# ========================================================================
# ОГЭ — АДМИНКА
# ========================================================================
from .models import (
    OgeTextAnalysisTask, OgeTextQuestion, OgeQuestionOption,
    OgeTaskGrammaticEight, OgeTaskGrammaticEightExample,
    OgePunktum, OgePunktumExample,
    OgeOrthogram, OgeOrthogramExample,
    OgeCorrectionExercise, OgeWordOk,
)


class OgeQuestionOptionInline(admin.TabularInline):
    model = OgeQuestionOption
    extra = 1

class OgeTextQuestionInline(admin.TabularInline):
    model = OgeTextQuestion
    extra = 1
    show_change_link = True


@admin.register(OgeTextAnalysisTask)
class OgeTextAnalysisTaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    inlines = [OgeTextQuestionInline]
    search_fields = ['title', 'text_content']

@admin.register(OgeTextQuestion)
class OgeTextQuestionAdmin(admin.ModelAdmin):
    list_display = ['task', 'question_number', 'question_type']
    list_filter = ['question_type']
    inlines = [OgeQuestionOptionInline]
    search_fields = ['question_text', 'task__title']


@admin.register(OgeTaskGrammaticEight)
class OgeTaskGrammaticEightAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_id_display', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']

@admin.register(OgeTaskGrammaticEightExample)
class OgeTaskGrammaticEightExampleAdmin(admin.ModelAdmin):
    list_display = ['preview', 'has_error', 'error_type', 'is_active', 'is_for_quiz']
    list_filter = ['has_error', 'error_type', 'is_active', 'is_for_quiz', 'grades']
    list_editable = ['is_active', 'is_for_quiz']

    def preview(self, obj):
        return (obj.text[:60] + '…') if len(obj.text) > 60 else obj.text


@admin.register(OgePunktum)
class OgePunktumAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'rule')
    search_fields = ('id', 'name')

@admin.register(OgePunktumExample)
class OgePunktumExampleAdmin(admin.ModelAdmin):
    list_display = ('text', 'punktum', 'is_active', 'added_by', 'created_at')
    list_filter = ('is_active', 'punktum', 'added_by', 'grades')
    search_fields = ('text', 'masked_word')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 5, 'cols': 80})},
    }


@admin.register(OgeOrthogram)
class OgeOrthogramAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'letters', 'grades']
    list_editable = ['grades']
    search_fields = ['id', 'name']

@admin.register(OgeOrthogramExample)
class OgeOrthogramExampleAdmin(admin.ModelAdmin):
    list_display = ['text', 'orthogram', 'masked_word', 'grades', 'difficulty', 'is_for_quiz', 'is_active']
    list_filter = ['orthogram', 'difficulty', 'is_for_quiz', 'is_active']
    search_fields = ['text', 'masked_word', 'incorrect_variant', 'grades']
    list_editable = ['grades', 'is_for_quiz', 'is_active']


@admin.register(OgeCorrectionExercise)
class OgeCorrectionExerciseAdmin(admin.ModelAdmin):
    list_display = (
        'incorrect_text',
        'correct_text_short',
        'exercise_id',
        'is_active',
        'is_for_quiz',
        'grades'
    )
    list_filter = ('exercise_id', 'is_active', 'is_for_quiz', 'grades')
    search_fields = ('incorrect_text', 'correct_text', 'explanation')
    list_editable = ('is_active', 'is_for_quiz', 'grades')

    def correct_text_short(self, obj):
        return (obj.correct_text[:30] + '...') if len(obj.correct_text) > 30 else obj.correct_text
    correct_text_short.short_description = 'Правильный ответ'


@admin.register(OgeWordOk)
class OgeWordOkAdmin(admin.ModelAdmin):
    list_display = ['preview', 'task_type', 'correct_variants', 'is_active', 'is_for_quiz']
    list_editable = ['is_active', 'is_for_quiz']
    list_filter = ['task_type', 'is_active', 'is_for_quiz', 'grades']
    search_fields = ['text', 'correct_variants']

    def preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
