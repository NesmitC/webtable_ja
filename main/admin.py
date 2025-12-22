# main/admin.py
from django.contrib import admin
from django import forms
from django.db import models 
from .models import CorrectAnswer, Orthogram, OrthogramExample, Punktum, PunktumExample, TextAnalysisTask, TextQuestion, QuestionOption, OrthoepyWord, CorrectionExercise
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


# =======================================================================
# @admin.register(OrthoepyWord)
# class OrthoepyWordAdmin(admin.ModelAdmin):
#     list_display = ['word_base', 'correct_variant', 'get_variants_count', 'difficulty', 'is_active', 'is_for_quiz']
#     list_filter = ['difficulty', 'is_active', 'is_for_quiz']
#     search_fields = ['word_base', 'correct_variant']
#     list_editable = ['is_active', 'is_for_quiz', 'difficulty']
#     fieldsets = (
#         ('Основная информация', {
#             'fields': ('word_base', 'correct_variant', 'incorrect_variants', 'explanation')
#         }),
#         ('Настройки', {
#             'fields': ('difficulty', 'is_active', 'is_for_quiz')
#         }),
#     )
    
#     def get_variants_count(self, obj):
#         return len(obj.get_incorrect_variants_list()) + 1
#     get_variants_count.short_description = 'Всего вариантов'
    
    

# admin.py - обновленная админка
@admin.register(OrthoepyWord)
class OrthoepyWordAdmin(admin.ModelAdmin):
    list_display = ('correct_variant', 'incorrect_variants_short', 'is_active', 'is_for_quiz', 'grades')
    list_filter = ('is_active', 'is_for_quiz', 'grades')
    search_fields = ('correct_variant', 'incorrect_variants')
    
    # 🔥 Только is_active редактируем в списке (is_for_quiz оставляем для будущего)
    list_editable = ('is_active', 'grades')
    
    fieldsets = (
        ('Слово', {
            'fields': ('correct_variant', 'incorrect_variants'),
            'description': '''
                <strong>Правильный вариант:</strong> бралА<br>
                <strong>Неправильные через запятую:</strong> брАла, бранА
            '''
        }),
        ('Настройки', {
            'fields': ('grades', 'is_active', 'is_for_quiz'),
            'description': '''
                <strong>is_active</strong> - используется в тестах (включите!)<br>
                <strong>is_for_quiz</strong> - для будущих квизов (пока не используется)<br>
                <strong>grades</strong> - для каких классов (9,10,11)
            '''
        }),
    )
    
    def incorrect_variants_short(self, obj):
        """Короткое отображение неправильных вариантов"""
        variants = obj.get_incorrect_variants_list()
        return ', '.join(variants[:2]) if variants else '—'
    
    incorrect_variants_short.short_description = 'Неправильные варианты'
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('correct_variant')


# admin.py
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
