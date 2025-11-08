# main/admin.py
from django.contrib import admin
from .models import CorrectAnswer, Orthogram, OrthogramExample 


@admin.register(CorrectAnswer)
class CorrectAnswerAdmin(admin.ModelAdmin):
    list_display = ['orthogram_number', 'correct_word', 'description']
    list_filter = ['orthogram_number']
    search_fields = ['correct_word', 'description']
    ordering = ['orthogram_number', 'correct_word']



@admin.register(Orthogram)
class OrthogramAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'letters', 'grades']
    list_editable = ['grades']  # можно быстро редактировать
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

@admin.register(OrthogramExample)
class OrthogramExampleAdmin(admin.ModelAdmin):
    list_display = ['text', 'orthogram', 'masked_word', 'grades', 'difficulty', 'is_for_quiz', 'is_active']
    fieldsets = (
        (None, {
            'fields': ('orthogram', 'text', 'masked_word', 'incorrect_variant', 'explanation', 'grades')
        }),
        ('Настройки', {
            'fields': ('difficulty', 'is_for_quiz', 'is_active'),
            'description': '<strong>Важно:</strong> Поле "Grades" указывает, для каких классов предназначен этот пример. Орфограмма может быть актуальна для всех классов, но конкретное слово — только для одного.'
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