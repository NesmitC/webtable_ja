# main/admin.py
from django.contrib import admin
from django import forms
from django.db import models
from django.urls import reverse
from django.utils.html import format_html
from .models import (CorrectAnswer, Orthogram, OrthogramExample, Punktum, 
                     PunktumExample, TextAnalysisTask, TextAnalysisTask2326, TextQuestion, QuestionOption, 
                     OrthoepyWord, CorrectionExercise, TaskGrammaticEight, 
                     TaskGrammaticEightExample, TaskGrammaticTwoTwo, 
                     TaskGrammaticTwoTwoExample, TaskPaponim, WordOk,
                     DiagnosticAttempt, TutorInvite, LLMCache, BotLog,
)
from django.contrib.admin.actions import delete_selected
from django.db.models.functions import Cast
from django.db.models import IntegerField
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserProfile
from datetime import timedelta
from django.shortcuts import render, redirect
from django.utils import timezone



# Снимаем стандартную регистрацию User
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    ordering = ['date_joined']


class MainAdminSite(admin.AdminSite):
    def get_app_list(self, request):
        app_list = super().get_app_list(request)
        app_list.append({
            'name': 'Проверка планингов',
            'app_label': 'planning_check',
            'models': [{
                'name': 'Проверить слова из планингов',
                'object_name': 'planning_check',
                'admin_url': reverse('admin:planning-check'),
                'view_only': True,
            }]
        })
        return app_list


@admin.register(DiagnosticAttempt)
class DiagnosticAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'created_at', 'user', 'test_code',
        'score', 'max_score', 'is_reviewed_by_teacher', 'access_code',
    )
    list_filter = ('is_reviewed_by_teacher', 'is_completed', 'test_code')
    search_fields = ('access_code', 'user__username', 'user__email')
    readonly_fields = (
        'id', 'session_key', 'answers_data', 'weak_topics', 'created_at',
    )
    ordering = ('-created_at',)
    list_per_page = 25

# ... DiagnosticAttemptAdmin остаётся как есть ...


# === Выдача премиум-доступа вручную (без ЮKassa) ===
PREMIUM_PLAN = 'premium'

class GrantPremiumForm(forms.Form):
    days = forms.IntegerField(
        min_value=1, initial=30,
        label='На сколько дней выдать доступ',
        help_text='30 — месяц · 270 — 9 месяцев · 365 — год',
    )

@admin.action(description='🎓 Выдать премиум-доступ')
def grant_premium(modeladmin, request, queryset):
    if 'apply' in request.POST:
        form = GrantPremiumForm(request.POST)
        if form.is_valid():
            days = form.cleaned_data['days']
            now = timezone.now()
            for profile in queryset:
                # продление от max(сейчас, текущее окончание): остаток не сгорает
                base = profile.plan_until if (profile.plan_until and profile.plan_until > now) else now
                profile.plan = PREMIUM_PLAN
                profile.plan_until = base + timedelta(days=days)
                profile.save(update_fields=['plan', 'plan_until'])
            modeladmin.message_user(request, f'Премиум выдан: {queryset.count()} на {days} дн.')
            return redirect(request.get_full_path())
    else:
        form = GrantPremiumForm()

    return render(request, 'admin/grant_premium_form.html', {
        'form': form,
        'profiles': queryset,
        'title': 'Выдать премиум-доступ',
    })


class UserProfileAdmin(admin.ModelAdmin):
    actions = [grant_premium]          # ← вот сюда
    list_display = ('user', 'registered_at', 'plan', 'plan_until', 'trial_until', 'role', 'tutor_active', 'email_confirmed')
    list_filter = ('plan',)
    search_fields = ('user__username', 'user__email')
    fields = ('plan', 'plan_until', 'trial_until', 'role', 'tutor_active')
    ordering = ('-user__date_joined',)   # свежие регистрации сверху по умолчанию

    @admin.display(description='Регистрация', ordering='user__date_joined')
    def registered_at(self, obj):
        return timezone.localtime(obj.user.date_joined).strftime('%d.%m.%Y %H:%M')

if not admin.site.is_registered(UserProfile):
    admin.site.register(UserProfile, UserProfileAdmin)


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

class OrthogramExampleForm(forms.ModelForm):
    """Резиновые многострочные поля Text и Masked word для длинных предложений"""
    class Meta:
        model = OrthogramExample
        fields = '__all__'
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'style': 'width: 100%;'}),
            'masked_word': forms.Textarea(attrs={'rows': 3, 'style': 'width: 100%;'}),
        }


@admin.register(OrthogramExample)
class OrthogramExampleAdmin(admin.ModelAdmin):
    form = OrthogramExampleForm
    list_display = ['text', 'orthogram', 'masked_word', 'grades', 'difficulty', 'is_for_quiz', 'is_active', 'planning_check_link']
    actions = ['delete_selected']
    list_filter = ['orthogram', 'difficulty', 'is_for_quiz', 'is_active']
    search_fields = ['text', 'masked_word', 'incorrect_variant', 'grades']
    list_editable = ['grades', 'is_for_quiz', 'is_active']

    fieldsets = (
        (None, {
            'fields': ('orthogram', 'text', 'masked_word', 'incorrect_variant', 'explanation', 'grades')
        }),
        ('Настройки', {
            'fields': ('difficulty', 'is_for_quiz', 'is_active'),
            'description': '<strong>Важно:</strong> Поле "Grades" указывает, для каких классов предназначен этот пример.'
        }),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "orthogram":
            from django.db.models import IntegerField
            from django.db.models.functions import Cast
            kwargs["queryset"] = Orthogram.objects.annotate(
                id_int=Cast('id', IntegerField())
            ).order_by('id_int')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def planning_check_link(self, obj=None):
        from django.utils.html import format_html
        return format_html(
            '<a href="/admin/planning-check/" target="_blank" style="color:#007bff;text-decoration:none;">🔍 Проверить слова</a>'
        )
    planning_check_link.short_description = 'Действия'
    planning_check_link.allow_tags = True

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        from django.db.models import IntegerField
        from django.db.models.functions import Cast
        return qs.annotate(
            ortho_id_int=Cast('orthogram_id', IntegerField())
        ).order_by('ortho_id_int', 'text')

    class Media:
        css = {'all': ('css/admin.css',)}


# ===== ЗАДАНИЯ 17-22 ==================================================
@admin.register(Punktum)
class PunktumAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'rule')
    search_fields = ('id', 'name')


@admin.register(PunktumExample)
class PunktumExampleAdmin(admin.ModelAdmin):
    list_display = ('text', 'punktum', 'is_active', 'added_by', 'created_at')
    list_filter = ('is_active', 'punktum', 'added_by', 'grades')
    search_fields = ('text', 'masked_word')
    readonly_fields = ('created_at',)

    def get_queryset(self, request):
        """По умолчанию — по номеру пунктограммы: 1600, 1700, ... (числовая сортировка)"""
        qs = super().get_queryset(request)
        return qs.extra(select={'punktum_int': 'CAST(punktum_id AS INTEGER)'}).order_by('punktum_int', 'id')

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
    """Блок «Тексты для анализа 1–3» (микротексты)"""
    list_display = ['title', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    inlines = [TextQuestionInline]
    search_fields = ['title', 'text_content']
    exclude = ['task_type']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(task_type='1_3')

    def get_changeform_initial_data(self, request):
        return {'task_type': '1_3'}

    def save_model(self, request, obj, form, change):
        obj.task_type = '1_3'
        super().save_model(request, obj, form, change)


@admin.register(TextAnalysisTask2326)
class TextAnalysisTask2326Admin(admin.ModelAdmin):
    """Блок «Тексты для анализа 23–26» (макротексты)"""
    list_display = ['title', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    inlines = [TextQuestionInline]
    search_fields = ['title', 'text_content']
    exclude = ['task_type']

    def get_queryset(self, request):
        return super().get_queryset(request).filter(task_type='23_26')

    def get_changeform_initial_data(self, request):
        return {'task_type': '23_26'}

    def save_model(self, request, obj, form, change):
        obj.task_type = '23_26'
        super().save_model(request, obj, form, change)

@admin.register(TextQuestion)
class TextQuestionAdmin(admin.ModelAdmin):
    list_display = ['task', 'question_number', 'question_type']
    list_filter = ['question_type']
    inlines = [QuestionOptionInline]
    search_fields = ['question_text', 'task__title']



# ===== ЗАДАНИЕ 5 ===================================================
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


# ===== ЗАДАНИЕ 6 ===================================================
@admin.register(TaskPaponim)
class TaskPaponimAdmin(admin.ModelAdmin):
    list_display = ['preview', 'root', 'has_error', 'is_active', 'is_for_quiz']
    list_editable = ['is_active', 'is_for_quiz']
    list_filter = ['is_active', 'is_for_quiz', 'root']
    search_fields = ['text', 'correct_word', 'root']

    def get_ordering(self, request):
        # Алфавитная сортировка по корню (А–Я), без учёта регистра:
        # одинаковые корни стоят рядом — видно, что уже внесено
        from django.db.models.functions import Lower
        return [Lower('root')]

    def preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    preview.short_description = "Предложение"

    def has_error(self, obj):
        return obj.has_error
    has_error.boolean = True
    has_error.short_description = "С ошибкой"


# ===== ЗАДАНИЕ 7 ===================================================
@admin.register(WordOk)
class WordOkAdmin(admin.ModelAdmin):
    list_display = ['preview', 'task_type', 'correct_variants', 'is_active', 'is_for_quiz']
    list_editable = ['is_active', 'is_for_quiz']
    list_filter = ['task_type', 'is_active', 'is_for_quiz', 'grades']
    search_fields = ['text', 'correct_variants', 'explanation']
    fields = ['text', 'task_type', 'correct_variants', 'explanation', 'is_active', 'is_for_quiz', 'grades']

    def preview(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text


# ===== ЗАДАНИЕ 8 ===================================================
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


# ===== ЗАДАНИЕ 9 ===================================================
@admin.register(TaskGrammaticEight)
class TaskGrammaticEightAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_id_display', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']
    search_fields = ['id']


@admin.register(TaskGrammaticEightExample)
class TaskGrammaticEightExampleAdmin(admin.ModelAdmin):
    list_display = ['preview', 'has_error', 'error_type', 'is_active', 'is_for_quiz']
    list_filter = ['has_error', 'error_type', 'is_active', 'is_for_quiz', 'grades']
    list_editable = ['is_active', 'is_for_quiz']
    
    def preview(self, obj):
        return (obj.text[:60] + '…') if len(obj.text) > 60 else obj.text

# ===== ЗАДАНИЕ 23 ===================================================
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
    RagTopic,
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
    list_display = ['id', 'name', 'is_active']
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
    list_display = ('id', 'name', 'letters', 'rule')
    search_fields = ('id', 'name')

@admin.register(OgePunktumExample)
class OgePunktumExampleAdmin(admin.ModelAdmin):
    list_display = ('short_text', 'punktum', 'explanation', 'is_active', 'created_at')
    list_filter = ('is_active', 'punktum', 'grades')
    search_fields = ('text', 'masked_word')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'punktum_letters_display')
    exclude = ('correct_letters', 'added_by', 'is_user_added', 'source_field')

    fields = (
        'punktum',
        'punktum_letters_display',
        'text',
        'masked_word',
        'explanation',
        'difficulty',
        'is_active',
        'is_for_quiz',
        'grades',
        'created_at',
    )

    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 3, 'cols': 80})},
    }

    class Media:
        js = ('js/admin_punktum_example.js',)

    def short_text(self, obj):
        return (obj.text[:70] + '…') if len(obj.text) > 70 else obj.text
    short_text.short_description = 'Текст'

    def punktum_letters_display(self, obj):
        if obj.punktum_id:
            letters = obj.punktum.get_letters_list()
            return 'Варианты ответов: ' + ', '.join(letters)
        return '—'
    punktum_letters_display.short_description = 'Варианты из правила'


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

@admin.register(TutorInvite)
class TutorInviteAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_active', 'used_by', 'used_at')
    list_filter = ('is_active',)


PREMIUM_PLAN = 'premium'   # код из PLAN_LEVEL / PLAN_PRICES


class GrantPremiumForm(forms.Form):
    days = forms.IntegerField(
        min_value=1, initial=30,
        label='На сколько дней выдать доступ',
        help_text='30 — месяц · 270 — 9 месяцев · 365 — год',
    )


@admin.action(description='🎓 Выдать премиум-доступ')
def grant_premium(modeladmin, request, queryset):
    # Второй заход после заполнения формы — применяем
    if 'apply' in request.POST:
        form = GrantPremiumForm(request.POST)
        if form.is_valid():
            days = form.cleaned_data['days']
            now = timezone.now()
            for profile in queryset:
                # продление от max(сейчас, текущее окончание): остаток не сгорает
                base = profile.plan_until if (profile.plan_until and profile.plan_until > now) else now
                profile.plan = PREMIUM_PLAN
                profile.plan_until = base + timedelta(days=days)
                profile.save(update_fields=['plan', 'plan_until'])
            modeladmin.message_user(
                request, f'Премиум выдан: {queryset.count()} на {days} дн.')
            return redirect(request.get_full_path())
    else:
        form = GrantPremiumForm()

    return render(request, 'admin/grant_premium_form.html', {
        'form': form,
        'profiles': queryset,
        'title': 'Выдать премиум-доступ',
    })


# === Лог запросов к ИИ (аналитика качества ассистента) ===
from .models import AiQueryLog

@admin.register(AiQueryLog)
class AiQueryLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "specialist", "intent", "short_message", "duration_ms", "short_error")
    list_filter = ("specialist", "intent")
    search_fields = ("message", "reply", "user__username")
    readonly_fields = ("user", "message", "intent", "specialist", "reply", "guessed_word",
                       "duration_ms", "error", "chat_message", "created_at")
    ordering = ("-created_at",)
    list_per_page = 50

    @admin.display(description="Вопрос")
    def short_message(self, obj):
        return obj.message[:60]

    @admin.display(description="Ошибка")
    def short_error(self, obj):
        return obj.error[:40] if obj.error else ""

# ===== РЕЕСТР ТЕМ RAG ===================================================
@admin.register(RagTopic)
class RagTopicAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_ready', 'live_examples', 'source')
    list_editable = ('is_ready',)
    list_filter = ('is_ready',)
    fields = ('name', 'code', 'description', 'source', 'is_ready', 'order')
    readonly_fields = ('code',)

    def live_examples(self, obj):
        n = obj.examples_count()
        return n if n >= 0 else 'md'
    live_examples.short_description = 'Примеров в БД'



@admin.register(LLMCache)
class LLMCacheAdmin(admin.ModelAdmin):
    list_display = ('category', 'question', 'provider', 'hits', 'created_at')
    list_filter = ('category', 'provider')
    search_fields = ('question', 'answer')
    readonly_fields = ('cache_key', 'hits', 'created_at')


@admin.register(BotLog)
class BotLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'platform', 'username', 'category', 'question')
    list_filter = ('platform', 'category')
    search_fields = ('question', 'answer', 'username')
    readonly_fields = ('user', 'username', 'platform', 'question', 'answer',
                       'category', 'specialist', 'created_at')
