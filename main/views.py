# main/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.core.cache import cache
from django.contrib.auth import login, logout
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from datetime import timedelta
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.utils.html import escape
from django.template.loader import render_to_string
from django.core.mail import send_mail, EmailMultiAlternatives
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.db import transaction, models
from django.db.models import Count, Avg
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.conf import settings
import os
import re
import traceback
import json, secrets, datetime
from pathlib import Path
import logging
import threading
from .forms import CustomUserCreationForm, ProfileForm, CustomAuthenticationForm
from .models import (
    UserExample, UserProfile, OrthogramExample, Orthogram, 
    StudentAnswer, Punktum, PunktumExample, TextAnalysisTask, 
    TextQuestion, QuestionOption, OrthoepyWord, CorrectionExercise, 
    TaskGrammaticEightExample, TaskGrammaticTwoTwo, TaskGrammaticTwoTwoExample, 
    TaskPaponim, WordOk, UserWord, QuizHistory, DiagnosticAttempt,
    TRIAL_DAYS, Payment, PLAN_NAMES, PLAN_PRICES, TutorInvite, FREE_PLANNING_WORDS,
    OrthoepyAttempt, OrthoepyAttemptWord, OrthoepyWordStat,
    LessonView, PaponimView, ChatMessage, AiQueryLog,
    Task9Attempt, Task9AttemptWord, Task9WordStat, CheckpointAttempt,
)
from .models import (
    OgeTextAnalysisTask, OgeTextQuestion, OgeQuestionOption,
    OgeTaskGrammaticEight, OgeTaskGrammaticEightExample,
    OgePunktum, OgePunktumExample,
    OgeOrthogram, OgeOrthogramExample,
    OgeCorrectionExercise, OgeWordOk,
)
import random
from random import sample, choice, randint, shuffle
from django.db.models import Q
from .assistant import get_orchestrator
import re as _re
from django.utils.html import escape as _esc
import html as _pyhtml
from django.urls import reverse, reverse_lazy
from functools import wraps
from django.contrib.auth.views import redirect_to_login
import requests as _requests
from main import bot_core
from django.http import FileResponse, Http404




logger = logging.getLogger('django')


# === Утилиты ===

def extract_correct_letter(text, masked_word, orth_id=None):
    """
    Извлекает правильную букву/буквы из оригинального текста.
    Маска *N* в masked_word может заменять одну или несколько букв.
    """
    try:
        # Находим позицию открывающей скобки маски в masked_word
        mask_start = masked_word.find('*')
        if mask_start == -1:
            return ''
        
        # Находим позицию закрывающей скобки маски
        mask_end = masked_word.find('*', mask_start + 1)
        if mask_end == -1:
            return ''
        
        # В оригинальном text на той же позиции стоит правильная буква/буквы
        if mask_start >= len(text):
            return ''
        
        # Смотрим, что идёт после маски в masked_word
        after_mask = masked_word[mask_end + 1:]
        
        # Ищем эту же последовательность в оригинальном тексте, начиная с позиции маски
        text_from_mask = text[mask_start:]
        
        # Если after_mask не пустой, ищем его вхождение
        if after_mask and after_mask in text_from_mask:
            # Всё, что до after_mask - это искомая буква/буквы
            pos = text_from_mask.find(after_mask)
            return text_from_mask[:pos]
        else:
            # Если after_mask не найден, берём один символ
            char = text[mask_start]
            return '|' if char == '\\' else char
        
    except Exception:
        return ''

def teacher_required(view):
    """Доступ к разборам: staff ИЛИ активный репетитор."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        prof = getattr(request.user, 'profile', None)
        if request.user.is_staff or (prof and prof.role == 'tutor' and prof.tutor_active):
            return view(request, *args, **kwargs)
        return HttpResponseForbidden()
    return wrapper


@login_required
def activate_tutor_code(request):
    if request.method == 'POST':
        code = (request.POST.get('code') or '').strip().upper()
        prof, _ = UserProfile.objects.get_or_create(user=request.user)
        inv = TutorInvite.objects.filter(code=code, is_active=True, used_by__isnull=True).first()
        if inv and prof.role != 'tutor':
            prof.role = 'tutor'
            prof.tutor_active = True
            prof.save()
            inv.used_by = request.user
            inv.used_at = timezone.now()
            inv.save()
            messages.success(request, 'Доступ репетитора активирован')
        else:
            messages.error(request, 'Код не найден, уже использован или отключён')
    return redirect('profile')


def subscription_required(feature):
    """Пропускной пункт: логин → проверка уровня → paywall."""
    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            if not profile.has_access(feature):
                return render(request, 'registration/paywall.html', {'profile': profile}, status=403)
            return view(request, *args, **kwargs)
        return wrapper
    return deco

# оплата, вебхук, активация
YK_API = 'https://api.yookassa.ru/v3'


def _activate_plan(user, plan_code, days=30):
    """Продление от max(сейчас, текущее окончание) — повторная оплата не сжигает остаток."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    now = timezone.now()
    base = profile.plan_until if (profile.plan_until and profile.plan_until > now) else now
    profile.plan = plan_code
    profile.plan_until = base + timedelta(days=days)
    profile.save()
    logger.info(f'Plan activated: {user.username} -> {plan_code} until {profile.plan_until}')


@login_required
def buy_plan(request, plan_code):
    """Создаёт платёж в ЮKassa и уводит на платёжную страницу."""
    if plan_code not in PLAN_PRICES or plan_code == 'free':
        return HttpResponseBadRequest('Неизвестный тариф')
    price = PLAN_PRICES[plan_code]   # цена ТОЛЬКО с сервера, не из браузера
    body = {
        'amount': {'value': f'{price:.2f}', 'currency': 'RUB'},
        'capture': True,
        'confirmation': {
            'type': 'redirect',
            'return_url': request.build_absolute_uri('/pay/success/'),
        },
        'description': f'Нейростат: тариф «{PLAN_NAMES[plan_code]}», 1 месяц',
        'metadata': {'user_id': request.user.id, 'plan': plan_code},
    }
    resp = _requests.post(f'{YK_API}/payments', json=body,
                          auth=(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY),
                          headers={'Idempotence-Key': secrets.token_hex(16)},
                          timeout=15)

    if not (200 <= resp.status_code < 300):
        logger.error(f'YooKassa create failed: {resp.status_code} {resp.text}')
        return JsonResponse({'error': 'Платёжный сервис недоступен, попробуйте позже'}, status=502)
    data = resp.json()
    Payment.objects.create(yk_payment_id=data['id'], user=request.user,
                           plan=plan_code, amount=price, status='pending')
    return redirect(data['confirmation']['confirmation_url'])


@csrf_exempt
def yookassa_webhook(request):
    """Источник правды: активирует подписку ТОЛЬКО по подтверждённому из API платежу."""
    if request.method != 'POST':
        return HttpResponse(status=405)
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    event = payload.get('event')
    yk_id = (payload.get('object') or {}).get('id')
    if not yk_id:
        return HttpResponse(status=200)

    # Перепроверяем статус запросом в API (защита от поддельных уведомлений)
    check = _requests.get(f'{YK_API}/payments/{yk_id}',
                          auth=(settings.YOOKASSA_SHOP_ID, settings.YOOKASSA_SECRET_KEY),
                          timeout=15)
    if check.status_code != 200:
        return HttpResponse(status=200)
    payment = check.json()

    pay = Payment.objects.filter(yk_payment_id=yk_id).first()
    if pay is None:
        return HttpResponse(status=200)   # платёж не наш — игнорируем

    if event == 'payment.succeeded' and payment.get('status') == 'succeeded':
        if pay.status != 'succeeded':     # идемпотентность: ретрай вебхука не продлит дважды
            pay.status = 'succeeded'
            pay.save(update_fields=['status'])
            _activate_plan(pay.user, pay.plan)
            try:
                send_payment_success_emails(pay, amount=payment.get('amount'))
            except Exception:
                logger.exception(f'Не удалось отправить письма об оплате: {yk_id}')

    elif event == 'payment.canceled':
        pay.status = 'canceled'
        pay.save(update_fields=['status'])
    elif event == 'refund.succeeded':
        pay.status = 'refunded'
        pay.save(update_fields=['status'])
        logger.info(f'Refund: {yk_id}')
    return HttpResponse(status=200)


@login_required
def pay_success(request):
    """Возврат из ЮKassa после оплаты.

    Настоящая HTML-страница вместо прежнего redirect('profile'): при редиректе
    счётчик Метрики не успевал выполниться, и главная конверсия сайта — оплата —
    не фиксировалась вовсе.

    Источник правды о платеже — вебхук, а он приходит асинхронно. Поэтому
    страница показывает фактический статус и один раз обновляется сама, если
    вебхук ещё не пришёл (параметр ?wait=1 не даёт зациклиться).
    """
    # ЮKassa возвращает на return_url без идентификатора платежа,
    # поэтому берём последний платёж пользователя.
    pay = Payment.objects.filter(user=request.user).order_by('-created_at').first()

    # Прямой заход на /pay/success/ без платежа конверсией считаться не должен,
    # иначе её можно накрутить простым открытием URL.
    if pay is None:
        return redirect('profile')

    succeeded = pay.status == 'succeeded'
    return render(request, 'registration/payment_success_page.html', {
        'pay': pay,
        'plan_name': PLAN_NAMES.get(pay.plan, pay.plan),
        'succeeded': succeeded,
        'need_refresh': not succeeded and request.GET.get('wait') != '1',
    })

@login_required
def pay_fail(request):
    messages.warning(request, 'Платёж не прошёл. Попробуйте ещё раз или напишите нам в Telegram.')
    return redirect('profile')

def send_payment_success_emails(pay, amount=None):
    """Отправляет два письма об успешной оплате.

    1. Ученику (родителю) — подтверждение оплаты и открытого доступа.
    2. Владельцу — уведомление, чтобы сразу связаться с семьёй.

    Вызывается из вебхука. Любая ошибка здесь НЕ должна ломать платёж —
    на стороне вебхука вызов обёрнут в try/except.

    :param pay: запись Payment (поля user, plan, yk_payment_id).
    :param amount: словарь ЮKassa вида {'value': '990.00', 'currency': 'RUB'}
                   или None, если сумму получить не удалось.
    """
    user = pay.user
    name = user.first_name or user.username

    # Название тарифа: из choices модели либо просто строкой
    try:
        plan_name = pay.get_plan_display()
    except AttributeError:
        plan_name = str(pay.plan)

    cabinet_url = f'{settings.SITE_URL}/profile/'
    admin_url = f'{settings.SITE_URL}/admin/auth/user/{user.id}/change/'

    profile = getattr(user, 'profile', None)
    phone = getattr(profile, 'phone', None) if profile else None

    # --- 1) Письмо ученику / родителю ---------------------------------------------
    if user.email:
        ctx = {
            'name': name,
            'plan_name': plan_name,
            'cabinet_url': cabinet_url,
        }
        body = render_to_string('registration/payment_success_user.html', ctx)
        EmailMultiAlternatives(
            subject='Оплата получена — доступ к занятиям открыт',
            body=body,          # в шаблоне нет HTML-разметки — шлём как обычный текст
            to=[user.email],
        ).send(fail_silently=False)
        logger.info(f'Письмо об оплате отправлено: {user.email}')
    else:
        logger.warning(f'Письмо об оплате не отправлено: у пользователя {user.id} нет email')

    # --- 2) Уведомление владельцу --------------------------------------------------
    owner_ctx = {
        'name': name,
        'email': user.email or '—',
        'phone': phone,
        'plan_name': plan_name,
        'amount': amount,
        'payment_id': pay.yk_payment_id,
        'admin_url': admin_url,
    }
    owner_html = render_to_string('registration/payment_success_owner.html', owner_ctx)
    owner_text = (
        f'Новая оплата на Нейростате.\n\n'
        f'Ученик: {name}\n'
        f'Email: {owner_ctx["email"]}\n'
        + (f'Телефон: {phone}\n' if phone else '')
        + f'Тариф: {plan_name}\n'
        + (f'Сумма: {amount["value"]} {amount["currency"]}\n' if amount else '')
        + f'Платёж ЮKassa: {pay.yk_payment_id}\n\n'
        + f'Профиль в админке: {admin_url}\n\n'
        + 'Хороший момент, чтобы написать семье и спланировать занятия.'
    )
    msg = EmailMultiAlternatives(
        subject=f'💰 Оплата: {name} — {plan_name}',
        body=owner_text,                     # текстовый запасной вариант
        to=[settings.OWNER_NOTIFY_EMAIL],
    )
    msg.attach_alternative(owner_html, 'text/html')   # красивая версия с таблицей и кнопкой
    msg.send(fail_silently=False)





def validate_orthogram_ids(ids):
    """Преобразует строковые/списочные ID орфограмм в список целых чисел."""
    if not isinstance(ids, list):
        ids = [x.strip() for x in str(ids).split(',') if x.strip()]
    result = []
    for oid in ids:
        try:
            result.append(int(oid))
        except (ValueError, TypeError):
            continue
    return result

def _normalize_text(text):
    """
    Унифицированная нормализация текста для сравнения ответов.
    - Приводит к нижнему регистру
    - Заменяет ё → е
    - Удаляет ВСЕ пробелы (чтобы "в связи с" == "всвязис")
    """
    if not text:
        return ''
    if not isinstance(text, str):
        text = str(text)
    text = text.strip().lower()
    text = text.replace('ё', 'е')
    text = text.replace(' ', '')  # Удаляем все пробелы
    return text


def _normalize_digits(s):
    """Извлекает только цифры из строки."""
    if not isinstance(s, str):
        s = str(s)
    return ''.join(filter(str.isdigit, s))


# === Основные представления ===

def index(request):
    return render(request, 'index.html')

def privacy(request):
    """Политика обработки персональных данных (отдельная страница + источник для модального окна)."""
    return render(request, 'privacy.html')

def terms(request):
    """Пользовательское соглашение (оферта)."""
    return render(request, 'terms.html')

@subscription_required('planning')
def planning_5kl(request):
    return render(request, 'planning_5kl.html')

@subscription_required('planning')
def planning_6kl(request):
    return render(request, 'planning_6kl.html')

@subscription_required('planning')
def planning_7kl(request):
    return render(request, 'planning_7kl.html')

@subscription_required('planning')
def planning_8kl(request):
    return render(request, 'planning_8kl.html')

@subscription_required('planning')
def planning_9kl(request):
    return render(request, 'planning_9kl.html')


def ege(request):
    return render(request, 'ege.html')


def oge(request):
    return render(request, 'oge.html')


def starting_diagnostic_oge(request):
    return render(request, 'diagnostic_oge.html')

@subscription_required('targetn')
def targetn(request):
    return render(request, 'games_html/targetn.html')


# === ДАШБОРД СТАТИСТИКИ ===
def _planning_url(profile):
    try:
        g = int(profile.grade)
    except (ValueError, TypeError):
        g = None
    if g and 5 <= g <= 9:
        return reverse(f'planning_{g}kl')
    return reverse('planning_5kl')


def _extract_essay_from_diagnostic(diag):
    """Достаёт самоопределённый балл за сочинение (задание 27) из user_answers."""
    data = diag.answers_data or {}
    if not isinstance(data, dict):
        return None
    user_answers = data.get('user_answers', {})
    raw = user_answers.get('27')
    if raw is None:
        return None
    try:
        score = float(raw)
        return max(0.0, min(score, 22.0))   # ограничиваем диапазоном 0–22
    except (TypeError, ValueError):
        return None


def statistic(request):
    """Страница статистики (Дашборд)"""
    if not request.user.is_authenticated:
        return render(request, 'statistic.html', {'is_auth': False})

    from .models import (UserWord, QuizHistory, OrthoepyAttempt, OrthoepyWordStat,
                         StudentAnswer, DiagnosticAttempt, LessonView, PaponimView,
                         EssayScore, DailyWord)

    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # === Диагностика ===
    diagnostics = list(user.diagnostic_attempts.filter(is_completed=True).order_by('-created_at'))
    diag_count = len(diagnostics)
    diag_avg = None
    if diagnostics:
        rates = [d.score / d.max_score * 100 for d in diagnostics if d.max_score]
        diag_avg = round(sum(rates) / len(rates)) if rates else None

    # Три типа диагностик для блока «Диагностика»
    diag_starting = user.diagnostic_attempts.filter(
        is_completed=True, diagnostic_type='starting'
    ).order_by('-created_at').first()
    diag_current = user.diagnostic_attempts.filter(
        is_completed=True, diagnostic_type='current'
    ).order_by('-created_at').first()
    diag_final = user.diagnostic_attempts.filter(
        is_completed=True, diagnostic_type='final'
    ).order_by('-created_at').first()

    # Вычисляем primary_score, если его нет
    for diag in [diag_starting, diag_current, diag_final]:
        if diag and diag.primary_score is None and diag.answers_data:
            try:
                p, _ = compute_primary_secondary(diag.answers_data)
                diag.primary_score = p
                diag.save(update_fields=['primary_score'])
            except Exception:
                pass

    # Последняя диагностика для блока «Диагностика» (для обратной совместимости)
    last_diag = diagnostics[0] if diagnostics else None
    if last_diag and last_diag.primary_score is None and last_diag.answers_data:
        try:
            p, _ = compute_primary_secondary(last_diag.answers_data)
            last_diag.primary_score = p
            last_diag.save(update_fields=['primary_score'])
        except Exception:
            pass

    # === Уроки ===
    lessons_viewed = LessonView.objects.filter(user=user).count()
    cp9_qs = CheckpointAttempt.objects.filter(user=user, checkpoint_code='cp9')
    cp9_passed = cp9_qs.filter(passed=True).exists()
    cp_stats = {
        'passed': cp9_qs.filter(passed=True).count(),
        'failed': cp9_qs.filter(passed=False).count(),
        'passed_bool': cp9_passed,
        'best': max([a.correct_count for a in cp9_qs], default=0),
    }

    # === Паронимы ===
    paponims_viewed = PaponimView.objects.filter(user=user).count()

    # === Сочинение (ЕГЭ): балл из задания 27 последней диагностики ===
    essay_score = _extract_essay_from_diagnostic(diagnostics[0]) if diagnostics else None
    if essay_score is None:
        essay_obj = EssayScore.objects.filter(user=user).first()
        essay_score = essay_obj.score if essay_obj else 0
    essay_max = 22

    # === Словарь ударений ===
    ortho_total = OrthoepyAttempt.objects.filter(user=user).count()
    ortho_in_correction = OrthoepyWordStat.objects.filter(user=user, in_correction=True).count()

    # === Тренажёры ===
    tasks_total = StudentAnswer.objects.filter(user=user).count()
    tasks_correct = StudentAnswer.objects.filter(user=user, is_correct=True).count()
    tasks_rate = round(tasks_correct / tasks_total * 100) if tasks_total else 0

    # === Планинг ===
    planning_qs = UserWord.objects.filter(user=user, is_active=True)
    planning_total = planning_qs.count()
    planning_weak = planning_qs.filter(error_count__gt=0).count()

    # === Квизы ===
    quiz_total = QuizHistory.objects.filter(user=user).count()
    quiz_correct = QuizHistory.objects.filter(user=user, was_correct=True).count()
    quiz_rate = round(quiz_correct / quiz_total * 100) if quiz_total else 0

    # === Слово дня ===
    daily_answered = DailyWord.objects.filter(user=user, answered=True).count()

    # === График ===
    chart = _stat_chart(user, 'month')

    # === Метрики для блока «Прогресс» ===
    days_on_platform = max((timezone.now().date() - user.date_joined.date()).days, 0)
    quiz_all = QuizHistory.objects.filter(user=user).count()
    quiz_correct_all = QuizHistory.objects.filter(user=user, was_correct=True).count()
    tasks_all = StudentAnswer.objects.filter(user=user).count()
    tasks_correct_all = StudentAnswer.objects.filter(user=user, is_correct=True).count()
    total_answers_all = quiz_all + tasks_all
    correct_answers_all = quiz_correct_all + tasks_correct_all
    overall_rate = round(correct_answers_all / total_answers_all * 100) if total_answers_all else 0
    trend = _stat_week_trend(user)

    context = {
        'is_auth': True,
        # Диагностика
        'diagnostics': diagnostics,
        'diag_count': diag_count,
        'diag_avg': diag_avg,
        'last_diag': last_diag,
        'diag_starting': diag_starting,
        'diag_current': diag_current,
        'diag_final': diag_final,
        # Уроки и паронимы
        'lessons_viewed': lessons_viewed,        'cp_stats': cp_stats,
        'cp_attempts': list(cp9_qs),
        'paponims_viewed': paponims_viewed,
        # Сочинение
        'essay_score': essay_score,
        'essay_max': essay_max,
        # Орфоэпия
        'ortho_total': ortho_total,
        'ortho_in_correction': ortho_in_correction,
        # Тренажёры
        'tasks_total': tasks_total,
        'tasks_rate': tasks_rate,
        # Планинг
        'planning_total': planning_total,
        'planning_weak': planning_weak,
        'planning_url': _planning_url(profile),
        # Квизы
        'quiz_total': quiz_total,
        'quiz_rate': quiz_rate,
        # Слово дня
        'daily_answered': daily_answered,
        # Рекомендации
        'recommendations': _stat_recommendations(user, profile),
        # График
        'chart_labels_json': json.dumps(chart['labels']),
        'chart_data_json': json.dumps(chart['data']),
        'days_on_platform_text': _ru_days(days_on_platform),
        'total_answers_all': total_answers_all,
        'overall_rate': overall_rate,
        'trend_arrow': trend['arrow'],
        'trend_color': trend['color'],
        'trend_text': trend['text'],
        'chart_has_data': chart['has_data'],
    }
    return render(request, 'statistic.html', context)


def _ru_days(n):
    m10, m100 = n % 10, n % 100
    if 11 <= m100 <= 14:
        return f'{n} дней'
    if m10 == 1:
        return f'{n} день'
    if 2 <= m10 <= 4:
        return f'{n} дня'
    return f'{n} дней'


def _stat_chart(user, period='month'):
    """
    Успешность (квизы + задания) за период.
    period: 'month' — по дням, 31 день
            '3months' — по неделям, 91 день
            'all' — по неделям, с момента регистрации
    """
    from .models import QuizHistory, StudentAnswer
    today = timezone.now().date()
    joined = user.date_joined.date()

    if period == 'all':
        days = max((today - joined).days, 0) + 1
        by_week = True
    elif period == '3months':
        days = 91
        by_week = True
    else:
        days = 31
        by_week = False
    days = max(days, 1)
    start = today - timedelta(days=days - 1)

    buckets = {}

    def add(ts, correct):
        d = ts.date()
        if d < start:
            return
        key = (d - timedelta(days=d.weekday())) if by_week else d
        slot = buckets.setdefault(key, {'total': 0, 'correct': 0})
        slot['total'] += 1
        if correct:
            slot['correct'] += 1

    for h in QuizHistory.objects.filter(user=user, answer_time__date__gte=start):
        add(h.answer_time, h.was_correct)
    for a in StudentAnswer.objects.filter(user=user, answered_at__date__gte=start):
        add(a.answered_at, a.is_correct)

    labels, data = [], []
    if by_week:
        w = start - timedelta(days=start.weekday())
        while w <= today:
            labels.append(w.strftime('%m.%y') if period == 'all' else w.strftime('%d.%m'))
            slot = buckets.get(w)
            data.append(round(slot['correct'] / slot['total'] * 100) if slot and slot['total'] else None)
            w += timedelta(days=7)
    else:
        for i in range(days):
            d = start + timedelta(days=i)
            labels.append(d.strftime('%d.%m'))
            slot = buckets.get(d)
            data.append(round(slot['correct'] / slot['total'] * 100) if slot and slot['total'] else None)

    return {'labels': labels, 'data': data,
            'has_data': any(x is not None for x in data)}


def _stat_week_trend(user):
    """Успешность за последние 7 дней против предыдущих 7 дней."""
    from .models import QuizHistory, StudentAnswer
    today = timezone.now().date()
    recent_start = today - timedelta(days=6)
    prev_start = today - timedelta(days=13)

    recent = {'total': 0, 'correct': 0}
    prev = {'total': 0, 'correct': 0}

    for h in QuizHistory.objects.filter(user=user, answer_time__date__gte=prev_start):
        bucket = recent if h.answer_time.date() >= recent_start else prev
        bucket['total'] += 1
        if h.was_correct:
            bucket['correct'] += 1
    for a in StudentAnswer.objects.filter(user=user, answered_at__date__gte=prev_start):
        bucket = recent if a.answered_at.date() >= recent_start else prev
        bucket['total'] += 1
        if a.is_correct:
            bucket['correct'] += 1

    def rate(b):
        return round(b['correct'] / b['total'] * 100) if b['total'] else None

    recent_rate = rate(recent)
    prev_rate = rate(prev)

    if recent_rate is None and prev_rate is None:
        return {'arrow': '·', 'color': '#888', 'text': 'Пока нет данных для трендов'}
    if recent_rate is None:
        return {'arrow': '·', 'color': '#888', 'text': 'Пока нет данных для трендов'}
    if prev_rate is None:
        return {'arrow': '·', 'color': '#888', 'text': 'Недостаточно данных для сравнения'}

    diff = recent_rate - prev_rate
    if diff > 0:
        return {'arrow': '↑', 'color': '#28a745', 'text': f'+{diff}% к прошлой неделе'}
    if diff < 0:
        return {'arrow': '↓', 'color': '#dc3545', 'text': f'{diff}% к прошлой неделе'}
    return {'arrow': '→', 'color': '#888', 'text': 'Без изменений к прошлой неделе'}


@login_required
def stats_progress_api(request):
    """Данные графика прогресса за выбранный период."""
    period = request.GET.get('period', 'month')
    if period not in ('month', '3months', 'all'):
        period = 'month'
    return JsonResponse(_stat_chart(request.user, period))


def _stat_anti_rating(user, limit=8):
    """Слова с наибольшим числом ошибок за всё время."""
    from .models import QuizHistory, OrthogramExample
    errors = {}
    for h in QuizHistory.objects.filter(user=user, was_correct=False).only('word_id'):
        errors[h.word_id] = errors.get(h.word_id, 0) + 1
    top = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:limit]
    if not top:
        return []
    words = {w.id: w for w in OrthogramExample.objects.filter(id__in=[w for w, _ in top])}
    return [{'text': words[w].text, 'errors': c} for w, c in top if w in words]


def _stat_recommendations(user, profile):
    """Персональный план: с чего начать завтра."""
    from .models import QuizHistory, OrthoepyWordStat, UserWord
    recs = []

    # 1. Ударения, которые сейчас на отработке
    ortho_corr = OrthoepyWordStat.objects.filter(user=user, in_correction=True).count()
    if ortho_corr:
        recs.append({'icon': '🎯', 'priority': 1,
                     'text': f'Отработай {ortho_corr} слов с ударениями, в которых были ошибки',
                     'link': reverse('orthoepy_trening'), 'link_text': 'К тренажёру ударений'})

    # 2. Самые слабые правила за месяц
    month_ago = timezone.now() - timedelta(days=30)
    weak = (QuizHistory.objects
            .filter(user=user, was_correct=False, answer_time__gte=month_ago,
                    word__orthogram__isnull=False)
            .values('word__orthogram__name')
            .annotate(errors=Count('id'))
            .order_by('-errors')[:2])
    for o in weak:
        recs.append({'icon': '📖', 'priority': 2,
                     'text': f"Повтори правило «{o['word__orthogram__name']}» — {o['errors']} ошибок за месяц",
                     'link': reverse('trainers_ege'), 'link_text': 'К тренажёрам'})

    # 3. Слова планинга с ошибками
    planning_weak = UserWord.objects.filter(user=user, is_active=True, error_count__gt=0).count()
    if planning_weak:
        recs.append({'icon': '✍️', 'priority': 3,
                     'text': f'Повтори {planning_weak} слов из планинга, в которых были ошибки',
                     'link': _planning_url(profile), 'link_text': 'К планингу'})

    # 4. Слабые задания последней диагностики
    last_diag = user.diagnostic_attempts.filter(is_completed=True).order_by('-created_at').first()
    if last_diag and last_diag.weak_topics:
        nums = [str(t) for t in list(last_diag.weak_topics)[:4]]
        recs.append({'icon': '📋', 'priority': 4,
                     'text': f"Проработай задания {', '.join(nums)} по итогам последней диагностики",
                     'link': reverse('trainers_ege'), 'link_text': 'К тренажёрам'})

    # 5. Если совсем ничего не нашлось
    if not recs:
        recs.append({'icon': '🚀', 'priority': 5,
                     'text': 'Начни с короткого квиза, чтобы размяться',
                     'link': reverse('quizzes_ege'), 'link_text': 'К квизам'})
        recs.append({'icon': '🩺', 'priority': 6,
                     'text': 'Пройди диагностику, чтобы найти слабые места',
                     'link': reverse('diagnostics_ege'), 'link_text': 'К диагностикам'})

    recs.sort(key=lambda r: r['priority'])
    return recs[:5]


def custom_logout(request):
    logout(request)
    return redirect('/')  # Перенаправление на главную


def diagnostics(request):
    return render(request, 'diagnostics_ege.html')


def demo_ege(request):
    return render(request, 'demo_ege.html')

@login_required
def trainers_ege(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'trainers_ege.html', {'level': profile.level})

@subscription_required('paponim_trening')
def paponim_trening(request):
    """Онлайн-словник паронимов (статическая страница, без БД)."""
    return render(request, 'paponim_trening.html')

@login_required
def quizzes_ege(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'quizzes_ege.html', {
        'subscription': profile.subscription_info(),
        'level': profile.level,
    })

@subscription_required('lessons')
def lessons_ege(request):
    cp9 = CheckpointAttempt.objects.filter(
        user=request.user, checkpoint_code='cp9')
    return render(request, 'lessons_ege.html', {
        'cp9_passed': cp9.filter(passed=True).exists(),
        'cp9_attempts': cp9.count(),
        'cp9_best': max([a.correct_count for a in cp9], default=0),
    })


def diagnostic_result(request, attempt_id):
    attempt = get_object_or_404(DiagnosticAttempt, id=attempt_id)

    # 1. Преподаватель/админ видит всё (зеркальная проверка на встрече)
    if request.user.is_authenticated and request.user.is_staff:
        return render(request, 'test_fix_ege/diagnostic_ege_result.html', {'attempt': attempt})

    # 2. Залогиненный владелец
    if attempt.user:
        if request.user.is_authenticated and attempt.user == request.user:
            return render(request, 'test_fix_ege/diagnostic_ege_result.html', {'attempt': attempt})
        return HttpResponseForbidden()

    # 3. Аноним — только своя сессия (свежий результат до регистрации)
    if attempt.session_key and attempt.session_key == request.session.session_key:
        return render(request, 'test_fix_ege/diagnostic_ege_result.html', {'attempt': attempt})

    return HttpResponseForbidden()





# === Валидация текстовые поля планингов - пользователи вносят примеры слов ===
from django.utils.html import strip_tags
from django.http import JsonResponse

def save_user_inputs(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не разрешён'}, status=405)

    raw = request.POST.get('user-input-orf-13', '')
    
    # 1. Санитизация: удаляем HTML/JS, оставляем только текст и переносы строк
    clean_text = strip_tags(raw).strip()
    
    # 2. Валидация длины
    if len(clean_text) > 500:
        return JsonResponse({'error': 'Лимит: 500 символов'}, status=400)
    
    # 3. Безопасное сохранение (в сессию, БД или кэш)
    request.session['orf_13_input'] = clean_text
    # или: MyModel.objects.create(user=request.user, text=clean_text)
    
    return JsonResponse({'status': 'ok', 'length': len(clean_text)})


# === Аутентификация и профиль ===

def _send_activation_email_bg(user_pk: int, subject: str, body: str, to_email: str) -> None:
    """Отправляет письмо активации в фоновом потоке.

    SMTP с EMAIL_TIMEOUT=10 иначе держит POST-запрос открытым: школьник жмёт
    «Зарегистрироваться» и до 10 секунд смотрит на зависшую кнопку.

    Тема и тело рендерятся в основном потоке, сюда приходят готовыми строками —
    поток не обращается ни к БД, ни к шаблонам. send_mail() сам открывает и
    закрывает соединение, поэтому утечки SMTP-сессий нет.
    """
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email])
    except Exception as e:  # noqa: BLE001
        # Аккаунт создан, но не активирован и письмо не ушло — пользователь
        # застрял. Молча терять регистрацию нельзя, поэтому пишем в лог и
        # уведомляем владельца. Если лежит весь SMTP, это уведомление тоже не
        # отправится — значит, спама при массовой аварии не будет.
        logger.error(f"Письмо активации не отправлено, user_id={user_pk}: {e}")
        try:
            send_mail(
                '❌ Регистрация осталась без письма активации',
                f"Пользователь id={user_pk} ({to_email}) зарегистрировался,\n"
                f"но письмо активации не отправилось — аккаунт неактивен.\n\n"
                f"Ошибка: {e}",
                settings.DEFAULT_FROM_EMAIL,
                [settings.OWNER_NOTIFY_EMAIL],
                fail_silently=True,
            )
        except Exception:  # noqa: BLE001
            pass


def register(request):
    # Получаем IP пользователя
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
    cache_key = f"register_attempts_{ip}"
    
    # Считаем попытки
    attempts = cache.get(cache_key, 0)
    if attempts >= 5: # Максимум 5 регистраций в час с одного IP
        return HttpResponseForbidden("Слишком много попыток. Попробуйте через час.")
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = False
                user.save()

                # === Привязка анонимной диагностики по коду (страховка кросс-устройства) ===
                # Код однозначно идентифицирует попытку независимо от сессии/устройства,
                # поэтому привязываем СРАЗУ при создании user — до письма и активации.
                code = (request.POST.get('access_code') or '').strip().upper()
                if code:
                    bound = DiagnosticAttempt.objects.filter(
                        access_code=code, user__isnull=True
                    ).update(user=user)
                    if bound:
                        logger.info(f"Register-migration by code {code}: {bound} -> {user.username}")

                current_site = get_current_site(request)
                mail_subject = 'Активируйте ваш аккаунт'
                message = render_to_string('registration/confirm_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': default_token_generator.make_token(user),
                    'scheme': 'https' if not settings.DEBUG else 'http',
                })
                # Письмо — в фоновый поток: ответ пользователю не ждёт SMTP.
                threading.Thread(
                    target=_send_activation_email_bg,
                    args=(user.pk, mail_subject, message, user.email),
                    daemon=True,
                ).start()

                cache.set(cache_key, attempts + 1, timeout=3600)

                # PRG: редирект вместо render(). Чинит повторную отправку формы
                # по F5 и даёт Метрике отдельный URL страницы цели — сам POST
                # идёт на тот же /accounts/register/, что неотличимо от
                # простого открытия формы.
                # Флаг в сессии: прямой заход на /accounts/register/done/
                # не должен засчитываться как конверсия.
                request.session['reg_done'] = True
                return redirect('register_done')
            except Exception as e:
                logger.error(f"Ошибка при регистрации: {e}")
                messages.error(request, "Произошла ошибка при регистрации. Попробуйте позже.")
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})



def register_done(request):
    """Страница-цель «Письмо отправлено» (финал PRG после регистрации).

    Отдельный URL нужен потому, что успешный POST идёт на тот же
    /accounts/register/, и Яндекс.Метрика не может отличить отправку формы от
    простого её открытия. Флаг в сессии отсекает прямые заходы на этот адрес:
    иначе конверсию можно накрутить любой перезагрузкой URL.
    """
    if not request.session.pop('reg_done', False):
        return redirect('register')
    return render(request, 'registration/email_sent.html')


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Русское склонение при числительном: 1 день, 2 дня, 5 дней, 21 день.

    Штатный фильтр pluralize тут не годится: он понимает максимум две формы,
    а при трёх аргументах молча возвращает пустую строку.
    """
    n10, n100 = n % 10, n % 100
    if n10 == 1 and n100 != 11:
        return one
    if 2 <= n10 <= 4 and not 12 <= n100 <= 14:
        return few
    return many


@login_required
def account_activated(request):
    """Страница-цель «Аккаунт активирован».

    Фиксирует подтверждение e-mail и старт триала, затем уводит лида в
    wow-момент — на разбор его диагностики.
    """
    next_url = request.session.pop('post_activate_next', None)
    profile = getattr(request.user, 'profile', None)
    return render(request, 'registration/account_activated.html', {
        'next_url': next_url or reverse('index'),
        'trial_until': getattr(profile, 'trial_until', None),
        'trial_days': TRIAL_DAYS,
        'trial_days_word': _plural_ru(TRIAL_DAYS, 'день', 'дня', 'дней'),
    })


def confirm_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.email_confirmed = True
        profile.save()

        if not profile.trial_until:
            profile.trial_until = timezone.now() + timedelta(days=TRIAL_DAYS)
            profile.save()

        
        # 🔹 МИГРАЦИЯ АНОНИМНЫХ ПОПЫТОК
        session_key = request.session.session_key
        if session_key:
            migrated = DiagnosticAttempt.objects.filter(
                session_key=session_key, 
                user__isnull=True
            ).update(user=user)
            if migrated:
                logger.info(f"Мигрировано диагностик: {migrated} → {user.username}")
        
        login(request, user)

        last_attempt = DiagnosticAttempt.objects.filter(user=user).order_by('-created_at').first()
        # Куда вести лида после страницы-цели. Храним в сессии, а не в
        # query-параметре: ссылка активации приходит из письма, дописывать
        # к ней next= нельзя.
        request.session['post_activate_next'] = (
            reverse('student_review', args=[last_attempt.id]) if last_attempt
            else reverse('index')
        )
        # PRG на страницу-цель: её URL и reachGoal фиксируют завершение
        # активации. Прежний редирект на '/' был неотличим от обычного
        # визита, поэтому Метрика не видела эту конверсию.
        return redirect('account_activated')
    
    return render(request, 'registration/invalid_link.html')



@login_required
def profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    diagnostics = request.user.diagnostic_attempts.filter(is_completed=True)

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные успешно сохранены!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    # VK-бот: активный код привязки для ЛК
    vk_code, vk_code_expires = None, None
    if (profile.link_code and profile.link_code_expires
            and profile.link_code_expires > timezone.now()):
        vk_code = profile.link_code
        vk_code_expires = profile.link_code_expires.strftime('%d.%m в %H:%M')

    return render(request, 'profile.html', {
        'form': form,
        'diagnostics': diagnostics,
        'subscription': profile.subscription_info(),
        'vk_link_code': vk_code,
        'vk_link_code_expires': vk_code_expires,
        'vk_bot_url': settings.VK_BOT_LINK,
        'max_bot_url': settings.MAX_BOT_LINK,
        'max_deeplink': f'{settings.MAX_BOT_LINK}?start={vk_code}' if vk_code else None,
    })



class EmailLoginView(DjangoLoginView):
    """Вход по email + автоматическая привязка анонимных диагностик."""
    template_name = 'registration/login.html'
    authentication_form = CustomAuthenticationForm

    def form_valid(self, form):
        old_key = self.request.session.session_key   # анонимный ключ ДО логина
        response = super().form_valid(form)          # здесь login() сменит ключ
        if old_key and self.request.user.is_authenticated:
            n = DiagnosticAttempt.objects.filter(
                session_key=old_key, user__isnull=True
            ).update(user=self.request.user)
            if n:
                logger.info(f"Login-migration: {n} diagnostic(s) -> {self.request.user.username}")
        return response


@login_required
def update_example(request):
    """Обновляет текст слова в планинге"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)
    
    try:
        data = json.loads(request.body)
        example_id = data.get('example_id')
        new_text = data.get('text', '').strip()
        
        if not example_id or not new_text:
            return JsonResponse({'status': 'error', 'message': 'Нет данных'}, status=400)
        
        example = OrthogramExample.objects.get(
            id=example_id, 
            added_by=request.user, 
            is_user_added=True
        )
        
        example.text = new_text
        example.masked_word = new_text  # или можно сгенерировать маску
        example.save()
        
        logger.info(f"✅ Updated example #{example_id}: '{new_text}'")
        return JsonResponse({'status': 'success'})
        
    except OrthogramExample.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Не найдено'}, status=404)
    except Exception as e:
        logger.error(f"❌ Update error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def delete_example(request):
    """Удаляет слово из планинга"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=400)
    
    try:
        data = json.loads(request.body)
        example_id = data.get('example_id')
        
        if not example_id:
            return JsonResponse({'status': 'error', 'message': 'Нет ID'}, status=400)
        
        deleted, _ = OrthogramExample.objects.filter(
            id=example_id,
            added_by=request.user,
            is_user_added=True
        ).delete()
        
        if deleted:
            logger.info(f"✅ Deleted example #{example_id}")
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Не найдено'}, status=404)
            
    except Exception as e:
        logger.error(f"❌ Delete error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



# ✅ API для фронтенда (соответствует urls.py)
def get_orthogram_letters(request, orth_id):
    """
    Возвращает список букв для орфограммы по ID.
    Оптимизировано: грузит только нужное поле из БД.
    """
    try:
        # 🔥 Оптимизация: берем только поле 'letters'
        orth = Orthogram.objects.only('letters').get(id=orth_id)

        if not orth.letters:
            return JsonResponse({'letters': []})

        # Разделяем, убираем пробелы и пустые строки
        letters = [char.strip() for char in orth.letters.split(',') if char.strip()]
        return JsonResponse({'letters': letters})

    except Orthogram.DoesNotExist:
        # Если ID нет в базе — возвращаем дефолтный набор
        return JsonResponse({'letters': ['а', 'о', 'е', 'и', 'я']}, status=404)

    except Exception as e:
        logger.error(f"Ошибка при загрузке букв для орфограммы {orth_id}: {e}")
        return JsonResponse({'letters': ['а', 'о', 'е', 'и', 'я']}, status=500)


def _extract_diff_letters(correct: str, incorrect: str) -> tuple[str, str]:
    """Возвращает первые отличающиеся буквы из двух вариантов."""
    if not correct or not incorrect:
        return '?', '?'
    for c_char, i_char in zip(correct, incorrect):
        if c_char != i_char:
            return c_char, i_char
    return correct[-1] if correct else '?', incorrect[-1] if incorrect else '?'


# === Генерация упражнений ОРФОГРАММ 1 маска ===
logger = logging.getLogger(__name__)

# === вспомогательные функции орф 10 - подгруппы выпадающего списка ===
def format_orthogram_masks(examples, is_multi_line=False):
    """
    Упрощенная версия - всегда возвращаем ВСЕ буквы для орфограммы 10
    """
    task10_orthograms = {10, 11, 28, 29, 6}
    
    if not any(ex.orthogram_id in task10_orthograms for ex in examples):
        if is_multi_line:
            return [ex.masked_word.strip() for ex in examples], {}, {}
        else:
            return ', '.join(ex.masked_word.strip() for ex in examples), {}, {}
    
    # ПРОСТОЙ подход: для орфограммы 10 - все 6 букв
    SUBGROUPS = [
        {'key': '10_all', 'letters': ['с', 'з', 'д', 'т', 'а', 'о'], 'orth_ids': [10]},
        {'key': '11', 'letters': ['з', 'с'], 'orth_ids': [11]},
        {'key': '28', 'letters': ['и', 'ы'], 'orth_ids': [28]},
        {'key': '29', 'letters': ['е', 'и'], 'orth_ids': [29]},
        {'key': '6', 'letters': ['ъ', 'ь', '/'], 'orth_ids': [6]},
    ]
    
    task10_letter_groups = {}
    task10_subgroup_letters = {g['key']: g['letters'] for g in SUBGROUPS}
    
    mask_index = 1
    formatted_items = []
    
    for ex in examples:
        masked = ex.masked_word.strip()
        
        if ex.orthogram_id in task10_orthograms:
            # Определяем ключ подгруппы
            subgroup_key = None
            for group in SUBGROUPS:
                if ex.orthogram_id in group['orth_ids']:
                    subgroup_key = group['key']
                    break
            
            # Создаём маску
            new_mask = f"10_{ex.orthogram_id}-{mask_index}"
            masked = re.sub(r'\*\d+(?:_\d+)?\*', f'*{new_mask}*', masked, count=1)
            
            if subgroup_key:
                task10_letter_groups[new_mask] = subgroup_key
            
            mask_index += 1
        
        formatted_items.append(masked)
    
    if is_multi_line:
        return formatted_items, task10_letter_groups, task10_subgroup_letters
    else:
        return ', '.join(formatted_items), task10_letter_groups, task10_subgroup_letters


# ============================================================================
# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ГЕНЕРАЦИИ ПРИМЕРОВ
# ============================================================================

def get_examples_with_subgroups(orthogram_ids, total_needed, grade_suffix=None):
    """
    Получает примеры с фильтрацией по подгруппам (как в диагностике) и по классу.
    """
    # Конфигурация подгрупп для задания 10
    SUBGROUPS = [
        {'key': 'sz', 'letters': ['з', 'с'], 'orth_ids': [10, 11]},
        {'key': 'ao', 'letters': ['а', 'о'], 'orth_ids': [10]},
        {'key': 'dt', 'letters': ['д', 'т'], 'orth_ids': [10]},
        {'key': 'ыи', 'letters': ['и', 'ы'], 'orth_ids': [28]},
        {'key': 'еи', 'letters': ['е', 'и'], 'orth_ids': [29]},
        {'key': 'ъь', 'letters': ['ъ', 'ь', '/'], 'orth_ids': [6]},
    ]
    
    all_examples = []
    taken_ids = set()  # отслеживаем взятые ID

    # === 1. ПОДГРУППЫ (10,11,28,29,6) ===
    for group in SUBGROUPS:
        for orth_id in group['orth_ids']:
            if orth_id not in orthogram_ids:
                continue
                
            qs = OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True
            )
            
            if grade_suffix:
                qs = qs.filter(grades__contains=str(grade_suffix))
            
            for ex in qs.order_by('?')[:50]:
                if ex.id in taken_ids:
                    continue
                    
                correct = extract_correct_letter(ex.text, ex.masked_word)
                if not correct:
                    continue
                    
                if orth_id == 6:
                    letter = '/' if correct == '' else correct
                else:
                    letter = correct.lower()
                
                if letter in group['letters']:
                    all_examples.append((ex, letter, orth_id))
                    taken_ids.add(ex.id)
    
    # === 2. ОРФОГРАММЫ НЕ ИЗ ПОДГРУПП (1, 2, 21, 22, 23, 24 и т.д.) ===
    orth_ids_regular = [
        oid for oid in orthogram_ids 
        if not any(oid in group['orth_ids'] for group in SUBGROUPS)
    ]
    
    if orth_ids_regular:
        qs = OrthogramExample.objects.filter(
            orthogram_id__in=orth_ids_regular,
            is_active=True
        ).exclude(id__in=taken_ids)
        
        if grade_suffix:
            qs = qs.filter(grades__contains=str(grade_suffix))
        
        for ex in qs.order_by('?')[:total_needed * 2]:
            if ex.id in taken_ids:
                continue
                
            # Для орфограмм Н/НН передаём orth_id для правильной экстракции
            letter = extract_correct_letter(ex.text, ex.masked_word, orth_id)
            
            # Добавляем логирование для орфограммы 38
            if ex.orthogram_id == 38:
                print(f"\n--- Обработка примера для орфограммы 38 ---")
                print(f"ex.id: {ex.id}")
                print(f"ex.text: '{ex.text}'")
                print(f"ex.masked_word: '{ex.masked_word}'")
                print(f"extracted letter: '{letter}'")
                
            if letter:
                all_examples.append((ex, letter.lower(), ex.orthogram_id))
                taken_ids.add(ex.id)

    # === ОРФОГРАММЫ 35 И 37 (Ё/О/Е) ===
    for orth_id in [35, 37]:
        if orth_id in orthogram_ids:
            qs = OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True
            )
            
            if grade_suffix:
                qs = qs.filter(grades__contains=str(grade_suffix))
            
            for ex in qs.order_by('?')[:total_needed]:
                correct = extract_correct_letter(ex.text, ex.masked_word)
                if correct:
                    all_examples.append((ex, correct.lower(), orth_id))
    
    # === 3. ДОБИРАЕМ ПРИ НЕОБХОДИМОСТИ ===
    if len(all_examples) < total_needed:
        remaining = total_needed - len(all_examples)
        
        extra = OrthogramExample.objects.filter(
            orthogram_id__in=orthogram_ids,
            is_active=True
        ).exclude(id__in=taken_ids)
        
        if grade_suffix:
            extra = extra.filter(grades__contains=str(grade_suffix))
        
        for ex in extra.order_by('?')[:remaining]:
            # Для орфограмм Н/НН передаём orth_id для правильной экстракции
            letter = extract_correct_letter(ex.text, ex.masked_word, orth_id)
            if letter:
                all_examples.append((ex, letter.lower(), ex.orthogram_id))
                taken_ids.add(ex.id)
    
    random.shuffle(all_examples)
    return all_examples



@login_required
def generate_exercise(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        data = json.loads(request.body)
        raw_ids = data.get('orthogram_ids', [])
        
        # === ИЗВЛЕЧЕНИЕ СУФФИКСА КЛАССА ===
        grade_suffix = None
        for raw_id in raw_ids:
            if isinstance(raw_id, str) and '_' in raw_id:
                parts = raw_id.split('_')
                if len(parts) > 1:
                    grade_suffix = parts[1]
                    break
        
        # === ПАРСИНГ ID ОРФОГРАММ ===
        orthogram_ids = []
        grade_filter = None

        for raw_id in raw_ids:
            raw_id_str = str(raw_id)
            
            # Обработка классовых фильтров (1_5, 2_7, 1_11 и т.д.)
            if raw_id_str.startswith(('1_', '2_')):
                try:
                    base_id, grade = raw_id_str.split('_')
                    orthogram_ids.append(int(base_id))
                    if grade_filter is None:
                        grade_filter = int(grade)
                except (ValueError, AttributeError):
                    continue
            else:
                # Обычные ID орфограмм
                try:
                    orthogram_ids.append(int(raw_id_str))
                except (ValueError, TypeError):
                    continue

        # Удаляем дубликаты
        orthogram_ids = list(set(orthogram_ids))

        # Удаляем дубликаты, СОХРАНЯЯ ПОРЯДОК
        orthogram_ids = list(dict.fromkeys(orthogram_ids))

        if not orthogram_ids:
            return JsonResponse({'error': 'Некорректные ID орфограмм'}, status=400)
        
        # === Определяем количество ===
        TASK_13_ORTHOGRAMS = {21, 32, 36, 46, 54, 56, 57, 58, 581, 582}
        is_task_13 = set(orthogram_ids) <= TASK_13_ORTHOGRAMS
        is_task_14 = orthogram_ids == [1400]
        total_needed = 5 if (is_task_13 or is_task_14) else 16
        
        # === Получаем примеры С ФИЛЬТРАЦИЕЙ ПО КЛАССУ ===
        examples_with_data = get_examples_with_subgroups(
            orthogram_ids, 
            total_needed * 2,  # Берем с запасом
            grade_suffix=grade_suffix or grade_filter
        )

        if not examples_with_data:
            return JsonResponse({'error': 'Нет доступных слов'}, status=404)
        
        # === СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ ОРФОГРАММ 21, 32, 36 (НЕ с разными частями речи) ===
        # Орфограммы, где нужно контролировать соотношение слитных/раздельных примеров
        CONTROLLED_ORTHOGRAMS = {21, 32, 36}

        if len(orthogram_ids) == 1 and orthogram_ids[0] in CONTROLLED_ORTHOGRAMS:
            orth_id = orthogram_ids[0]
            total_needed = 5
            
            # Случайно выбираем соотношение: 2/3 или 3/2
            if random.choice([True, False]):
                # Вариант А: 2 слитных, 3 раздельных
                combined_count = 2
                separate_count = 3
            else:
                # Вариант Б: 3 слитных, 2 раздельных
                combined_count = 3
                separate_count = 2
            
            logger.info(f"Орфограмма {orth_id}: генерируем {combined_count} слитных, {separate_count} раздельных")
            
            # Получаем примеры со слитным написанием
            combined_examples = list(OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True,
                explanation__icontains='/'
            ).order_by('?')[:10])
            
            # Получаем примеры с раздельным написанием
            separate_examples = list(OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True,
                explanation__icontains='|'
            ).order_by('?')[:10])
            
            # Проверяем, хватает ли примеров
            if len(combined_examples) < combined_count or len(separate_examples) < separate_count:
                logger.warning(f"Недостаточно примеров для орфограммы {orth_id} с контролируемым соотношением")
                # Если не хватает, используем обычную логику
                examples_with_data = get_examples_with_subgroups(
                    orthogram_ids, total_needed * 2,
                    grade_suffix=grade_suffix or grade_filter
                )
            else:
                # Выбираем нужное количество примеров
                selected_combined = random.sample(combined_examples, combined_count)
                selected_separate = random.sample(separate_examples, separate_count)
                
                # Объединяем и перемешиваем
                all_examples = selected_separate + selected_combined
                random.shuffle(all_examples)
                
                # Формируем результат
                examples_with_data = []
                used_ids = set()
                
                for ex in all_examples:
                    if ex.id in used_ids:
                        continue
                    letter = extract_correct_letter(ex.text, ex.masked_word, orth_id)
                    if letter:
                        examples_with_data.append((ex, letter, orth_id))
                        used_ids.add(ex.id)
                
                # Если не хватило, добираем
                if len(examples_with_data) < total_needed:
                    remaining = total_needed - len(examples_with_data)
                    extra = OrthogramExample.objects.filter(
                        orthogram_id=orth_id,
                        is_active=True
                    ).exclude(id__in=used_ids).order_by('?')[:remaining]
                    
                    for ex in extra:
                        letter = extract_correct_letter(ex.text, ex.masked_word, orth_id)
                        if letter:
                            examples_with_data.append((ex, letter, orth_id))
        else:
            # Обычная логика для всех остальных орфограмм
            examples_with_data = get_examples_with_subgroups(
                orthogram_ids, total_needed * 2,
                grade_suffix=grade_suffix or grade_filter
            )

        # Обрезаем до нужного количества
        examples_with_data = examples_with_data[:total_needed]

        # Разделяем данные
        examples = [item[0] for item in examples_with_data]
        letters = [item[1] for item in examples_with_data]
        
        # === УМНЫЙ ЗАГОЛОВОК ДЛЯ ЕГЭ ===
        exercise_title = f"Орфограмма № {orthogram_ids[0]}"  # fallback

        # Задание 10: Корни
        if set(orthogram_ids) == {1, 2, 12, 13, 14, 15, 24, 26, 27, 271}:
            exercise_title = "Задание № 10. Корни"

        # Задание 11: Приставки
        elif set(orthogram_ids) == {10, 11, 28, 29, 6}:
            exercise_title = "Задание № 11. Приставки."

        # Задание 12: Суффиксы
        elif set(orthogram_ids) == {31, 33, 34, 35, 37, 39, 48, 481, 482, 483, 484, 60, 61, 610, 485}:
            exercise_title = "Задание № 12. Суффиксы."

        # Задание 13: Спряжения. Причастия
        elif set(orthogram_ids) == {25, 49, 50, 51, 511, 512, 513}:
            exercise_title = "Задание № 13. Спряжения. Причастия"

        # Задание 14: Слитно - раздельно
        elif set(orthogram_ids) == {21, 32, 36, 46, 54, 56, 57, 58, 581, 582}:
            exercise_title = "Задание № 14. Слитно - раздельно"

        # Задание 15: Слитно - раздельно - дефис
        elif orthogram_ids == [1400]:
            exercise_title = "Задание № 15. Слитно - раздельно - дефис"
            
        # Для одной орфограммы
        else:
            exercise_title = f"Орфограмма № {orthogram_ids[0]}"
        
        # === Конфигурация для задания 10 ===
        SUBGROUPS_CONFIG = [
            {'key': 'sz', 'letters': ['с', 'з'], 'orth_ids': [10, 11]},
            {'key': 'ao', 'letters': ['а', 'о'], 'orth_ids': [10]},
            {'key': 'dt', 'letters': ['д', 'т'], 'orth_ids': [10]},
            {'key': 'ыи', 'letters': ['и', 'ы'], 'orth_ids': [28]},
            {'key': 'еи', 'letters': ['е', 'и'], 'orth_ids': [29]},
            {'key': 'ъь', 'letters': ['ъ', 'ь', '/'], 'orth_ids': [6]},
        ]
        
        task10_subgroup_letters = {g['key']: g['letters'] for g in SUBGROUPS_CONFIG}
        task10_letter_groups = {}
        
        # === Форматируем маски ===
        mask_index = 1
        formatted_items = []
        filtered_examples = []
        filtered_letters = []

        # ← ОПРЕДЕЛЯЕМ is_ege ОДИН РАЗ
        is_ege = (grade_suffix in ['10', '11']) or (grade_filter in [10, 11])

        for ex, correct_letter, orth_id in examples_with_data:
            masked = ex.masked_word.strip()
            
            # === ВАЛИДАЦИЯ ===
            if '*' not in masked:
                continue
            
            if not correct_letter:
                continue
            
            # === ОПРЕДЕЛЯЕМ ПОДГРУППУ ===
            subgroup_key = None
            for group in SUBGROUPS_CONFIG:
                if orth_id in group['orth_ids'] and correct_letter in group['letters']:
                    subgroup_key = group['key']
                    break
            
            # === ФОРМИРУЕМ МАСКУ ===
            if orth_id in {10, 11, 28, 29, 6}:
                # ВСЕГДА используем формат 10_ORTHID-INDEX
                new_mask = f"10_{orth_id}-{mask_index}"
                masked = re.sub(r'\*\d+(?:_\d+)?\*', f'*{new_mask}*', masked, count=1)
                if subgroup_key:
                    task10_letter_groups[new_mask] = subgroup_key
                mask_index += 1
            else:
                # Обычная маска: *ID*
                masked = re.sub(r'\*[^*]+\*', f'*{orth_id}*', masked)
            
            # ← СОХРАНЯЕМ ТОЛЬКО ВАЛИДНЫЕ СЛОВА
            formatted_items.append(masked)
            filtered_examples.append(ex)
            filtered_letters.append(correct_letter)

        # ← КРИТИЧЕСКИ ВАЖНО: обрезаем ДО нужного количества ПОСЛЕ фильтрации!
        if len(formatted_items) > total_needed:
            formatted_items = formatted_items[:total_needed]
            filtered_examples = filtered_examples[:total_needed]
            filtered_letters = filtered_letters[:total_needed]

        # Заменяем оригинальные списки
        examples = filtered_examples
        letters = filtered_letters

        if not formatted_items:
            return JsonResponse({'error': 'Нет качественных примеров'}, status=404)

        logger.info(f"✅ После валидации: {len(formatted_items)} слов из {total_needed}")
        
        # === Форматируем вывод ===
        is_ne_split_lines = is_task_13 or is_task_14
        if is_ne_split_lines:
            words_lines = formatted_items
            words_text = None
        else:
            words_text = ', '.join(formatted_items)
            words_lines = None
        
        # Сохраняем в сессию
        request.session['current_exercise'] = {
            'exercise_id': f'dynamic_{",".join(map(str, orthogram_ids))}',
            'example_ids': [ex.id for ex in examples],
            'correct_letters': letters,
            'orthogram_ids': orthogram_ids,
        }
        
        # Рендерим шаблон
        html = render_to_string('exercise_snippet.html', {
            'words_text': words_text,
            'words_lines': words_lines,
            'is_orth21_lines': is_ne_split_lines,
            'exercise_id': request.session['current_exercise']['exercise_id'],
            'exercise_title': exercise_title,
            'show_next_button': True,
            'orthogram_ids': orthogram_ids,
            'task10_letter_groups': json.dumps(task10_letter_groups),
            'task10_subgroup_letters': json.dumps(task10_subgroup_letters),
        })
        
        return JsonResponse({
            'html': html,
            'task10_letter_groups': task10_letter_groups,
            'task10_subgroup_letters': task10_subgroup_letters,
        })
        
    except Exception as e:
        logger.error(f"Ошибка в generate_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# === Генерация упражнений ОРФОГРАММ много масок ===
@login_required
def generate_exercise_multi(request):
    """
    Генерирует упражнение с несколькими масками (Задания 14 и 15).
    Для задания 14 выдаётся 5 примеров-предложений.
    Для задания 15 выдаётся 1 пример-предложение.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    try:
        data = json.loads(request.body)
        orthogram_ids = data.get('orthogram_ids', [])
        
        # КОНВЕРТИРУЕМ СТРОКИ В ЧИСЛА для сравнения
        orthogram_ids_int = []
        for orth_id in orthogram_ids:
            try:
                orthogram_ids_int.append(int(orth_id))
            except (ValueError, TypeError):
                continue
        
        # Поддерживаем и 1400 и 1500 (теперь как числа)
        if orthogram_ids_int not in [[1400], [1500]]:
            return JsonResponse({'error': 'Поддерживаются только орфограммы 1400 и 1500'}, status=400)
        
        orthogram_id = orthogram_ids_int[0]
        
        # Определяем количество примеров по типу задания
        if orthogram_id == 1400:
            # Задание 14 - 5 примеров-предложений
            total_needed = 5
        else:  # orthogram_id == 1500
            # Задание 15 - 1 пример-предложение
            total_needed = 1
        
        # Берем нужное количество примеров
        examples = OrthogramExample.objects.filter(
            orthogram_id=orthogram_id,
            is_active=True
        ).order_by('?')[:total_needed * 3]  # Берем с запасом
        
        correct_letters = []
        valid_examples = []
        
        # === ИЗВЛЕЧЕНИЕ ПРАВИЛЬНЫХ ОТВЕТОВ ===
        for ex in examples:
            explanation_text = (ex.explanation or '').strip()
            
            if orthogram_id == 1400:
                # ЗАДАНИЕ 14: слитное/раздельное/дефисное написание
                parts = []
                if explanation_text:
                    # Очищаем explanation: убираем пробелы и переносы
                    clean_text = explanation_text.replace(' ', '').replace('\n', '').replace('\r', '')
                    # Парсим символы
                    for char in clean_text.split(','):
                        if char and char in ['|', '/', '-']:
                            parts.append(char)
                
                if not parts:
                    # Fallback: извлекаем из text
                    parts = extract_from_text_and_masks(ex.text, ex.masked_word, orthogram_id)
                
                if parts:
                    # Проверяем, что количество частей совпадает с количеством масок
                    mask_count = ex.masked_word.count(f'*{orthogram_id}*')
                    if len(parts) >= mask_count and mask_count > 0:
                        correct_letters.append(parts[:mask_count])
                        valid_examples.append(ex)
            
            else:  # orthogram_id == 1500
                # ЗАДАНИЕ 15: Н/НН в суффиксах
                parts = []
                if explanation_text:
                    clean_text = explanation_text.replace(' ', '').replace('\n', '').replace('\r', '')
                    for part in clean_text.split(','):
                        if part in ['н', 'нн']:
                            parts.append(part)
                
                if not parts and ex.correct_letters:
                    clean_cl = ex.correct_letters.replace(' ', '').replace('\n', '').replace('\r', '')
                    for part in clean_cl.split(','):
                        if part in ['н', 'нн']:
                            parts.append(part)
                
                if parts:
                    mask_count = ex.masked_word.count(f'*{orthogram_id}*')
                    if len(parts) >= mask_count and mask_count > 0:
                        correct_letters.append(parts[:mask_count])
                        valid_examples.append(ex)
        
        # Если после валидации примеров меньше, чем нужно, используем что есть
        if not valid_examples:
            return JsonResponse({'error': 'Нет корректных примеров'}, status=400)
        
        # Обрезаем до нужного количества
        valid_examples = valid_examples[:total_needed]
        correct_letters = correct_letters[:total_needed]
        
        exercise_id = f'multi_{orthogram_id}'
        title = 'Задание 14' if orthogram_id == 1400 else 'Задание 15'
        
        request.session['current_exercise'] = {
            'exercise_id': exercise_id,
            'example_ids': [ex.id for ex in valid_examples],
            'correct_letters': correct_letters,
            'orthogram_ids': [orthogram_id],
        }
        
        # === ПОДГОТОВКА ДАННЫХ ДЛЯ ШАБЛОНА ===
        words_lines = []
        mask_counter = 1
        
        # === ГРУППЫ БУКВ ДЛЯ ВЫПАДАЮЩИХ СПИСКОВ ===
        if orthogram_id == 1400:
            task14_letter_groups = {}
            task14_subgroup_letters = {'preposition': ['|', '/', '-']}
            task15_letter_groups = {}
            task15_subgroup_letters = {}
        else:  # orthogram_id == 1500
            task14_letter_groups = {}
            task14_subgroup_letters = {}
            task15_letter_groups = {}
            task15_subgroup_letters = {'nn': ['н', 'нн']}
        
        for ex in valid_examples:
            masked_word = ex.masked_word
            
            # Заменяем маски *1400* на *14-1*, *14-2* и т.д.
            # ИЛИ маски *1500* на *15-1*, *15-2* и т.д.
            prefix = '14-' if orthogram_id == 1400 else '15-'
            
            while f'*{orthogram_id}*' in masked_word:
                mask_id = f"{prefix}{mask_counter}"
                masked_word = masked_word.replace(f'*{orthogram_id}*', f'*{mask_id}*', 1)
                
                # === ЗАПОЛНЯЕМ ГРУППЫ БУКВ ===
                if orthogram_id == 1400:
                    task14_letter_groups[mask_id] = 'preposition'
                else:  # orthogram_id == 1500
                    task15_letter_groups[mask_id] = 'nn'
                
                mask_counter += 1
            
            words_lines.append(masked_word)
        
        # === РЕНДЕРИНГ ШАБЛОНА ===
        html = render_to_string('exercise_snippet.html', {
            'words_lines': words_lines,
            'words_text': None,
            'is_orth21_lines': True,
            'exercise_id': exercise_id,
            'exercise_title': title,
            'show_next_button': False,
            # === ПЕРЕДАЁМ ДАННЫЕ О ПОДГРУППАХ ===
            'task14_letter_groups': json.dumps(task14_letter_groups) if task14_letter_groups else '{}',
            'task14_subgroup_letters': json.dumps(task14_subgroup_letters) if task14_subgroup_letters else '{}',
            'task15_letter_groups': json.dumps(task15_letter_groups) if task15_letter_groups else '{}',
            'task15_subgroup_letters': json.dumps(task15_subgroup_letters) if task15_subgroup_letters else '{}',
        })
        
        return JsonResponse({
            'html': html,
            'task14_letter_groups': task14_letter_groups,
            'task14_subgroup_letters': task14_subgroup_letters,
            'task15_letter_groups': task15_letter_groups,
            'task15_subgroup_letters': task15_subgroup_letters,
        })
        
    except Exception as e:
        logger.error(f"Ошибка в generate_exercise_multi: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка сервера'}, status=500)




def extract_from_text_and_masks(text, masked_word, orthogram_id):
    """
    Извлекает правильные символы из text по позициям масок.
    Для орфограммы 1400 нормализует обратный слэш в вертикальную черту.
    """
    parts = []
    masked = masked_word
    
    while f'*{orthogram_id}*' in masked:
        mask_start = masked.find('*')
        if mask_start == -1:
            break
            
        if mask_start >= len(text):
            break
            
        char = text[mask_start]
        
        # Нормализация для орфограммы 1400
        if orthogram_id == 1400 and char == '\\':
            char = '|'  # Заменяем обратный слеш на вертикальную черту
        
        parts.append(char)
        
        # Заменяем маску для продолжения поиска
        masked = masked.replace(f'*{orthogram_id}*', 'X', 1)
    
    return parts


# === Генерация упражнений ПУНКТОГРАММ (задания 16–21) ===
@login_required
def generate_punktum_exercise(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        orthogram_ids = data.get('orthogram_ids', [])

        # Всегда сбрасываем сессию для новых упражнений
        if 'current_exercise' in request.session:
            del request.session['current_exercise']

        # Поддерживаемые пунктограммы
        PUNKTUM_TASKS = {
            '1600', '1700', '1800', '1900', '2000', '2100', '2101', '2102'
        }
        if not set(orthogram_ids).issubset(PUNKTUM_TASKS):
            return JsonResponse({'error': 'Поддерживаются только задания 16–21'}, status=400)

        punktum_id = orthogram_ids[0]

        # Статические значения для совместимости с фронтендом
        if punktum_id == '2100':
            allowed_letters = ['5', '8', '8.1', '9.2', '10', '13', '16', '18']
        elif punktum_id == '2101':
            allowed_letters = ['5', '9.1', '19']
        elif punktum_id == '2102':
            allowed_letters = ['2', '4.1', '4.2', '4.3', '5', '6', '7', '11', '12', '13', '14', '15', '16', '17']
        else:
            # Для 16-20 получаем из БД
            try:
                punktum = Punktum.objects.get(id=punktum_id)
                allowed_letters = [letter.strip() for letter in punktum.letters.split(',') if letter.strip()]
            except Punktum.DoesNotExist:
                return JsonResponse({'error': f'Пунктограмма {punktum_id} не найдена'}, status=404)

        # Ищем активные примеры
        examples = PunktumExample.objects.filter(
            punktum__id=punktum_id,
            is_active=True
        ).order_by('?')[:10]

        if not examples:
            return JsonResponse({'error': f'Нет примеров для пунктограммы {punktum_id}'}, status=404)

        correct_letters = []
        valid_examples = []
        mask_pattern = f"*{punktum_id}*"
        
        for ex in examples:
            explanation_text = (ex.explanation or '').strip()
            if not explanation_text:
                continue

            parts = [p.strip() for p in explanation_text.split(',') if p.strip()]
            mask_count = ex.masked_word.count(mask_pattern)
            
            # Пропускаем примеры без масок
            if mask_count == 0:
                continue
                
            # Проверяем соответствие количества масок и частей
            if mask_count != len(parts):
                continue
                
            # Проверяем допустимость частей
            if not all(part in allowed_letters for part in parts):
                continue
                
            # Все проверки пройдены
            correct_letters.extend(parts)
            valid_examples.append(ex)
            
            # Останавливаемся на 5 примерах
            if len(valid_examples) >= 5:
                break

        if not valid_examples:
            return JsonResponse({'error': 'Нет корректных примеров'}, status=400)

        # Формирование инструкции для заданий 21
        instruction = ""
        if punktum_id == '2100':
            instruction = "На месте смайликов ТИРЕ. Выберите подходящий номер пунктограммы"
        elif punktum_id == '2101':
            instruction = "На месте смайликов ДВОЕТОЧИЕ. Выберите подходящий номер пунктограммы"
        elif punktum_id == '2102':
            instruction = "На месте смайликов ЗАПЯТЫЕ. Выберите подходящий номер пунктограммы"

        # Сохраняем в сессию
        request.session['current_exercise'] = {
            'exercise_id': f'punktum_{punktum_id}',
            'example_ids': [ex.id for ex in valid_examples],
            'correct_letters': correct_letters,
            'orthogram_ids': [punktum_id],
        }

        # Подготовка данных для шаблона
        words_lines = [ex.masked_word.strip() for ex in valid_examples]
        task_num = punktum_id[:2]

        html = render_to_string('exercise_snippet.html', {
            'words_lines': words_lines,
            'words_text': None,
            'is_orth21_lines': True,
            'exercise_id': request.session['current_exercise']['exercise_id'],
            'exercise_title': f'Задание № {task_num}',
            'exercise_instruction': instruction,
            'show_next_button': False,
        })

        return JsonResponse({'html': html})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат JSON'}, status=400)
    except Exception as e:
        logger.error(f"Ошибка в generate_punktum_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка генерации упражнения'}, status=500)


# === Генерация упражнений на МНОЖЕСТВО ПУНКТОГРАММ (задания 16–21) ===
@login_required
def generate_punktum_exercise_multi(request):
    """
    Генерирует упражнение для заданий 16–21 ЕГЭ.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    try:
        data = json.loads(request.body)
        orthogram_ids = data.get('orthogram_ids', [])
        
        if not isinstance(orthogram_ids, list) or not orthogram_ids:
            return JsonResponse({'error': 'Неверный формат orthogram_ids'}, status=400)
        
        punktum_id = str(orthogram_ids[0])
        SUPPORTED = {'1600', '1700', '1800', '1900', '2000', '2100', '2101', '2102'}
        
        if punktum_id not in SUPPORTED:
            return JsonResponse({'error': 'Поддерживаются только задания 16–21'}, status=400)
        
        # Определяем количество требуемых примеров
        total_needed = 5 if punktum_id == '1600' else 1
        
        # Получаем активные примеры
        examples = PunktumExample.objects.filter(
            punktum__id=punktum_id,
            is_active=True
        ).order_by('?')[:total_needed * 3]
        
        valid_examples = []
        correct_letters = []
        
        for ex in examples:
            explanation_text = (ex.explanation or '').strip()
            if not explanation_text:
                continue
            
            parts = [p.strip() for p in explanation_text.split(',') if p.strip()]
            
            # Для задания 21 используем формат 21-XXXX
            if punktum_id.startswith('21'):
                mask_pattern = f"*{punktum_id}*"
                if mask_pattern not in ex.masked_word:
                    continue
            else:
                mask_pattern = f"*{punktum_id}*"
                if mask_pattern not in ex.masked_word:
                    continue
            
            mask_count = ex.masked_word.count(mask_pattern)
            if mask_count != len(parts) or mask_count == 0:
                continue
            
            valid_examples.append(ex)
            correct_letters.extend(parts)
            
            if len(valid_examples) >= total_needed:
                break
        
        if not valid_examples:
            return JsonResponse({'error': f'Нет корректных примеров для пунктограммы {punktum_id}'}, status=400)
        
        # Инструкция и картинка для задания 21
        instruction = ""
        image_name = None
        task21_subgroup_letters = None
        
        if punktum_id == '1600':
            image_name = 'images/punktum_task_16.webp'
        elif punktum_id == '1700':
            image_name = 'images/punktum_task_17.webp'
        elif punktum_id == '1800':
            image_name = 'images/punktum_task_18.webp'
        elif punktum_id == '1900':
            image_name = 'images/punktum_task_19.webp'
        elif punktum_id == '2000':
            image_name = 'images/punktum_task_20.webp'
        elif punktum_id == '2100':
            instruction = "На месте смайликов ТИРЕ. Выберите подходящий номер пунктограммы"
            image_name = 'images/punktum_task_21_0.webp'
            task21_subgroup_letters = {'punktum_21': ['5', '8', '8.1', '9.2', '10', '13', '16', '18']}
        elif punktum_id == '2101':
            instruction = "На месте смайликов ДВОЕТОЧИЕ. Выберите подходящий номер пунктограммы"
            image_name = 'images/punktum_task_21_1.webp'
            task21_subgroup_letters = {'punktum_21': ['5', '9.1', '19']}
        elif punktum_id == '2102':
            instruction = "На месте смайликов ЗАПЯТЫЕ. Выберите подходящий номер пунктограммы"
            image_name = 'images/punktum_task_21_2.webp'
            task21_subgroup_letters = {'punktum_21': ['2', '4.0', '4.1', '4.2', '5', '6', '7', '11', '12', '13', '14', '15', '16', '17']}
        
        # Сохраняем в сессию
        request.session['current_exercise'] = {
            'exercise_id': f'punktum_multi_{punktum_id}',
            'example_ids': [ex.id for ex in valid_examples],
            'correct_letters': correct_letters,
            'orthogram_ids': [punktum_id],
        }
        
        # === ФОРМИРОВАНИЕ WORDS_LINES С ИНДЕКСАМИ ===
        words_lines = []
        mask_counter = 1
        task_num = punktum_id[:2]  # '1600' -> '16'
        
        # === ГРУППЫ БУКВ ДЛЯ ПУНКТОГРАММ 16-20 ===
        letter_groups = {}
        subgroup_letters = {f'punktum_{task_num}': ['!', '?']}
        
        for ex in valid_examples:
            masked = ex.masked_word.strip()
            
            # Заменяем маски *1600* на *16-1*, *16-2* и т.д.
            while f"*{punktum_id}*" in masked:
                mask_id = f"{task_num}-{mask_counter}"
                masked = masked.replace(f"*{punktum_id}*", f"*{mask_id}*", 1)
                letter_groups[mask_id] = f'punktum_{task_num}'
                mask_counter += 1
            
            words_lines.append(masked)
        
        # === STRUCTURED_EXAMPLES ДЛЯ ЗАДАНИЯ 18 (С АБЗАЦАМИ) ===
        structured_examples = [
            [p.strip() for p in ex.masked_word.split('\n') if p.strip()]
            for ex in valid_examples
        ]
        
        is_punktum_with_paragraphs = (punktum_id == '1800')
        
        # === РЕНДЕРИНГ ШАБЛОНА ===
        html = render_to_string('exercise_snippet.html', {
            'structured_examples': structured_examples,
            'words_lines': words_lines,
            'is_punktum_exercise': True,
            'punktogram_id': punktum_id,
            'exercise_id': f'punktum_multi_{punktum_id}',
            'exercise_instruction': instruction,
            'show_next_button': False,
            'is_punktum_with_paragraphs': is_punktum_with_paragraphs,
            'image_name': image_name,
            'task21_subgroup_letters': json.dumps(task21_subgroup_letters) if task21_subgroup_letters else None,
            # === ПЕРЕДАЁМ LETTER_GROUPS ДЛЯ 16-20 ===
            f'task{task_num}_letter_groups': json.dumps(letter_groups) if letter_groups else '{}',
            f'task{task_num}_subgroup_letters': json.dumps(subgroup_letters) if subgroup_letters else '{}',
        })
        
        return JsonResponse({
            'html': html,
            f'task{task_num}_letter_groups': letter_groups,
            f'task{task_num}_subgroup_letters': subgroup_letters,
            'task21_subgroup_letters': task21_subgroup_letters if punktum_id.startswith('21') else None,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный JSON'}, status=400)
    except Exception as e:
        logger.error(f"Ошибка в generate_punktum_exercise_multi: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка сервера'}, status=500)

# ========================================================

@login_required
def generate_alphabetical_exercise(request):
    """Алфавитная навигация ФИПИ для ЕГЭ (только 10-11 классы)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        data = json.loads(request.body)
        orthogram_id = data.get('orthogram_id')
        range_code = data.get('range')

        if not orthogram_id or not range_code:
            return JsonResponse({'error': 'Отсутствуют обязательные параметры'}, status=400)

        config = {
            '1': {
                'ranges': {'A-O': ('А', 'О'), 'P-S': ('П', 'С'), 'T-YA': ('Т', 'Я')},
                'title_prefix': 'Безударные гласные, ПРОВЕРЯЕМЫЕ ударением'
            },
            '2': {
                'ranges': {'A-D': ('А', 'Д'), 'E-K': ('Е', 'К'), 'L-R': ('Л', 'Р'), 'S-YA': ('С', 'Я')},
                'title_prefix': 'Безударные гласные, НЕПРОВЕРЯЕМЫЕ ударением'
            }
        }

        if orthogram_id not in config or range_code not in config[orthogram_id]['ranges']:
            return JsonResponse({'error': 'Неподдерживаемая орфограмма или диапазон'}, status=400)

        orthogram_id_int = int(orthogram_id)
        start_letter, end_letter = config[orthogram_id]['ranges'][range_code]
        
        logger.info(f"Алфавитное задание: орфограмма {orthogram_id}, диапазон {range_code} ({start_letter}-{end_letter})")

        # === ШАГ 1: Берем ВСЕ активные примеры для этой орфограммы (ТОЛЬКО 10-11 классы) ===
        from django.db.models import Q
        
        all_examples = OrthogramExample.objects.filter(
            Q(orthogram_id=orthogram_id_int) &
            Q(is_active=True) &
            (Q(grades__contains='10') | Q(grades__contains='11'))
        ).distinct()
        
        logger.info(f"Найдено примеров в базе: {all_examples.count()}")
        
        # === ШАГ 2: Функция проверки первой буквы ===
        def check_first_letter(word, start, end):
            word_upper = word.upper()
            for char in word_upper:
                if ('А' <= char <= 'Я') or char == 'Ё':
                    if char == 'Ё':
                        char = 'Е'
                    return start <= char <= end
            return False
        
        # === ШАГ 3: СТРОГАЯ ВАЛИДАЦИЯ И ФИЛЬТРАЦИЯ ===
        filtered_examples = []
        seen_words = set()  # для отслеживания дубликатов
        
        for ex in all_examples:
            # 1. Проверка первой буквы
            if not check_first_letter(ex.masked_word, start_letter, end_letter):
                continue
            
            # 2. Извлекаем правильную букву
            letter = extract_correct_letter(ex.text, ex.masked_word)
            if not letter:
                continue
            
            # 3. СТРОГАЯ ВАЛИДАЦИЯ masked_word:
            masked = ex.masked_word.strip()
            
            # === КРИТИЧЕСКАЯ ВАЛИДАЦИЯ ===
            # Проверяем, что в слове ровно ДВА символа *
            if masked.count('*') != 2:
                continue
            
            # Проверяем формат: должно быть *цифра*
            if not re.match(r'^[^*]*\*\d+\*[^*]*$', masked):
                continue
            
            # Проверяем, что нет двойных пробелов
            if '  ' in masked:
                continue
            
            # Проверяем, что нет смайликов в исходных данных
            if '😊' in masked:
                continue
            
            # Минимальная длина слова
            if len(masked) < 3:
                continue
            
            # Проверяем дубликаты
            word_key = masked.lower().replace('*', '')
            if word_key in seen_words:
                continue
            seen_words.add(word_key)
            
            # 4. ЗАМЕНА МАСКИ (ТОЛЬКО ОДИН РАЗ!)
            masked = re.sub(r'\*\d+\*', f'*{orthogram_id_int}*', masked, count=1)
            
            filtered_examples.append((ex, letter.lower(), masked))
        
        logger.info(f"Отфильтровано по алфавиту и валидации: {len(filtered_examples)} примеров")
        
        if not filtered_examples:
            return JsonResponse({'error': f'Нет качественных слов в диапазоне {start_letter}-{end_letter} для 10-11 классов'}, status=404)
        
        # === ШАГ 4: Формируем слова ===
        words = [item[2] for item in filtered_examples]  # masked words
        correct_letters = [item[1] for item in filtered_examples]
        
        # === ШАГ 5: Формируем текст и сессию ===
        words_text = ', '.join(words)
        
        request.session['current_exercise'] = {
            'exercise_id': f'alphabetical_{orthogram_id}_{range_code}',
            'correct_words': words,
            'correct_letters': correct_letters,
            'orthogram_id': orthogram_id,
            'range_code': range_code,
        }

        # === ШАГ 6: Название упражнения ===
        prefix = config[orthogram_id]['title_prefix']
        range_labels = {
            'A-O': 'А-О', 'P-S': 'П-С', 'T-YA': 'Т-Я',
            'A-D': 'А-Д', 'E-K': 'Е-К', 'L-R': 'Л-Р', 'S-YA': 'С-Я'
        }
        range_label = range_labels.get(range_code, range_code)
        exercise_title = f"{prefix} ({range_label})"

        # === ШАГ 7: Рендерим HTML ===
        html = render_to_string('exercise_snippet.html', {
            'words_text': words_text,
            'exercise_id': request.session['current_exercise']['exercise_id'],
            'exercise_title': exercise_title,
            'show_next_button': False,
        })
        
        return JsonResponse({
            'html': html,
            'word_count': len(words),
            'orthogram_id': orthogram_id,
            'range_code': range_code,
            'report': _task9_report(request.user, orthogram_id, range_code),
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)
    except Exception as e:
        logger.error(f"Ошибка в generate_alphabetical_exercise: {e}", exc_info=True)
        return JsonResponse({'error': f'Внутренняя ошибка: {str(e)}'}, status=500)


@login_required
def generate_task9_exercise(request):
    """Задание 9 ЕГЭ: 16 слов, орфограммы 1,2 (11 класс) + 12-15,24,26,27,271"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        # Конфигурация
        ORTH_CLASS_FILTERED = [1, 2]      # только 11 класс
        ORTH_REGULAR = [12, 13, 14, 15, 24, 26, 27, 271]  # любые классы
        ALL_ORTH_IDS = ORTH_CLASS_FILTERED + ORTH_REGULAR
        TOTAL_NEEDED = 16
        WORDS_PER_ORTH = 2  # по 2 слова из каждой орфограммы
        
        examples_data = []
        
        # 1. Орфограммы 1 и 2 (только 11 класс)
        for orth_id in ORTH_CLASS_FILTERED:
            qs = OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True,
                grades__contains='11'
            ).order_by('?')[:WORDS_PER_ORTH]
            
            for ex in qs:
                letter = extract_correct_letter(ex.text, ex.masked_word)
                if letter:
                    examples_data.append((ex, letter.lower(), orth_id))
        
        # 2. Остальные орфограммы (любые классы)
        for orth_id in ORTH_REGULAR:
            if len(examples_data) >= TOTAL_NEEDED:
                break
                
            qs = OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True
            ).order_by('?')[:WORDS_PER_ORTH]
            
            for ex in qs:
                if len(examples_data) >= TOTAL_NEEDED:
                    break
                letter = extract_correct_letter(ex.text, ex.masked_word)
                if letter:
                    examples_data.append((ex, letter.lower(), orth_id))
        
        # 3. Добираем при необходимости (из всех орфограмм)
        if len(examples_data) < TOTAL_NEEDED:
            taken_ids = [ex.id for ex, _, _ in examples_data]
            remaining = TOTAL_NEEDED - len(examples_data)
            
            extra = OrthogramExample.objects.filter(
                orthogram_id__in=ALL_ORTH_IDS,
                is_active=True
            ).exclude(id__in=taken_ids).order_by('?')[:remaining]
            
            for ex in extra:
                letter = extract_correct_letter(ex.text, ex.masked_word)
                if letter:
                    examples_data.append((ex, letter.lower(), ex.orthogram_id))
        
        if not examples_data:
            return JsonResponse({'error': 'Нет примеров для задания 9'}, status=404)
        
        # 4. Перемешиваем, обрезаем и валидируем
        random.shuffle(examples_data)
        examples_data = examples_data[:TOTAL_NEEDED]

        formatted_items = []
        correct_letters = []
        example_ids = []

        for ex, letter, orth_id in examples_data:
            # Нормализуем маску
            masked = re.sub(r'\*[^*]+\*', f'*{orth_id}*', ex.masked_word.strip())
            
            # === ВАЛИДАЦИЯ ДО ДОБАВЛЕНИЯ ===
            if '*' not in masked:
                continue
            if '  ' in masked or masked.startswith(',') or masked.endswith(','):
                continue
            if len(masked) < 2:
                continue
            if masked in formatted_items:
                continue
            
            # === ТОЛЬКО ТЕПЕРЬ ДОБАВЛЯЕМ ===
            formatted_items.append(masked)
            correct_letters.append(letter)
            example_ids.append(ex.id)
        
        # Если после валидации осталось меньше слов - добираем
        if len(formatted_items) < TOTAL_NEEDED:
            logger.warning(f"⚠️ Задание 9: после валидации осталось {len(formatted_items)} слов")
            # Здесь можно рекурсивно вызвать или просто вернуть что есть
            # Пока возвращаем как есть
        
        # 5. Сессия
        request.session['current_exercise'] = {
            'exercise_id': 'task9_ege',
            'example_ids': example_ids[:len(formatted_items)],
            'correct_letters': correct_letters,
            'orthogram_ids': ALL_ORTH_IDS,
        }
        
        # 6. Рендерим
        html = render_to_string('exercise_snippet.html', {
            'words_text': ', '.join(formatted_items),
            'exercise_id': 'task9_ege',
            'exercise_title': 'Задание № 10. Корни',
            'show_next_button': False,
        })
        
        return JsonResponse({'html': html})
        
    except Exception as e:
        logger.error(f"Ошибка в generate_task9_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


@login_required
def generate_chered_exercise(request):
    """Задание 9 ЕГЭ: Чередующиеся гласные (орфограммы 12,13,24,26,27,271,272,273,274,275)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        # Конфигурация
        ORTH_IDS = [12, 13, 24, 26, 27, 271, 272, 273, 274, 275]
        TOTAL_NEEDED = 16
        WORDS_PER_ORTH = 2  # по 2 слова из каждой орфограммы
        
        examples_data = []
        
        # 1. Берем слова из всех орфограмм чередования (только 10-11 классы)
        for orth_id in ORTH_IDS:
            if len(examples_data) >= TOTAL_NEEDED:
                break
            
            qs = OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True,
                grades__contains='11'  # только 11 класс для ЕГЭ
            ).order_by('?')[:WORDS_PER_ORTH]
            
            for ex in qs:
                if len(examples_data) >= TOTAL_NEEDED:
                    break
                letter = extract_correct_letter(ex.text, ex.masked_word)
                if letter:
                    examples_data.append((ex, letter.lower(), orth_id))
        
        # 2. Добираем при необходимости (из всех орфограмм)
        if len(examples_data) < TOTAL_NEEDED:
            taken_ids = [ex.id for ex, _, _ in examples_data]
            remaining = TOTAL_NEEDED - len(examples_data)
            
            extra = OrthogramExample.objects.filter(
                orthogram_id__in=ORTH_IDS,
                is_active=True,
                grades__contains='11'
            ).exclude(id__in=taken_ids).order_by('?')[:remaining]
            
            for ex in extra:
                letter = extract_correct_letter(ex.text, ex.masked_word)
                if letter:
                    examples_data.append((ex, letter.lower(), ex.orthogram_id))
        
        if not examples_data:
            return JsonResponse({'error': 'Нет примеров для чередующихся гласных'}, status=404)
        
        # 3. Перемешиваем, обрезаем и валидируем
        random.shuffle(examples_data)
        examples_data = examples_data[:TOTAL_NEEDED]

        formatted_items = []
        correct_letters = []
        example_ids = []

        for ex, letter, orth_id in examples_data:
            # Нормализуем маску
            masked = re.sub(r'\*[^*]+\*', f'*{orth_id}*', ex.masked_word.strip())
            
            # === ВАЛИДАЦИЯ ДО ДОБАВЛЕНИЯ ===
            if '*' not in masked:
                continue
            if '  ' in masked or masked.startswith(',') or masked.endswith(','):
                continue
            if len(masked) < 2:
                continue
            if masked in formatted_items:
                continue
            
            # === ТОЛЬКО ТЕПЕРЬ ДОБАВЛЯЕМ ===
            formatted_items.append(masked)
            correct_letters.append(letter)
            example_ids.append(ex.id)
        
        # Если после валидации осталось меньше слов - добираем
        if len(formatted_items) < TOTAL_NEEDED:
            logger.warning(f"⚠️ Чередование: после валидации осталось {len(formatted_items)} слов")
        
        # 4. Сессия
        request.session['current_exercise'] = {
            'exercise_id': 'chered_ege',
            'example_ids': example_ids[:len(formatted_items)],
            'correct_letters': correct_letters,
            'orthogram_ids': ORTH_IDS,
            # Летопись: маски слов и ключ блока. Общий эндпоинт проверки
            # (check_alphabetical_exercise) пишет по ним прохождение —
            # отдельный check для чередующихся не нужен.
            'correct_words': formatted_items,
            'orthogram_id': 'CHERED',
            'range_code': 'CHERED',
        }
        
        # 5. Рендерим
        html = render_to_string('exercise_snippet.html', {
            'words_text': ', '.join(formatted_items),
            'exercise_id': 'chered_ege',
            'exercise_title': 'Чередующиеся гласные',
            'show_next_button': False,
        })
        
        return JsonResponse({
            'html': html,
            'word_count': len(formatted_items),
            'orthogram_id': 'CHERED',
            'range_code': 'CHERED',
            'report': _task9_report(request.user, 'CHERED', 'CHERED'),
        })
        
    except Exception as e:
        logger.error(f"Ошибка в generate_chered_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

def _task9_correction_data(user, orthogram_id: str, range_code: str) -> list:
    """Слова, стоящие на коррекции в блоке задания 9 (группировка по датам — на фронте)."""
    stats = Task9WordStat.objects.filter(
        user=user, orthogram_id=orthogram_id, range_code=range_code, in_correction=True,
    ).order_by('-correction_since')
    return [{
        'word': s.word,
        'chosen_letter': s.last_chosen_letter,
        'correct_letter': s.correct_letter,
        'errors': s.errors,
        'correction_since': s.correction_since.strftime('%d.%m.%Y') if s.correction_since else '',
    } for s in stats]


def _task9_attempts_data(user, orthogram_id: str, range_code: str) -> list:
    """История прохождений блока задания 9 (20 последних)."""
    attempts = Task9Attempt.objects.filter(
        user=user, orthogram_id=orthogram_id, range_code=range_code,
    ).order_by('-created_at')[:20]
    return [{
        'date': a.created_at.strftime('%d.%m.%Y %H:%M'),
        'chosen': a.chosen_count,
        'correct': a.correct_count,
    } for a in attempts]


def _task9_report(user, orthogram_id: str, range_code: str) -> dict:
    """Проверочно-отчётный блок: текущие ошибки + история прохождений."""
    return {
        'correction': _task9_correction_data(user, orthogram_id, range_code),
        'attempts': _task9_attempts_data(user, orthogram_id, range_code),
    }


@login_required
def check_alphabetical_exercise(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        data = json.loads(request.body)
        selected_letters = data.get('selected_letters', [])
        
        # Получаем правильные буквы из сессии
        exercise_data = request.session.get('current_exercise', {})
        correct_letters = exercise_data.get('correct_letters', [])
        
        if not correct_letters:
            return JsonResponse({'error': 'Нет данных для проверки'}, status=400)
        
        # Проверяем ответы
        results = []
        correct_count = 0
        total_count = len(correct_letters)
        
        for i, selected in enumerate(selected_letters):
            if i >= len(correct_letters):
                break
            
            correct = correct_letters[i]
            
            if selected is None:
                # Не выбрана буква
                results.append(False)
            elif selected == correct:
                # Правильно
                results.append(True)
                correct_count += 1
            else:
                # Неправильно
                results.append(False)
        
        all_correct = correct_count == total_count
        
        # === ЛЕТОПИСЬ: сохраняем прохождение и обновляем статистику слов ===
        orthogram_id = str(exercise_data.get('orthogram_id', ''))
        range_code = str(exercise_data.get('range_code', ''))
        correct_words = exercise_data.get('correct_words', [])
        resolved = []

        if orthogram_id and range_code:
            now = timezone.now()
            with transaction.atomic():
                attempt = Task9Attempt.objects.create(
                    user=request.user,
                    orthogram_id=orthogram_id,
                    range_code=range_code,
                    total_words=total_count,
                    chosen_count=sum(1 for s in selected_letters if s is not None),
                    correct_count=correct_count,
                )
                for i, is_correct in enumerate(results):
                    if i >= len(selected_letters) or selected_letters[i] is None:
                        continue   # буква не выбрана — в летопись не пишем
                    word = correct_words[i] if i < len(correct_words) else f'#{i}'
                    chosen = selected_letters[i]
                    Task9AttemptWord.objects.create(
                        attempt=attempt, word=word,
                        chosen_letter=chosen, correct_letter=correct_letters[i],
                        is_correct=is_correct,
                    )
                    stat, _ = Task9WordStat.objects.get_or_create(
                        user=request.user, orthogram_id=orthogram_id, word=word,
                        defaults={'range_code': range_code,
                                  'correct_letter': correct_letters[i]},
                    )
                    stat.range_code = range_code
                    stat.correct_letter = correct_letters[i]
                    stat.attempts += 1
                    stat.last_seen = now
                    stat.last_result = is_correct
                    stat.last_chosen_letter = chosen
                    if is_correct:
                        if stat.in_correction:
                            resolved.append({'word': word,
                                           'correct_letter': correct_letters[i]})
                        stat.in_correction = False
                        stat.correction_since = None
                    else:
                        stat.errors += 1
                        if not stat.in_correction:
                            stat.in_correction = True
                            stat.correction_since = now.date()
                    stat.save()

        return JsonResponse({
            'results': results,
            'correct_count': correct_count,
            'total_count': total_count,
            'all_correct': all_correct,
            'orthogram_id': orthogram_id,
            'range_code': range_code,
            'resolved': resolved,
            'report': (_task9_report(request.user, orthogram_id, range_code)
                       if orthogram_id and range_code else None),
        })
        
    except Exception as e:
        logger.error(f"Ошибка в check_alphabetical_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


@csrf_exempt
@login_required
def check_exercise(request):
    if request.method != 'POST':
        logger.warning("Получен не POST-запрос в check_exercise")
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        # === Парсинг тела запроса ===
        data = json.loads(request.body)
        user_letters = data.get('user_words', [])
        logger.info(f"Получены ответы от пользователя: {user_letters}")

        if not isinstance(user_letters, list):
            logger.error("Некорректный формат: user_words не является списком")
            return JsonResponse({'error': 'Некорректный формат данных'}, status=400)

        # === Получение сессии ===
        current_exercise = request.session.get('current_exercise')
        if not current_exercise:
            logger.error("Нет активного упражнения в сессии")
            return JsonResponse({'error': 'Нет активного упражнения'}, status=400)

        correct_letters = current_exercise.get('correct_letters', [])
        exercise_id = current_exercise.get('exercise_id', '')
        
        logger.info(f"Ожидаемые ответы: {correct_letters}")
        logger.info(f"Exercise ID: {exercise_id}")
        
        # === ОБРАБОТКА МНОЖЕСТВЕННЫХ МАСОК (орфограммы 1400 и 1500) ===
        is_multi_mask = exercise_id.startswith('multi_')
        
        if is_multi_mask:
            # correct_letters = [['нн', 'н', 'нн', 'нн', 'н', 'н']] - список списков
            # user_letters = ['н', 'н', 'нн', 'нн', 'н', 'н'] - плоский список
            results = []
            user_index = 0
            
            for example_index, example_letters in enumerate(correct_letters):
                example_results = []
                for correct_letter in example_letters:
                    if user_index >= len(user_letters):
                        example_results.append(False)
                    else:
                        user_clean = user_letters[user_index].strip()
                        correct_clean = correct_letter.strip()  # ← ЭТО РАБОТАЕТ, потому что correct_letter теперь строка
                        is_correct = user_clean == correct_clean
                        example_results.append(is_correct)
                        user_index += 1
                results.extend(example_results)
            
        else:
            # === ОБЫЧНАЯ ПРОВЕРКА (одна маска на строку) ===
            if len(user_letters) != len(correct_letters):
                logger.warning(f'⚠️ Несоответствие длин: {len(user_letters)} != {len(correct_letters)}')
                min_len = min(len(user_letters), len(correct_letters))
                user_letters = user_letters[:min_len]
                correct_letters = correct_letters[:min_len]

            results = []
            for i, (user_letter, correct_letter) in enumerate(zip(user_letters, correct_letters)):
                user_clean = user_letter.strip()
                correct_clean = correct_letter.strip()
                is_correct = user_clean == correct_clean
                results.append(is_correct)

        logger.info(f"Итоговые результаты: {results}")
        return JsonResponse(results, safe=False)

    except json.JSONDecodeError:
        logger.error("Ошибка декодирования JSON из тела запроса")
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)
    except Exception as e:
        logger.error(f"Критическая ошибка в check_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка проверки'}, status=500)



# === АВТОРИЗАЦИЯ ВК ===
# === Эндпоинты для сайта (с авторизацией) ===

@login_required
def vk_status(request):
    """Статус привязки ВК"""
    p = request.user.profile
    return JsonResponse({'is_linked': bool(p.vk_id)})


@login_required
def vk_generate_code(request):
    """Генерация кода для привязки"""
    p = request.user.profile
    p.link_code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))
    p.link_code_expires = timezone.now() + timedelta(hours=1)
    p.save()
    return JsonResponse({
        'status': 'success',
        'code': p.link_code,
        'expires': p.link_code_expires.strftime('%H:%M')
    })


# === Эндпоинты для бота (без авторизации) ===
@login_required
def vk_create_link(request):
    """ЛК: создать одноразовый код привязки VK (действует 1 час)."""
    if request.method == 'POST':
        p, _ = UserProfile.objects.get_or_create(user=request.user)
        if p.level >= 1:
            p.link_code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))
            p.link_code_expires = timezone.now() + timedelta(hours=1)
            p.save(update_fields=['link_code', 'link_code_expires'])
            messages.success(request, 'Код создан. Отправьте его боту в течение часа.')
        else:
            messages.warning(request, 'Бот доступен на платных тарифах и на триале.')
    return redirect('profile')


@login_required
def vk_unlink(request):
    """ЛК: отвязать VK."""
    if request.method == 'POST':
        p, _ = UserProfile.objects.get_or_create(user=request.user)
        if p.vk_id:
            p.vk_id = None
            p.save(update_fields=['vk_id'])
            messages.success(request, 'VK отключён.')
    return redirect('profile')


@csrf_exempt
def vk_health(request):
    """Проверка API"""
    return JsonResponse({'status': 'ok'})


@login_required
def max_create_link(request):
    """ЛК: создать одноразовый код привязки MAX (действует 1 час)."""
    if request.method == 'POST':
        p, _ = UserProfile.objects.get_or_create(user=request.user)
        if p.level >= 1:
            p.link_code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=8))
            p.link_code_expires = timezone.now() + timedelta(hours=1)
            p.save(update_fields=['link_code', 'link_code_expires'])
            messages.success(request, 'Код создан. Нажмите «Привязать» или отправьте код боту.')
        else:
            messages.warning(request, 'Бот доступен на платных тарифах и на триале.')
    return redirect('profile')


@login_required
def max_unlink(request):
    """ЛК: отвязать MAX."""
    if request.method == 'POST':
        p, _ = UserProfile.objects.get_or_create(user=request.user)
        if p.max_id:
            p.max_id = None
            p.save(update_fields=['max_id'])
            messages.success(request, 'MAX отключён.')
    return redirect('profile')


# === API: получение квиза в ЛК ===

@login_required
def quiz_snippet_api(request, quiz_type):
    """Минималистичный сниппет квиза"""
    templates = {
        'planning': 'quiz/quiz_planning_snippet.html',
        'orthography': 'quiz/quiz_orthography_snippet.html',
        'orthoepy': 'quiz/quiz_orthoepy_snippet.html',
        'grammar': 'quiz/quiz_grammar_snippet.html',
        'hot': 'quiz/quiz_hot_snippet.html',
    }
    tpl = templates.get(quiz_type)
    if not tpl:
        return JsonResponse({'error': 'Неизвестный тип'}, status=400)
    
    html = render_to_string(tpl, {'quiz_type': quiz_type}, request=request)
    return JsonResponse({'html': html})


@login_required
def get_quiz(request):
    """Квиз по орфографии или грамматике"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=400)
    
    import json, random, re
    import traceback
    
    try:
        data = json.loads(request.body)
        quiz_type = data.get('quiz_type', 'orthography')

        #Freemium: личные квизы закрыты для тарифа «0»
        _prof, _ = UserProfile.objects.get_or_create(user=request.user)
        if _prof.level == 0:
            return JsonResponse({'error': '🔒 Личные квизы доступны на платных тарифах. «🔥 Горячие» открыты для всех 🙂'}, status=403)
        
        from .models import OrthogramExample
        
        # Базовый запрос: эталонные вопросы с explanation
        base_query = OrthogramExample.objects.filter(
            is_active=True,
            is_user_added=False,
            explanation__isnull=False,
            incorrect_variant__isnull=False
        ).exclude(
            explanation='',
            incorrect_variant=''
        ).select_related('orthogram')
        
        # Фильтр по типу квиза
        if quiz_type == 'grammar':
            # Грамматика: орфограмма 661
            base_query = base_query.filter(orthogram_id=661)
        else:
            # Орфография: всё кроме 661
            base_query = base_query.exclude(orthogram_id=661)
        
        if not base_query.exists():
            return JsonResponse({'error': f'Нет вопросов для раздела {quiz_type}'})
        
        # Выбираем случайное слово
        reference = base_query.order_by('?').first()
        
        correct = reference.text
        masked = re.sub(r'\*\d+\*', '😊', reference.masked_word or '') if reference.masked_word else correct
        incorrect = reference.incorrect_variant.strip()
        explanation = reference.explanation
        
        options = [
            {'text': correct, 'is_correct': True},
            {'text': incorrect, 'is_correct': False}
        ]
        random.shuffle(options)
        
        return JsonResponse({
            'question': f'Как пишется правильно? {{word:{masked}}}',
            'options': options,
            'correct_answer': correct,
            'explanation': explanation,
            'example_id': reference.id
        })
        
    except Exception as e:
        print(f"Ошибка в get_quiz: {e}")
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@csrf_exempt  # <-- Добавь csrf_exempt, если бот будет вызывать напрямую без токена
def get_quiz_orthoepy_pair(request):
    """Квиз по ударениям. Возвращает options с флагом is_correct"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=400)

    # Freemium: для тарифа «0» закрыто
    _prof, _ = UserProfile.objects.get_or_create(user=request.user)
    if _prof.level == 0:
        return JsonResponse({'error': '🔒 Этот квиз доступен на платных тарифах. «🔥 Горячие» открыты для всех 🙂'}, status=403)

    import random
    from .models import OrthoepyWord
    from django.db.models import Count

    # Ищем леммы, у которых есть минимум 2 варианта (правильный и неправильный)
    lemmas_with_both = OrthoepyWord.objects.filter(
        is_active=True
    ).values('lemma').annotate(
        variant_count=Count('id')
    ).filter(variant_count__gte=2)

    if not lemmas_with_both:
        return JsonResponse({'error': 'Нет слов для ударений'}, status=404)

    # Выбираем случайную лемму
    selected_lemma = random.choice(lemmas_with_both)['lemma']
    
    # Получаем все варианты для этой леммы
    variants = list(OrthoepyWord.objects.filter(
        lemma=selected_lemma,
        is_active=True
    ))

    correct_variant = None
    incorrect_variant = None
    
    for v in variants:
        if v.is_correct:
            correct_variant = v
        else:
            incorrect_variant = v

    if not correct_variant or not incorrect_variant:
        return JsonResponse({'error': 'Нет пары для слова'}, status=404)

    # Формируем ответ в едином формате (options)
    options = [
        {'text': correct_variant.word, 'is_correct': True},
        {'text': incorrect_variant.word, 'is_correct': False}
    ]
    random.shuffle(options)

    return JsonResponse({
        'question': f"Как правильно поставить ударение в слове «{correct_variant.lemma}»?",
        'options': options,
        'example_id': correct_variant.id,  # ID правильного слова для логирования
        'correct_answer': correct_variant.word
    })

@login_required
def log_quiz_answer_site(request):
    """Логирует ответ пользователя на сайте. Создаёт запись в истории ОДИН РАЗ."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=400)
    
    try:
        import json
        from .models import QuizHistory, UserWord
        from django.utils import timezone

        data = json.loads(request.body)
        word_id = data.get('example_id') or data.get('word_id')
        user_word_id = data.get('user_word_id')
        is_correct = bool(data.get('is_correct', False))

        if not word_id:
            return JsonResponse({'error': 'Missing word_id'}, status=400)

        # ✅ Создаём запись в истории ТОЛЬКО при ответе
        QuizHistory.objects.create(
            user=request.user,
            word_id=word_id,
            user_word_id=user_word_id,
            was_correct=is_correct,
            answer_time=timezone.now()
        )

        # ✅ Обновляем статистику слова в планинге (если есть связь)
        if user_word_id:
            try:
                uw = UserWord.objects.get(id=user_word_id, user=request.user)
                if is_correct:
                    uw.success_count += 1
                else:
                    uw.error_count += 1
                    uw.last_error = timezone.now()
                uw.last_shown = timezone.now()
                uw.save()
            except UserWord.DoesNotExist:
                pass  # Слово не из планинга (общая орфография)

        return JsonResponse({'status': 'ok'})
        
    except Exception as e:
        import logging, traceback
        logging.error(f"Log quiz answer error: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': 'Internal error'}, status=500)

@login_required
def get_planning_quiz(request):
    """Квиз из планинга: строгий последовательный цикл 1→2→3→...→1"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=400)

    # Freemium: для тарифа «0» закрыто
    _prof, _ = UserProfile.objects.get_or_create(user=request.user)
    if _prof.level == 0:
        return JsonResponse({'error': '🔒 Личные квизы доступны на платных тарифах. «🔥 Горячие» открыты для всех 🙂'}, status=403)

    try:
        # 1️⃣ Отбираем ТОЛЬКО полностью готовые слова. Остальные игнорируются.
        valid_qs = UserWord.objects.filter(
            user=request.user, is_active=True, reference_word__isnull=False
        ).select_related('reference_word')

        valid_words = [
            uw for uw in valid_qs
            if (uw.reference_word.is_active
                and uw.reference_word.explanation and uw.reference_word.explanation.strip()
                and uw.reference_word.incorrect_variant and uw.reference_word.incorrect_variant.strip())
        ]

        if not valid_words:
            # Планинг пуст или слова не совпали с эталонной базой:
            # останавливаем квиз и подсказываем записать примеры.
            total_active = UserWord.objects.filter(user=request.user, is_active=True).count()
            if total_active == 0:
                msg = '📝 В планинге нет слов. Запишите примеры — и они появятся в квизе.'
            else:
                msg = ('📝 В планинге пока нет слов, готовых к квизу. '
                       'Запишите примеры — и они появятся в квизе.')
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            return JsonResponse({'error': msg, 'empty': True,
                                 'planning_url': _planning_url(profile)})

        # Стабильный порядок обхода (по ID)
        valid_words.sort(key=lambda x: x.id)
        ids = [uw.id for uw in valid_words]

        # 2️⃣ Ищем последнее отвеченное слово
        last = QuizHistory.objects.filter(user=request.user).order_by('-answer_time').first()
        current_idx = 0
        
        if last:
            target = last.user_word_id
            
            # 🔹 ФОЛЛБЕК: если фронт не прислал user_word_id, ищем совпадение по example_id (word_id)
            if not target and last.word_id:
                for i, uw in enumerate(valid_words):
                    if uw.reference_word_id == last.word_id:
                        target = uw.id
                        break

            if target in ids:
                current_idx = ids.index(target)

        # 3️⃣ Вычисляем следующий индекс (цикл)
        next_idx = (current_idx + 1) % len(valid_words)

        selected = valid_words[next_idx]
        ref = selected.reference_word

        # ❗ НЕ создаём QuizHistory здесь! Только в log_quiz_answer_site

        # 4️⃣ Формируем ответ
        masked = re.sub(r'\*\d+\*', '😊', ref.masked_word or ref.text)
        options = [
            {'text': ref.text, 'is_correct': True},
            {'text': ref.incorrect_variant.strip(), 'is_correct': False}
        ]
        random.shuffle(options)  # Только кнопки, не нарушая цикл слов

        return JsonResponse({
            'question': f'Как пишется правильно? {{word:{masked}}}',
            'options': options,
            'correct_answer': ref.text,
            'explanation': ref.explanation,
            'example_id': ref.id,
            'user_word_id': selected.id
        })

    except Exception as e:
        import logging
        logging.error(f"Planning quiz error: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка загрузки'}, status=500)

@login_required
def site_daily_word(request):
    """Слово дня: состояние revealed/waiting + текущее время МСК."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if not bot_core.user_can_use_bot(profile):
        return JsonResponse({'state': 'waiting',
                             'message': 'Слово дня доступно на платных тарифах и на триале.'})
    return JsonResponse(bot_core.get_daily_word_state(profile))


@login_required
def site_daily_answer(request):
    """Ответ на слово дня. В статистику не попадает."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'bad json'}, status=400)
    result = bot_core.answer_daily_word(profile, data.get('period_date'), data.get('selected_index'))
    return JsonResponse(result)


# === СТАТИСТИКА для ЛК ===
@login_required
def get_user_quiz_stats_site(request):
    """Статистика + умные рекомендации с группировкой"""
    try:
        user = request.user
        from .models import UserWord, QuizHistory, OrthogramExample, OrthoepyWord
        from django.utils import timezone
        from datetime import timedelta
        
        # 1. Слова в планинге
        total_planning = UserWord.objects.filter(user=user, is_active=True).count()
        
        # 2. Всего попыток
        total_quizzes = QuizHistory.objects.filter(user=user).count()
        
        # 3. Правильные ответы
        correct = QuizHistory.objects.filter(user=user, was_correct=True).count()
        
        # 4. Успешность
        success_rate = round(correct / total_quizzes * 100) if total_quizzes > 0 else 0
        
        # 5. Ошибки за неделю
        week_ago = timezone.now() - timedelta(days=7)
        wrong_answers = QuizHistory.objects.filter(
            user=user,
            was_correct=False,
            answer_time__gte=week_ago
        )
        
        # 🔹 Убрали need_repeat — не используем
        
        # 6. Считаем ошибки по типам
        ortho_errors = {}  # {orth_id: {'name': ..., 'words': set()}}
        preposition_total = 0
        preposition_wrong = 0
        orthoepy_total = 0
        orthoepy_wrong = 0
        
        for answer in wrong_answers:
            if answer.word_id:
                # 🔍 Проверяем: это ударение (OrthoepyWord)?
                try:
                    orthoepy_word = OrthoepyWord.objects.get(id=answer.word_id)
                    orthoepy_wrong += 1
                    continue
                except OrthoepyWord.DoesNotExist:
                    pass
                
                # 🔍 Проверяем: это орфограмма (OrthogramExample)?
                try:
                    word = OrthogramExample.objects.get(id=answer.word_id)
                    orth_id = word.orthogram_id
                    
                    # 🔹 Предлоги: короткие слова (1-3 буквы)
                    if len(word.text) <= 3:
                        preposition_wrong += 1
                    else:
                        # 🔹 Орфограммы: группируем по ID
                        if orth_id:
                            if orth_id not in ortho_errors:
                                orth_name = word.orthogram.name if word.orthogram else f'Орфограмма {orth_id}'
                                ortho_errors[orth_id] = {
                                    'name': orth_name,
                                    'words': set()
                                }
                            ortho_errors[orth_id]['words'].add(word.text)
                except OrthogramExample.DoesNotExist:
                    pass
        
        # 🔹 Считаем общее количество попыток по типам (для процента)
        all_history = QuizHistory.objects.filter(user=user, answer_time__gte=week_ago)
        for answer in all_history:
            if answer.word_id:
                # Ударения
                try:
                    OrthoepyWord.objects.get(id=answer.word_id)
                    orthoepy_total += 1
                    continue
                except:
                    pass
                
                # Орфограммы/предлоги
                try:
                    word = OrthogramExample.objects.get(id=answer.word_id)
                    if len(word.text) <= 3:
                        preposition_total += 1
                except:
                    pass
        
        # 🔹 7. Формируем рекомендации
        recommendations = []
        
        # Орфограммы (слова + номера) — 🔹 ПРОБЕЛ ПОСЛЕ №
        for orth_id, data in sorted(ortho_errors.items(), key=lambda x: len(x[1]['words']), reverse=True):
            words_list = ', '.join(list(data['words'])[:5])  # Максимум 5 слов
            recommendations.append(f"{words_list} — орф. № {orth_id}")  # ← № пробел
        
        # Предлоги (если ошибок > 20%)
        preposition_rate = (preposition_wrong / preposition_total * 100) if preposition_total > 0 else 0
        if preposition_rate > 20:
            recommendations.append("Повтори правописание предлогов")
        
        # Ударения (если ошибок > 20%)
        orthoepy_rate = (orthoepy_wrong / orthoepy_total * 100) if orthoepy_total > 0 else 0
        if orthoepy_rate > 20:
            recommendations.append("Повтори ударения")
        
        return JsonResponse({
            'total_planning': total_planning,
            'total_quizzes': total_quizzes,
            'correct': correct,
            'success_rate': success_rate,
            'recommendations': recommendations  # 🔹 Убрали need_repeat
        })
        
    except Exception as e:
        print(f"Stats error: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'total_planning': 0,
            'total_quizzes': 0,
            'correct': 0,
            'success_rate': 0,
            'recommendations': []
        })


# === отчёты для ЛК ===

@login_required
def get_weekly_report(request):
    """Для отображения в ЛК (через GET, с авторизацией)"""
    
    week_ago = timezone.now() - timezone.timedelta(days=7)
    answers = StudentAnswer.objects.filter(
        user=request.user,
        answered_at__gte=week_ago
    )

    if not answers.exists():
        return JsonResponse({
            'status': 'inactive',
            'message': 'За последнюю неделю ты не выполнял упражнений. Пора начать!'
        })

    total = answers.count()
    correct = answers.filter(is_correct=True).count()
    success_rate = round(correct / total * 100, 1)
    weak_orthograms = answers.filter(is_correct=False)\
        .values('orthogram__id', 'orthogram__name')\
        .annotate(errors=Count('id'))\
        .order_by('-errors')[:3]

    return JsonResponse({
        'status': 'active',
        'total': total,
        'correct': correct,
        'success_rate': success_rate,
        'weak_orthograms': list(weak_orthograms),
        'message': f"Ты выполнил {total} заданий, {correct} из них — правильно ({success_rate}%)."
    })


# === СТАТИСТИКА для админа, учителя ===
@staff_member_required
def admin_planning_check(request):
    """Проверка слов из планингов прямо в админке"""
    
    # Получаем все уникальные слова из планингов
    planning_words = UserWord.objects.filter(
        is_active=True
    ).values('text').annotate(
        user_count=Count('user', distinct=True)
    ).order_by('-user_count')
    
    missing_words = []
    
    for item in planning_words:
        word_text = item['text']
        # Проверяем, есть ли слово в эталонной БД
        exists = OrthogramExample.objects.filter(
            text=word_text,
            is_user_added=False
        ).exists()
        
        if not exists:
            missing_words.append({
                'text': word_text,
                'user_count': item['user_count']
            })
    
    return render(request, 'admin/planning_check.html', {
        'missing_words': missing_words,
        'total_planning': planning_words.count(),
        'total_missing': len(missing_words)
    })


@staff_member_required
def teacher_analytics_view(request):
    """
    Страница аналитики для преподавателя
    Доступ: только для админов и преподавателей
    """
    from .assistants.teacher_analytics import TeacherAnalytics
    
    analytics = TeacherAnalytics()
    
    # Общая статистика
    overview = analytics.get_overview(days=7)
    
    # Все ученики (сводка)
    students_summary = analytics.get_all_students_summary()
    
    # Слова без объяснений
    missing_explanations = analytics.get_missing_explanations_list(limit=100)
    
    context = {
        'overview': overview,
        'students_summary': students_summary,
        'missing_explanations': missing_explanations,
    }
    
    return render(request, 'admin/analytics.html', context)


@staff_member_required
def student_detail_view(request, user_id):
    """Детальная информация по ученику"""
    from .assistants.teacher_analytics import TeacherAnalytics
    
    analytics = TeacherAnalytics()
    
    try:
        details = analytics.get_student_details(user_id)
    except Exception as e:
        return HttpResponse(f"❌ Ошибка: {e}", status=404)
    
    return render(request, 'admin/student_detail.html', {
        'student': details
    })


# === ПЕРСОНАЛИЗИРОВАННЫЕ КВИЗЫ ИЗ ПЛАНИНГА ===
# ========================================================================
# ✅ ВСПОМОГАТЕЛЬНАЯ: парсинг слов
# ========================================================================
def parse_words_from_text(text):
    """Разбивает текст на слова по переносам строк"""
    if not text:
        return []
    lines = re.split(r'\r?\n', text)
    return [line.strip() for line in lines if line.strip()]


# ========================================================================
# ✅ API: СОХРАНЕНИЕ ПРИМЕРОВ (ПЛАНИНГ)
# ========================================================================
log = logging.getLogger(__name__)

@login_required
def save_example(request):
    """Сохраняет слова из ЛЮБОГО поля планинга в UserWord"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=400)
    
    field_name = request.POST.get('field_name')
    content = request.POST.get('content', '').strip()
    
    if not field_name:
        return JsonResponse({'status': 'error', 'message': 'Missing field_name'}, status=400)
    
    try:
        # 1️⃣ Всегда сохраняем исходный текст в UserExample (резерв)
        UserExample.objects.update_or_create(
            user=request.user,
            field_name=field_name,
            defaults={'content': content}
        )
        
        # 2️⃣ Парсим слова (поддержка переносов строк и запятых)
        raw_words = content.replace(',', '\n').split('\n')
        words = [w.strip() for w in raw_words if w.strip()]
        
        # 3️⃣ Удаляем старые записи ТОЛЬКО для этого поля.
        #    ВАЖНО: делаем это ДО проверки «слов нет» — иначе при полностью
        #    очищенном поле старые UserWord остаются и «крутятся» в квизах.
        deleted, _ = UserWord.objects.filter(
            user=request.user,
            field_name=field_name
        ).delete()

        if not words:
            return JsonResponse({'status': 'success', 'count': 0, 'message': 'Слов не найдено'})
        
        # 3.5️⃣ Лимит тарифа «0»: не более FREE_PLANNING_WORDS активных слов суммарно
        cap_reached = False
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.level == 0:
            others = UserWord.objects.filter(user=request.user, is_active=True).count()
            allowed = max(0, FREE_PLANNING_WORDS - others)
            if len(words) > allowed:
                words = words[:allowed]
                cap_reached = True
            if not words:
                return JsonResponse({
                    'status': 'success', 'count': 0, 'cap_reached': True,
                    'message': f'На тарифе «0» в планинге — до {FREE_PLANNING_WORDS} слов. Больше — в платных тарифах 🙂'
                })

        # 4️⃣ Сохраняем каждое слово в UserWord
        saved_count = 0
        with_ref = 0
        for word_text in words:
            ref = OrthogramExample.objects.filter(text__iexact=word_text, is_active=True).first()
            if ref:
                with_ref += 1
                
            UserWord.objects.create(
                user=request.user,
                field_name=field_name,
                text=word_text,
                reference_word=ref,  # None — ок, слово всё равно учтётся в статистике
                is_active=True
            )
            saved_count += 1
            
        log.info(
            f"✅ save_example: user={request.user.id}, field={field_name}, "
            f"saved {saved_count} words, {with_ref} with reference"
        )
        
        return JsonResponse({
            'status': 'success',
            'count': saved_count,
            'with_reference': with_ref,
            'cap_reached': cap_reached,
            'message': (f'Сохранено {saved_count} слов. На тарифе «0» — до {FREE_PLANNING_WORDS} слов; больше — в платных тарифах 🙂'
                        if cap_reached else f'Сохранено {saved_count} слов')
        })
            
    except Exception as e:
        log.error(f"❌ save_example error: {e}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

# ========================================================================
# ✅ API: ЗАГРУЗКА ПРИМЕРОВ
# ========================================================================
@login_required
def load_examples(request):
    """Загружает слова пользователя для отображения в планинге"""
    result = {}
    
    # Загружаем из UserExample (резерв)
    for ue in UserExample.objects.filter(user=request.user):
        result[ue.field_name] = ue.content
    
    # Можно добавить дополнительную информацию
    return JsonResponse(result)


# ========================================================================
# ✅ API: КВИЗ ДЛЯ БОТА — ГЛАВНАЯ ФУНКЦИЯ
# ========================================================================
def _get_personalized_preposition_quiz(user_id: int) -> dict:
    from .models import UserWord, OrthogramExample, QuizHistory
    from django.utils import timezone
    import random, re

    today = timezone.now().date()

    # 🔹 1. История за сегодня (исключаем повторы)
    shown_today = set(
        QuizHistory.objects.filter(user_id=user_id, answer_time__date=today)
        .values_list('word_id', flat=True)
    )

    # 🔹 2. ЯВНО получаем планинг пользователя (убираем Pylance error)
    planning_qs = UserWord.objects.filter(
        user_id=user_id, is_active=True
    ).select_related('reference_word')

    planning_candidates = []
    for pw in planning_qs:
        ref = pw.reference_word
        if (ref and ref.is_active and ref.explanation and ref.incorrect_variant 
                and ref.id not in shown_today):
            planning_candidates.append({
                'word': ref,
                'user_word_id': pw.id,
                'source': 'planning'
            })

    selected = None

    # 🔹 3. Приоритет: планинг → общая база → фоллбек
    if planning_candidates:
        selected = random.choice(planning_candidates)
    else:
        general_qs = OrthogramExample.objects.filter(
            is_active=True, is_user_added=False,
            explanation__isnull=False, incorrect_variant__isnull=False
        ).exclude(explanation='', incorrect_variant='') \
         .exclude(id__in=shown_today) \
         .select_related('orthogram')

        if general_qs.exists():
            word_obj = general_qs.order_by('?').first()
            selected = {'word': word_obj, 'user_word_id': None, 'source': 'general'}

    if selected is None:
        return {
            'question': 'Как пишется правильно:\нв**а',
            'options': [{'text': 'вода', 'is_correct': True}, {'text': 'вада', 'is_correct': False}],
            'explanation': 'Проверяемая гласная в корне',
            'example_id': 0, 'user_word_id': None, 'source': 'fallback',
            'letter_correct': 'о', 'letter_incorrect': 'а'
        }

    # 🔹 4. Извлекаем буквы и формируем ответ
    word = selected['word']
    l_corr, l_incorr = _extract_diff_letters(word.text, word.incorrect_variant)
    masked = re.sub(r'\*\d+\*', '😊', word.masked_word or word.text)

    return {
        'question': f"Как пишется правильно:\n{masked}",
        'options': [
            {'text': word.text, 'is_correct': True},
            {'text': word.incorrect_variant, 'is_correct': False}
        ],
        'letter_correct': l_corr,
        'letter_incorrect': l_incorr,
        'explanation': word.explanation or (word.orthogram.rule if word.orthogram else 'Правило не указано'),
        'example_id': word.id,
        'user_word_id': selected['user_word_id'],
        'source': selected['source']
    }

@csrf_exempt
def user_progress(request):
    """Возвращает прогресс пользователя"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    data = json.loads(request.body)
    user_id = data.get('user_id')
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Слова с высокой успешностью (минимум 3 попытки)
    mastered = []
    history = QuizHistory.objects.filter(user_id=user_id)
    
    word_stats = {}
    for h in history:
        if h.word_id not in word_stats:
            word_stats[h.word_id] = {'total': 0, 'correct': 0}
        word_stats[h.word_id]['total'] += 1
        if h.was_correct:
            word_stats[h.word_id]['correct'] += 1
    
    for word_id, stats in word_stats.items():
        if stats['total'] >= 3:
            rate = (stats['correct'] / stats['total'] * 100)
            if rate >= 80:
                word = OrthogramExample.objects.get(id=word_id)
                mastered.append({
                    'text': word.text,
                    'success_rate': round(rate, 1)
                })
    
    # Прогресс за неделю
    week_history = history.filter(answer_time__date__gte=week_ago)
    prev_week = history.filter(
        answer_time__date__gte=week_ago - timedelta(days=7),
        answer_time__date__lt=week_ago
    )
    
    week_rate = week_history.filter(was_correct=True).count() / week_history.count() * 100 if week_history.count() > 0 else 0
    prev_rate = prev_week.filter(was_correct=True).count() / prev_week.count() * 100 if prev_week.count() > 0 else 0
    progress = round(week_rate - prev_rate, 1)
    
    return JsonResponse({
        'mastered_words': mastered[:10],
        'weekly_progress': progress
    })

@csrf_exempt
def user_praise(request):
    """Возвращает слова для похвалы (из любой истории)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'error': 'No user_id'}, status=400)
        
        week_ago = timezone.now().date() - timedelta(days=7)
        
        # Берем все ответы за неделю
        history = QuizHistory.objects.filter(
            user_id=user_id,
            answer_time__date__gte=week_ago
        )
        
        # Считаем статистику по каждому слову
        word_stats = {}
        for h in history:
            if h.word_id not in word_stats:
                word_stats[h.word_id] = {'total': 0, 'correct': 0}
            word_stats[h.word_id]['total'] += 1
            if h.was_correct:
                word_stats[h.word_id]['correct'] += 1
        
        # Отбираем слова с высокой успешностью (>=80% при минимум 3 попытках)
        mastered = []
        for word_id, stats in word_stats.items():
            if stats['total'] >= 3:
                rate = (stats['correct'] / stats['total'] * 100)
                if rate >= 80:
                    try:
                        word = OrthogramExample.objects.get(id=word_id)
                        mastered.append({
                            'text': word.text,
                            'success_rate': round(rate, 1),
                            'orthogram_id': word.orthogram_id
                        })
                    except OrthogramExample.DoesNotExist:
                        continue
        
        # Сортируем по убыванию успешности
        mastered.sort(key=lambda x: x['success_rate'], reverse=True)
        
        return JsonResponse({
            'mastered_words': mastered[:5],  # топ-5
            'total_mastered': len(mastered)
        })
        
    except Exception as e:
        print(f"❌ Ошибка в user_praise: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def user_weak_words(request):
    """Возвращает слова для повторения (из любой истории)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'error': 'No user_id'}, status=400)
        
        week_ago = timezone.now().date() - timedelta(days=7)
        
        # Слова с ошибками за неделю (где ошибок больше чем правильных ответов)
        history = QuizHistory.objects.filter(
            user_id=user_id,
            answer_time__date__gte=week_ago
        )
        
        # Считаем статистику по каждому слову
        word_stats = {}
        for h in history:
            if h.word_id not in word_stats:
                word_stats[h.word_id] = {'total': 0, 'correct': 0, 'errors': 0}
            word_stats[h.word_id]['total'] += 1
            if h.was_correct:
                word_stats[h.word_id]['correct'] += 1
            else:
                word_stats[h.word_id]['errors'] += 1
        
        # Отбираем слова с ошибками (минимум 2 попытки и ошибок >= 50%)
        weak_words = []
        for word_id, stats in word_stats.items():
            if stats['total'] >= 2 and stats['errors'] >= stats['correct']:
                try:
                    word = OrthogramExample.objects.get(id=word_id)
                    weak_words.append({
                        'text': word.text,
                        'errors': stats['errors'],
                        'total': stats['total'],
                        'orthogram_id': word.orthogram_id
                    })
                except OrthogramExample.DoesNotExist:
                    continue
        
        # Сортируем по количеству ошибок
        weak_words.sort(key=lambda x: x['errors'], reverse=True)
        
        return JsonResponse({'weak_words': weak_words[:10]})  # топ-10
        
    except Exception as e:
        print(f"❌ Ошибка в user_weak_words: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_word_by_id(request):
    """Возвращает слово по ID"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        word_id = data.get('word_id')
        
        if not word_id:
            return JsonResponse({'error': 'No word ID'}, status=400)
        
        from .models import OrthogramExample
        import re
        
        word = OrthogramExample.objects.filter(id=word_id, is_active=True).first()
        
        if not word:
            return JsonResponse({'error': 'Word not found'}, status=404)
        
        masked = word.masked_word if word.masked_word else word.text
        masked = re.sub(r'\*\d+\*', '😊', masked)
        
        return JsonResponse({
            'id': word.id,
            'correct': word.text,
            'incorrect': word.incorrect_variant,
            'masked': masked,
            'explanation': word.explanation or "Объяснение не найдено",
            'orthogram': word.orthogram.name if word.orthogram else "Без орфограммы"
        })
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_words_by_ids(request):
    """Возвращает список слов по массиву ID"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        word_ids = data.get('word_ids', [])
        
        if not word_ids:
            return JsonResponse({'error': 'No word IDs'}, status=400)
        
        from .models import OrthogramExample
        
        words = OrthogramExample.objects.filter(id__in=word_ids, is_active=True)
        
        result = []
        for word in words:
            result.append({
                'id': word.id,
                'text': word.text,
                'orthogram': word.orthogram.name if word.orthogram else "Без орфограммы"
            })
        
        return JsonResponse({'words': result})
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def get_orthoepy_pair(request):
    """
    Возвращает пару для теста по орфоэпии:
    - правильное ударение (is_correct=True)
    - неправильное ударение (is_correct=False)
    для одного и того же слова (леммы)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        # Получаем все уникальные леммы, у которых есть и правильный, и неправильный варианты
        from django.db.models import Count
        
        # Находим леммы, у которых есть минимум 2 варианта (правильный и неправильный)
        lemmas_with_both = OrthoepyWord.objects.filter(
            is_active=True
        ).values('lemma').annotate(
            variant_count=Count('id')
        ).filter(variant_count__gte=2)
        
        if not lemmas_with_both:
            return JsonResponse({'error': 'No words with both variants'}, status=404)
        
        # Выбираем случайную лемму
        selected_lemma = random.choice(lemmas_with_both)['lemma']
        
        # Получаем все варианты для этой леммы
        variants = list(OrthoepyWord.objects.filter(
            lemma=selected_lemma,
            is_active=True
        ))
        
        # Находим правильный и неправильный варианты
        correct = None
        incorrect = None
        
        for v in variants:
            if v.is_correct:
                correct = v
            else:
                incorrect = v
        
        if not correct or not incorrect:
            return JsonResponse({'error': 'Missing correct or incorrect variant'}, status=404)
        
        return JsonResponse({
            'id': correct.id,
            'lemma': correct.lemma,
            'variant1': correct.word,
            'variant2': incorrect.word,
            'correct': correct.word
        })
        
    except Exception as e:
        print(f"Ошибка в get_orthoepy_pair: {e}")
        return JsonResponse({'error': str(e)}, status=500)



# ========================================================================
# ✅ API ДЛЯ САЙТА: Горячие слова (ЕГЭ/ОГЭ)
# ========================================================================

from main.assistants.knowledge_bases.russian.hot_words import HOT_WORDS_LIST

_READY_HOT_WORDS = None

def _init_ready_hot_words():
    """Инициализирует список готовых слов в порядке файла"""
    global _READY_HOT_WORDS
    if _READY_HOT_WORDS is not None:
        return _READY_HOT_WORDS
    
    _READY_HOT_WORDS = []
    for word_text in HOT_WORDS_LIST:
        word = OrthogramExample.objects.filter(
            text__iexact=word_text,
            is_active=True,
            explanation__isnull=False,
            incorrect_variant__isnull=False
        ).exclude(explanation='', incorrect_variant='').first()
        if word:
            _READY_HOT_WORDS.append(word)
    
    return _READY_HOT_WORDS


@csrf_exempt
@login_required
def get_hot_word_quiz(request):
    """Квиз из горячих слов: строгий порядок по списку"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    ready = _init_ready_hot_words()
    if not ready:
        return JsonResponse({'error': 'Нет готовых слов'}, status=404)
    
    try:
        data = json.loads(request.body) if request.body else {}
        index = int(data.get('index', 0))
    except:
        index = 0
    
    word = ready[index % len(ready)]
    
    masked = re.sub(r'\*\d+\*', '😊', word.masked_word or word.text)
    l_corr, l_incorr = _extract_diff_letters(word.text, word.incorrect_variant)
    
    options = [
        {'text': word.text, 'is_correct': True},
        {'text': word.incorrect_variant.strip(), 'is_correct': False}
    ]
    random.shuffle(options)
    
    return JsonResponse({
        'question': f'Как пишется правильно? {{word:{masked}}}',
        'options': options,
        'letter_correct': l_corr,
        'letter_incorrect': l_incorr,
        'explanation': word.explanation,
        'example_id': word.id,
        'next_index': (index + 1) % len(ready),
        'total_available': len(ready)
    })


# ========================================================================
# ✅ ЧАТ-БОТ на сайте
# ========================================================================
def chat_proactive(request):
    """Проактивная рекомендация при открытии чата (раз в день на все каналы)."""
    if not request.user.is_authenticated:
        return JsonResponse({'tip': None})
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed'}, status=400)
    from main import bot_core
    prof, _ = UserProfile.objects.get_or_create(user=request.user)
    if bot_core.proactive_sent_today(request.user):
        return JsonResponse({'tip': None})
    rec = bot_core.recommend_next(prof)
    if not rec:
        return JsonResponse({'tip': None})
    bot_core.log_proactive(request.user, 'site', rec['text'])
    return JsonResponse({'tip': rec['text'], 'url': rec['url'], 'button': rec['button']})

# БЕЗ @login_required: гости получают вежливый paywall-JSON (см. ниже),
# а не 302-редирект, который ломает JSON-ответ виджету
def chat_api(request):
    """API чат-бота"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=400)

    # === Доступ к ИИ: только залогиненные + месячная квота тарифа ===
    if not request.user.is_authenticated:
        return JsonResponse({
            'paywall': True,
            'error': 'ИИ-ассистент доступен после входа. На тарифе «0» — 10 сообщений в месяц.',
        }, status=403)

    prof, _ = UserProfile.objects.get_or_create(user=request.user)
    # Квоту проверяем БЕЗ списания — спишем только после успешного ответа
    if not prof.can_use_ai():
        return JsonResponse({
            'paywall': True,
            'error': 'Лимит сообщений ИИ на этом тарифе исчерпан.',
        }, status=403)
    
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        simplify = bool(data.get('simplify'))
        
        # 🔹 История диалога из БД: последние 5 ходов за последние 30 минут
        window_start = timezone.now() - timedelta(minutes=30)
        recent = ChatMessage.objects.filter(
            user=request.user, created_at__gte=window_start
        ).order_by('-created_at')[:5]
        conversation_history = [
            {'message': t.message, 'intent': t.intent, 'guessed_word': t.guessed_word}
            for t in reversed(list(recent))
        ]
        
        # 🔹 Вызываем оркестратора — ✅ передаём request.user (объект!)
        import time as _time
        _started = _time.monotonic()
        orchestrator = get_orchestrator()
        result = orchestrator.get_response(request.user, message, conversation_history,
                                             simplify=simplify)
        
        # Квота списывается ТОЛЬКО после успешного ответа
        prof.try_consume_ai()
        
        # 🔹 Сохраняем ход диалога в БД
        chat_msg = ChatMessage.objects.create(
            user=request.user,
            message=message,
            reply=result['reply'],
            intent=result['intent'],
            specialist=result['specialist'],
            guessed_word=result.get('guessed_word'),
        )

        # 🔹 Пишем в AiQueryLog: успешный запрос
        AiQueryLog.objects.create(
            user=request.user,
            message=message,
            intent=result['intent'],
            specialist=result['specialist'],
            reply=result['reply'],
            guessed_word=result.get('guessed_word'),
            duration_ms=int((_time.monotonic() - _started) * 1000),
            chat_message=chat_msg,
        )
        
        return JsonResponse({
            'reply': result['reply'],
            'specialist': result['specialist'],
            'intent': result['intent'],
            'message_id': chat_msg.id,   # для кнопок 👍/👎
            'simplifiable': bool(result.get('simplifiable')),
        })
        
    except Exception as e:
        print(f"Chat API error: {e}")
        import traceback
        traceback.print_exc()
        # 🔹 Пишем в AiQueryLog: запрос с ошибкой (квота не списана)
        try:
            AiQueryLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                error=str(e)[:2000],
                duration_ms=int((_time.monotonic() - _started) * 1000) if '_started' in dir() else None,
            )
        except Exception:
            pass
        return JsonResponse({'reply': '⚠️ Временно не могу ответить.'})


@login_required
def chat_feedback(request):
    """Оценка ответа ассистента: 👍 / 👎."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=400)
    try:
        data = json.loads(request.body)
        msg_id = data.get('message_id')
        feedback = data.get('feedback')   # 1 или -1
        if feedback not in (1, -1):
            return JsonResponse({'error': 'feedback must be 1 or -1'}, status=400)
        msg = ChatMessage.objects.filter(id=msg_id, user=request.user).first()
        if not msg:
            return JsonResponse({'error': 'not found'}, status=404)
        msg.feedback = feedback
        msg.save(update_fields=['feedback'])
        return JsonResponse({'status': 'ok'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'bad json'}, status=400)




# =========== ЗАДАНИЯ 1-3 ================================================
@login_required
def generate_text_analysis(request):
    """Генерация задания 1-3 (анализ текста)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        # Получаем случайный активный МИКРОтекст (задания 1–3)
        tasks = TextAnalysisTask.objects.filter(is_active=True, task_type='1_3')
        if not tasks:
            return JsonResponse({'error': 'Нет доступных текстов'}, status=404)
        
        task = random.choice(tasks)
        
        # Получаем вопросы в правильном порядке (1, 2, 3)
        questions = task.questions.all().order_by('question_number')
        if questions.count() < 3:
            return JsonResponse({'error': 'Не все вопросы добавлены к тексту'}, status=404)
        
        # Подготавливаем данные для шаблона
        context = {
            'text_task': task,
            'questions': [],
            'exercise_id': f'text_analysis_{task.id}',
        }
        
        for question in questions:
            question_data = {
                'number': question.question_number,
                'text': question.question_text,
                'type': question.question_type,
                'correct_answer': question.correct_answer,
            }
            
            if question.question_type in ['multiple_choice', 'text_characteristics']:
                # Для вопросов 2 и 3 добавляем варианты
                options = question.options.all().order_by('option_number')
                question_data['options'] = [
                    {
                        'number': opt.option_number,
                        'text': opt.option_text,
                        'is_correct': opt.is_correct,
                    }
                    for opt in options
                ]
            
            context['questions'].append(question_data)
        
        # Сохраняем в сессию для проверки
        request.session['current_text_analysis'] = {
            'task_id': task.id,
            'correct_answers': {
                str(q.question_number): q.correct_answer
                for q in questions
            }
        }
        
        # Генерируем HTML
        html = render_to_string('text_analysis_snippet.html', context)
        return JsonResponse({'html': html})
        
    except Exception as e:
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)


@login_required
def check_text_analysis(request):
    """Проверка ответов на задания 1-3"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_answers = data.get('answers', {})
        
        # Получаем правильные ответы из сессии
        session_data = request.session.get('current_text_analysis')
        if not session_data:
            return JsonResponse({'error': 'Сессия устарела'}, status=400)
        
        correct_answers = session_data['correct_answers']
        
        results = {}
        total_correct = 0
        
        for q_num in ['1', '2', '3']:
            raw_user_answer = user_answers.get(q_num, '')
            correct_answer_raw = correct_answers.get(q_num, '')
            
            # 1. НОРМАЛИЗАЦИЯ ОТВЕТА ПОЛЬЗОВАТЕЛЯ
            if isinstance(raw_user_answer, list):
                # Для чекбоксов (вопросы 2 и 3): сортируем и объединяем в строку 
                # (чтобы ["3", "1"] и ["1", "3"] превращались в одинаковую строку "13")
                user_answer = ''.join(sorted([str(x).strip() for x in raw_user_answer]))
            else:
                # Для текстового поля (вопрос 1)
                user_answer = str(raw_user_answer).strip().lower()
            
            # 2. ПРОВЕРКА
            is_correct = False
            if q_num == '1':
                # Вопрос 1: проверяем вхождение в список допустимых вариантов (разделенных через /)
                correct_variants = [v.strip().lower() for v in str(correct_answer_raw).split('/')]
                is_correct = user_answer in correct_variants
            else:
                # Вопросы 2 и 3: сравниваем отсортированные строки ("134" == "134")
                correct_sorted = ''.join(sorted(str(correct_answer_raw).strip()))
                is_correct = user_answer == correct_sorted
            
            results[q_num] = {
                'is_correct': is_correct,
                'correct_answer': str(correct_answer_raw).strip(),
                'user_answer': raw_user_answer, # Возвращаем исходный формат для отображения в JS
            }
            
            if is_correct:
                total_correct += 1
        
        return JsonResponse({
            'results': results,
            'total_correct': total_correct,
            'total_questions': 3,
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Ошибка проверки: {str(e)}'}, status=500)


# =========== ЗАДАНИЯ 23-24 ===============================================

@login_required
def generate_text_analysis_23_24(request):
    """Генерация заданий 23-24"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        # Берем активные МАКРОтексты (задания 23–26)
        tasks = TextAnalysisTask.objects.filter(is_active=True, task_type='23_26')
        
        if not tasks:
            return JsonResponse({'error': 'Нет доступных текстов'}, status=404)
        
        # Для теста - берем первый или случайный
        # task = tasks.first()  # для теста
        task = random.choice(tasks)  # для продакшена
        
        # Ищем вопросы с номерами 23 и 24
        questions = task.questions.filter(
            question_number__in=[23, 24]
        ).order_by('question_number')
        
        if questions.count() < 2:
            # Если нет вопросов 23-24, показываем заглушку
            return JsonResponse({
                'html': '''
                <div class="text-analysis-exercise" data-exercise-id="text_analysis_23_24_placeholder">
                    <div class="text-content" style="white-space: pre-wrap; margin-bottom: 20px;">
                        Текст для заданий 23-24 пока не добавлен.
                        Добавьте текст через админку Django с вопросами 23 и 24.
                    </div>
                    <div class="questions">
                        <p>Для добавления:</p>
                        <ol>
                            <li>Зайдите в админку Django</li>
                            <li>Создайте "Текст для анализа"</li>
                            <li>Добавьте вопросы с номерами 23 и 24</li>
                            <li>Добавьте варианты ответов для каждого вопроса</li>
                        </ol>
                    </div>
                </div>
                '''
            })
        
        # Тот же контекст, что и для 1-3
        context = {
            'text_task': task,
            'questions': [],
            'exercise_id': f'text_analysis_23_24_{task.id}',
        }
        
        for question in questions:
            question_data = {
                'number': question.question_number,
                'text': question.question_text,
                'type': question.question_type,
                'correct_answer': question.correct_answer,
            }
            
            if question.question_type in ['multiple_choice', 'text_characteristics']:
                options = question.options.all().order_by('option_number')
                question_data['options'] = [
                    {
                        'number': opt.option_number,
                        'text': opt.option_text,
                        'is_correct': opt.is_correct,
                    }
                    for opt in options
                ]
            
            context['questions'].append(question_data)
        
        # Сохраняем в сессию
        request.session['current_text_analysis_23_24'] = {
            'task_id': task.id,
            'correct_answers': {
                str(q.question_number): q.correct_answer
                for q in questions
            }
        }
        
        html = render_to_string('text_analysis_snippet.html', context)
        return JsonResponse({'html': html})
        
    except Exception as e:
        logger.error(f"Ошибка в generate_text_analysis_23_24: {e}")
        return JsonResponse({'error': f'Ошибка генерации: {str(e)}'}, status=500)


@login_required
def check_text_analysis_23_24(request):
    """Проверка ответов на задания 23-24"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_answers = data.get('answers', {})
        
        session_data = request.session.get('current_text_analysis_23_24')
        if not session_data:
            return JsonResponse({'error': 'Сессия устарела'}, status=400)
        
        correct_answers = session_data['correct_answers']
        
        results = {}
        total_correct = 0
        
        for q_num in ['23', '24']:
            user_answer = user_answers.get(q_num, '').strip()
            correct_answer = correct_answers.get(q_num, '').strip()
            
            user_sorted = ''.join(sorted(user_answer))
            correct_sorted = ''.join(sorted(correct_answer))
            is_correct = user_sorted == correct_sorted
            
            results[q_num] = {
                'is_correct': is_correct,
                'correct_answer': correct_answer,
                'user_answer': user_answer,
            }
            
            if is_correct:
                total_correct += 1
        
        return JsonResponse({
            'results': results,
            'total_correct': total_correct,
            'total_questions': 2,
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Ошибка проверки: {str(e)}'}, status=500)



# =========== ЗАДАНИЯ 25-26 ===============================================
def normalize_free_text(s):
    """Нормализация текста: нижний регистр, один пробел"""
    return re.sub(r'\s+', ' ', s.strip().lower())

def normalize_numbers_only(s):
    """Оставить только цифры из строки"""
    return re.sub(r'\D', '', s.strip())

@login_required
def generate_text_analysis_23_26(request):
    """Генерация заданий 23–26 на основе TextAnalysisTask"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        tasks = TextAnalysisTask.objects.filter(is_active=True, task_type='23_26')
        if not tasks.exists():
            return JsonResponse({'error': 'Нет активных текстов для анализа'}, status=404)

        task = random.choice(tasks)
        questions = task.questions.filter(
            question_number__in=[23, 24, 25, 26]
        ).order_by('question_number')

        if not questions.exists():
            return JsonResponse({
                'html': '<p>Для этого текста не заданы вопросы 23–26.</p>'
            })

        context = {
            'text_task': task,
            'questions': [],
            'exercise_id': f'text_analysis_23_26_{task.id}',
            'task_range': '23-26',
        }

        for q in questions:
            q_data = {
                'number': q.question_number,
                'text': escape(q.question_text),
                'type': q.question_type,
                'correct_answer': q.correct_answer,
            }
            if q.question_type in ['multiple_choice', 'text_characteristics']:
                q_data['options'] = [
                    {
                        'number': opt.option_number,
                        'text': escape(opt.option_text),
                    }
                    for opt in q.options.all().order_by('option_number')
                ]
            context['questions'].append(q_data)

        # Сохраняем правильные ответы в сессию
        request.session['current_text_analysis_23_26'] = {
            'task_id': task.id,
            'correct_answers': {
                str(q.question_number): q.correct_answer for q in questions
            }
        }

        html = render_to_string('text_analysis_snippet.html', context)
        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка в generate_text_analysis_23_26: {e}")
        return JsonResponse({'error': f'Ошибка генерации: {str(e)}'}, status=500)


@login_required
def check_text_analysis_23_26(request):
    """Проверка ответов по заданиям 23–26"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        user_answers = data.get('answers', {})
        session = request.session.get('current_text_analysis_23_26')
        if not session:
            return JsonResponse({'error': 'Сессия устарела. Перезагрузите задание.'}, status=400)

        correct = session['correct_answers']
        results = {}
        total_correct = 0
        total_questions = len(correct)

        for q_num_str, correct_ans in correct.items():
            q_num = int(q_num_str)
            user_ans = user_answers.get(q_num_str, '').strip()

            if q_num in (23, 24):
                # Чекбоксы: сравниваем отсортированные цифры
                ua_clean = normalize_numbers_only(user_ans)
                ca_clean = normalize_numbers_only(correct_ans)
                ua_sorted = ''.join(sorted(ua_clean))
                ca_sorted = ''.join(sorted(ca_clean))
                is_correct = ua_sorted == ca_sorted

            elif q_num == 25:
                # Фразеологизм: сравнение с вариантами через |
                user_norm = normalize_free_text(user_ans)
                correct_variants = [normalize_free_text(v) for v in correct_ans.split('|')]
                is_correct = user_norm in correct_variants

            elif q_num == 26:
                # Номера предложений: только цифры, без сортировки!
                user_digits = normalize_numbers_only(user_ans)
                correct_variants = [normalize_numbers_only(v) for v in correct_ans.split('|')]
                is_correct = user_digits in correct_variants

            else:
                is_correct = False

            results[q_num_str] = {
                'is_correct': is_correct,
                'user_answer': user_ans,
                'correct_answer': correct_ans,
            }
            if is_correct:
                total_correct += 1

        return JsonResponse({
            'results': results,
            'total_correct': total_correct,
            'total_questions': total_questions,
        })

    except Exception as e:
        logger.error(f"Ошибка в check_text_analysis_23_26: {e}")
        return JsonResponse({'error': f'Ошибка проверки: {str(e)}'}, status=500)



# ===НА СТРАНИЦЕ ТРЕНАЖЕРОВ ЗАДАНИЕ 4: ОРФОЭПИЯ ===================================================
@login_required
def generate_orthoepy_test(request):
    """Генерирует тест по орфоэпии для тренажёра."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)

    test_type = data.get('test_type', 'main')
    grade_param = data.get('grade')
    
    filter_grade = None
    is_school_mode = False

    # 1. Логика определения класса
    if grade_param:
        try:
            filter_grade = int(grade_param)
            logger.info(f"🎯 Запрос орфоэпии: Явный класс {filter_grade}")
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Неверный формат класса: {grade_param}")
    
    # Если класс не передан явно, пробуем взять из профиля (но для кнопки 4000 это не сработает, там grade=None)
    if filter_grade is None and hasattr(request.user, 'profile'):
        # Важно: для кнопки ЕГЭ (4000) мы хотим ВСЕ слова, игнорируя профиль, 
        # если только профиль не указывает на 10-11 класс и мы хотим фильтровать только их.
        # Но обычно для ЕГЭ берут всё. Оставим как есть, но проверим режим.
        profile_grade = getattr(request.user.profile, 'grade', None)
        if profile_grade and not grade_param: 
             # Если кнопка была 4_10 или 4_11, grade_param будет. 
             # Если 4000 - grade_param None.
             pass 

    # 2. Определение режима
    # Школьный режим ТОЛЬКО если передан конкретный класс 6-9
    if filter_grade and 6 <= filter_grade <= 9:
        is_school_mode = True
        logger.info(f"✅ Активирован ШКОЛЬНЫЙ режим для {filter_grade} класса")
    else:
        # Для ЕГЭ (кнопка 4000 или классы 10-11) — берем всю базу
        filter_grade = None 
        is_school_mode = False
        logger.info("🎓 Активирован режим ЕГЭ (вся база слов, filter_grade=None)")

    # 3. Генерация теста
    try:
        # Вызываем метод модели
        test_data = OrthoepyWord.generate_test(
            num_options=5,
            correct_min=2,
            correct_max=4,
            user_grade=filter_grade,  # Для ЕГЭ здесь будет None
            test_type=test_type
        )
        
        # Проверка результата
        if not test_data:
            logger.error("❌ OrthoepyWord.generate_test вернул None")
            return JsonResponse({'error': 'Ошибка генерации: нет данных (метод вернул None)'}, status=500)
            
        if not test_data.get('variants') or len(test_data['variants']) < 5:
            count = len(test_data.get('variants', []))
            logger.error(f"❌ Недостаточно вариантов: найдено {count}, нужно минимум 5")
            msg = f'Недостаточно слов в базе для генерации теста (найдено {count}). Пополните базу.'
            return JsonResponse({'error': msg}, status=400)

        variants = test_data['variants']
        correct_answers = test_data['correct_answers']
        
        logger.info(f"✅ Тест сгенерирован успешно: {len(variants)} вариантов, {len(correct_answers)} правильных")

    except Exception as e:
        # ЛОВИМ ВСЕ ОШИБКИ И ПИШЕМ ПОДРОБНОСТИ В ЛОГ
        logger.error(f"❌ Критическая ошибка в generate_test: {e}", exc_info=True)
        return JsonResponse({'error': f'Внутренняя ошибка сервера: {str(e)}'}, status=500)

    # 4. Рендеринг шаблона
    try:
        html = render_to_string('orthoepy_test_snippet.html', {
            'variants': variants,
            'exercise_id': f'orthoepy-{test_type}',
            'user_grade': filter_grade,
            'is_school_mode': is_school_mode,
        })
    except Exception as e:
        logger.error(f"❌ Ошибка рендеринга шаблона: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка шаблона'}, status=500)

    # 5. Сохранение в сессию
    request.session['orthoepy_correct'] = correct_answers
    request.session['orthoepy_all_variants'] = variants

    return JsonResponse({
        'html': html,
        'test_type': test_type,
        'count': len(variants),
        'is_school_mode': is_school_mode,
    })


@login_required
def check_orthoepy_test(request):
    """Проверяет ответы пользователя по орфоэпии"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный формат данных.'}, status=400)

    # Получаем ответы пользователя
    selected = set(data.get('selected', []))
    
    # Получаем правильные ответы и все варианты из сессии
    correct_answers = request.session.get('orthoepy_correct', [])
    all_variants = request.session.get('orthoepy_all_variants', [])

    if not isinstance(correct_answers, list):
        correct_answers = [correct_answers]
    
    # Нормализуем правильные ответы для сравнения
    correct_set = set(_normalize_text(x) for x in correct_answers)
    
    # === ФОРМИРУЕМ РЕЗУЛЬТАТ С КЛЮЧАМИ '4-1', '4-2' ... ===
    variant_results = {}
    
    # Проходим по списку вариантов ПО ПОРЯДКУ (как они были показаны пользователю)
    for i, variant in enumerate(all_variants, 1):
        normalized_variant = _normalize_text(variant)
        
        # Проверяем, является ли этот вариант правильным
        is_correct_variant = normalized_variant in correct_set
        
        # Проверяем, выбрал ли его пользователь
        was_selected = variant in selected
        
        # ГЛАВНОЕ ИСПРАВЛЕНИЕ: ключ должен быть '4-1', '4-2', а не самим словом
        result_key = f'4-{i}'
        
        variant_results[result_key] = {
            'variant_text': variant,
            'is_correct': is_correct_variant,
            'was_selected': was_selected,
        }

    # === Подсчет баллов (Правило ЕГЭ: 1 балл только если ВСЁ идеально) ===
    selected_normalized = set(_normalize_text(x) for x in selected)
    is_perfect = selected_normalized == correct_set
    user_score = 1 if is_perfect else 0

    # === Возвращаем результат в структуре, которую ждет JS ===
    response_data = {
        'results': {
            '4': {
                'variant_results': variant_results,
                'score': user_score,
                'is_correct': is_perfect,
            }
        },
        'user_score': user_score,
    }
    
    return JsonResponse(response_data)

# страничка проверки всех слов орфоэпии ЕГЭ
# === Тренажёр орфоэпии: сохранение прохождений и коррекция ===

ORTHOEPY_JSON_PATH = os.path.join(
    settings.BASE_DIR, 'main', 'assistants', 'knowledge_bases', 'russian', 'orthoepy.json')


def _load_orthoepy_words():
    with open(ORTHOEPY_JSON_PATH, encoding='utf-8') as f:
        return json.load(f)


def _orthoepy_correction_data(user):
    stats = OrthoepyWordStat.objects.filter(user=user, in_correction=True).order_by('-correction_since')
    return [{
        'word_id': s.word_id,
        'word': s.word,
        'chosen_index': s.last_chosen_index,
        'correct_index': s.correct_index,
        'errors': s.errors,
        'correction_since': s.correction_since.strftime('%d.%m.%Y') if s.correction_since else '',
    } for s in stats]


def _orthoepy_attempts_data(user):
    attempts = OrthoepyAttempt.objects.filter(user=user).order_by('-created_at')[:20]
    return [{
        'date': a.created_at.strftime('%d.%m.%Y %H:%M'),
        'chosen': a.chosen_count,
        'correct': a.correct_count,
    } for a in attempts]


@login_required
def orthoepy_trening(request):
    words = _load_orthoepy_words()
    return render(request, 'orthoepy_trening.html', {
        'words_data': json.dumps(words, ensure_ascii=False),
        'correction_data': _orthoepy_correction_data(request.user),
        'attempts_data': _orthoepy_attempts_data(request.user),
    })


@login_required
def check_orthoepy_trening(request):
    """Сохраняет прохождение, обновляет коррекцию (сервер сам проверяет ответы)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'bad json'}, status=400)

    choices = data.get('choices') or {}
    if not choices:
        return JsonResponse({'status': 'empty', 'message': 'Отметьте ударение хотя бы в одном слове.'})

    words_by_id = {w['id']: w for w in _load_orthoepy_words()}
    now = timezone.now()
    results = []
    resolved = []
    correct_count = 0

    with transaction.atomic():
        attempt = OrthoepyAttempt.objects.create(
            user=request.user,
            total_words=len(words_by_id),
            chosen_count=len(choices),
        )

        for wid_raw, chosen_raw in choices.items():
            try:
                wid, chosen = int(wid_raw), int(chosen_raw)
            except (TypeError, ValueError):
                continue
            ref = words_by_id.get(wid)
            if ref is None:
                continue

            is_correct = (chosen == ref['correct_index'])
            if is_correct:
                correct_count += 1

            OrthoepyAttemptWord.objects.create(
                attempt=attempt, word_id=wid, word=ref['word'],
                chosen_index=chosen, correct_index=ref['correct_index'],
                is_correct=is_correct,
            )
            results.append({
                'word_id': wid, 'word': ref['word'],
                'chosen_index': chosen, 'correct_index': ref['correct_index'],
                'is_correct': is_correct,
            })

            stat, _ = OrthoepyWordStat.objects.get_or_create(
                user=request.user, word_id=wid,
                defaults={'word': ref['word'], 'correct_index': ref['correct_index']},
            )
            stat.attempts += 1
            stat.last_seen = now
            stat.last_result = is_correct
            stat.last_chosen_index = chosen
            stat.correct_index = ref['correct_index']

            if is_correct:
                if stat.in_correction:
                    resolved.append({'word': ref['word'], 'correct_index': ref['correct_index']})
                stat.in_correction = False
                stat.correction_since = None
            else:
                stat.errors += 1
                if not stat.in_correction:
                    stat.in_correction = True
                    stat.correction_since = now.date()
            stat.save()

        attempt.correct_count = correct_count
        attempt.save(update_fields=['correct_count'])

    return JsonResponse({
        'status': 'ok',
        'summary': {
            'total_words': len(words_by_id),
            'chosen_count': len(choices),
            'correct_count': correct_count,
        },
        'results': results,
        'correction': _orthoepy_correction_data(request.user),   # актуальный список с сервера
        'resolved': resolved,
        'attempts': _orthoepy_attempts_data(request.user),
    })

# ======= ЗАДАНИЕ 5 ===================================================
@login_required
def generate_task_paponim_test_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        # 1. Получаем все активные ошибочные предложения (для выбора одного)
        erroneous_qs = TaskPaponim.objects.filter(
            is_active=True,
            is_for_quiz=True,
            correct_word__gt=''
        )
        if not erroneous_qs.exists():
            return JsonResponse({'error': 'Нет активных заданий с ошибками'}, status=400)

        # 2. Выбираем ОДНО случайное ошибочное
        erroneous = erroneous_qs.order_by('?').first()

        # 3. Исключаем предложения с тем же корнем
        excluded_roots = [erroneous.root] if erroneous.root else []

        correct_qs = TaskPaponim.objects.filter(
            is_active=True,
            is_for_quiz=True,
            correct_word__exact=''
        )
        if excluded_roots:
            correct_qs = correct_qs.exclude(root__in=excluded_roots)

        correct_list = list(correct_qs.order_by('?')[:4])
        if len(correct_list) < 4:
            return JsonResponse({
                'error': f'Недостаточно корректных предложений (исключены корни: {excluded_roots})'
            }, status=400)

        # 4. Формируем тест
        all_sentences = [erroneous] + correct_list
        random.shuffle(all_sentences)

        # 5. Сохраняем в сессии
        erroneous_index = next(i for i, s in enumerate(all_sentences) if s.has_error)
        request.session['task_paponim_test'] = {
            'correct_word': erroneous.correct_word.lower().strip(),
            'erroneous_index': erroneous_index
        }

        html = render_to_string('task_paponim_snippet.html', {
            'sentences': [{'text': s.text} for s in all_sentences]
        })
        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка задания 5: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка генерации'}, status=500)


@login_required
def check_task_paponim_test_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        user_word = data.get('answer', '').lower().strip()
        session = request.session.get('task_paponim_test', {})

        correct_word = session.get('correct_word', '')
        is_correct = user_word == correct_word

        return JsonResponse({
            'is_correct': is_correct,
            'correct': correct_word.upper(),
            'score': 1 if is_correct else 0
        })
    except Exception as e:
        logger.error(f"Ошибка проверки задания 5: {e}")
        return JsonResponse({'error': 'Ошибка проверки'}, status=400)


# ======= ЗАДАНИЕ 6 ===================================================
@login_required
def generate_task_wordok_test_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        # Случайно выбираем тип: 6100 или 6200
        task_type = random.choice(['6100', '6200'])

        # Берём случайный пример нужного типа
        example = WordOk.objects.filter(
            task_type=task_type,
            is_active=True,
            is_for_quiz=True
        ).order_by('?').first()

        if not example:
            return JsonResponse({
                'error': f'Нет активных примеров для типа {task_type}'
            }, status=400)

        # Определяем инструкцию
        if task_type == '6100':
            instruction = "Отредактируйте предложение: исправьте лексическую ошибку, ИСКЛЮЧИВ лишнее слово. Выпишите это слово."
        else:
            instruction = "Отредактируйте предложение: исправьте лексическую ошибку, ЗАМЕНИВ употреблённое неверно слово. Запишите подобранное слово."

        # Сохраняем в сессии
        request.session['task_wordok_test'] = {
            'correct_words': example.get_correct_words(),
            'task_type': task_type
        }

        html = render_to_string('task_wordok_snippet.html', {
            'instruction': instruction,
            'text': example.text
        })
        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка задания 6: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка генерации'}, status=500)


# views.py
@login_required
def check_task_wordok_test_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        user_word = data.get('answer', '').strip().lower()
        session = request.session.get('task_wordok_test', {})

        correct_words = session.get('correct_words', [])
        is_correct = user_word in correct_words

        return JsonResponse({
            'is_correct': is_correct,
            'correct': ' / '.join(correct_words).upper(),
            'score': 1 if is_correct else 0
        })
    except Exception as e:
        logger.error(f"Ошибка проверки задания 6: {e}")
        return JsonResponse({'error': 'Ошибка проверки'}, status=400)
    

# ======= ЗАДАНИЕ 7 ===================================================
@login_required
def generate_correction_test_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    user_grade = getattr(request.user.profile, 'grade', None)
    test_data = CorrectionExercise.generate_correction_test(user_grade=user_grade)
    
    if not test_data:
        return JsonResponse({'error': 'Недостаточно данных'}, status=400)
    
    # Ищем объект упражнения для получения explanation
    wrong_item = CorrectionExercise.objects.filter(
        incorrect_text=test_data['incorrect_word'],
        correct_text=test_data['correct_answer']
    ).first()
    
    # Сохраняем explanation вместо correct_answer
    explanation = wrong_item.explanation.lower().strip() if wrong_item else ''
    correct_for_check = explanation or test_data['correct_answer'].lower().strip()
    
    request.session['correction_test'] = {
        'correct_answer': correct_for_check,  # ← теперь здесь explanation
        'exercise_id': test_data['exercise_id'],
        'incorrect_word': test_data['incorrect_word'].lower().strip(),
    }
    
    html = render_to_string('correction_test_snippet.html', {
        'words': test_data['words'],
    })
    return JsonResponse({'html': html})



@login_required
def check_correction_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    data = json.loads(request.body)
    user_answer = data.get('answer', '').lower().strip()
    test = request.session.get('correction_test', {})
    correct = test.get('correct_answer', '')
    is_correct = user_answer == correct
    return JsonResponse({
        'is_correct': is_correct,
        'correct': test.get('correct_answer', '').upper(),
        'score': 1 if is_correct else 0
    })


# ======= ЗАДАНИЕ 8 ===================================================

@login_required
def generate_task_eight_test_view(request):
    """
    Генерирует задание 8: случайные 5 типов ошибок из доступных,
    5 предложений с ошибками + 4 без ошибок, перемешанные.
    Сохраняет answer_key в сессии в новой структуре.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    try:
        import random
        
        # Импортируем модели
        from .models import TaskGrammaticEight, TaskGrammaticEightExample
        
        # 1. Выбираем 5 случайных активных типа ошибок
        all_types = list(TaskGrammaticEight.objects.filter(is_active=True))
        if len(all_types) < 5:
            return JsonResponse({'error': 'Недостаточно активных типов ошибок (нужно 5)'}, status=400)
        
        selected_types = random.sample(all_types, 5)
        selected_ids = [t.id for t in selected_types]

        # 2. Базовый queryset примеров
        examples_qs = TaskGrammaticEightExample.objects.filter(is_active=True)
        
        # 3. Примеры с ошибками — только для выбранных типов
        erroneous_qs = examples_qs.filter(has_error=True, error_type__id__in=selected_ids)
        
        # Собираем по одному примеру на каждый тип ошибки
        selected_erroneous = []
        for t_id in selected_ids:
            example = erroneous_qs.filter(error_type_id=t_id).first()
            if not example:
                return JsonResponse({'error': f'Не найдено примера для типа ошибки {t_id}'}, status=400)
            selected_erroneous.append(example)

        # 4. Примеры без ошибок
        correct_examples = list(examples_qs.filter(has_error=False))
        if len(correct_examples) < 4:
            return JsonResponse({'error': 'Недостаточно примеров без ошибок (нужно 4)'}, status=400)
            
        selected_correct = random.sample(correct_examples, 4)

        # 5. Перемешиваем
        all_selected = selected_erroneous + selected_correct
        random.shuffle(all_selected)

        # 6. Назначаем буквы А–Д
        letters = ['А', 'Б', 'В', 'Г', 'Д']
        type_to_letter = {selected_ids[i]: letters[i] for i in range(5)}

        # 7. Формируем данные для отображения
        sentences_data = []
        for i, ex in enumerate(all_selected, 1):
            sentences_data.append({
                'id': ex.id,
                'text': ex.text,
                'position': i  # добавляем позицию в списке
            })

        # 8. Формируем правильные ответы (новая структура: {'A': '1', 'B': '2', ...})
        correct_answers_new = {}
        # Также сохраняем старую структуру для совместимости
        correct_answers_old = {}
        
        for i, ex in enumerate(all_selected, 1):
            if ex.has_error and ex.error_type_id in type_to_letter:
                error_letter = type_to_letter[ex.error_type_id]
                # Новая структура для проверки: буква -> номер предложения
                correct_answers_new[error_letter] = str(i)
                # Старая структура для совместимости: id примера -> буква
                correct_answers_old[str(ex.id)] = error_letter
            else:
                correct_answers_old[str(ex.id)] = None

        error_type_names = {
            type_to_letter[t_id]: TaskGrammaticEight.objects.get(id=t_id).get_id_display()
            for t_id in selected_ids
        }

        # 9. Сохраняем в сессии
        request.session['task_eight_test'] = {
            'new_structure': correct_answers_new,  # {'A': '1', 'B': '2', ...}
            'old_structure': correct_answers_old,  # {'id1': 'A', 'id2': None, ...}
            'sentences_positions': {str(ex.id): i for i, ex in enumerate(all_selected, 1)}
        }

        # 10. Генерируем HTML с новой структурой
        html = render_to_string('task_grammatic_eight.html', {
            'sentences': sentences_data,
            'error_type_names': error_type_names,
        })

        return JsonResponse({'html': html})

    except Exception as e:
        import traceback
        logger.error(f"Ошибка: {str(e)}\n{traceback.format_exc()}")
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


@login_required
def check_task_eight_test(request):
    """
    Проверяет ответы ученика по заданию 8.
    Новая система баллов:
    - 5 правильных = 2 балла
    - 3-4 правильных = 1 балл
    - 0-2 правильных = 0 баллов
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    try:
        data = json.loads(request.body)
        user_answers = data.get('answers', {})
        if not isinstance(user_answers, dict):
            raise ValueError("answers must be a dict")
        
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Некорректный формат данных'}, status=400)

    # Получаем эталон из сессии
    session_data = request.session.get('task_eight_test')
    if not session_data or not isinstance(session_data, dict):
        return JsonResponse({'error': 'Тест не найден. Обновите страницу.'}, status=400)

    correct_answers = session_data.get('new_structure', {})
    if not correct_answers:
        return JsonResponse({'score': 0})

    # Проверяем ответы и собираем детали
    correct_count = 0
    details = {}
    
    for letter in ['А', 'Б', 'В', 'Г', 'Д']:
        user_answer = user_answers.get(letter, '-')
        correct_answer = correct_answers.get(letter, '-')
        
        is_correct = user_answer == correct_answer
        if is_correct:
            correct_count += 1
            
        details[letter] = {
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct
        }

    # Новая система баллов
    if correct_count == 5:
        score = 2
    elif correct_count >= 3:  # 3 или 4 правильных
        score = 1
    else:  # 0, 1 или 2 правильных
        score = 0

    return JsonResponse({
        'score': score,
        'correct_count': correct_count,
        'details': details,
        'total': 5
    })

# ======= ЗАДАНИЕ 22 ===================================================
@login_required
def generate_task_twotwo_test_view(request):
    """Генерирует задание 22: 5 примеров + 9 средств выразительности"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    try:
        # 1. Получаем активные средства выразительности
        all_types = list(TaskGrammaticTwoTwo.objects.filter(is_active=True))
        if len(all_types) < 5:
            return JsonResponse({
                'error': 'Недостаточно активных средств выразительности (нужно минимум 5)'
            }, status=400)
        
        # 2. Выбираем 5 уникальных типов
        selected_types = []
        while len(selected_types) < 5:
            device = random.choice(all_types)
            if device not in selected_types:
                # Проверяем наличие примеров
                if TaskGrammaticTwoTwoExample.objects.filter(
                    device_type=device, 
                    is_active=True
                ).exists():
                    selected_types.append(device)
        
        # 3. Выбираем уникальные примеры
        examples_qs = TaskGrammaticTwoTwoExample.objects.filter(is_active=True)
        selected_examples = []
        used_example_ids = set()
        
        for t in selected_types:
            type_examples = list(examples_qs.filter(device_type=t).exclude(id__in=used_example_ids))
            if not type_examples:
                type_examples = list(examples_qs.exclude(id__in=used_example_ids))
            if not type_examples:
                used_example_ids.clear()
                type_examples = list(examples_qs.filter(device_type=t))
            
            example = random.choice(type_examples)
            selected_examples.append(example)
            used_example_ids.add(example.id)

        # 4. Добавляем еще 4 случайных средства
        remaining_types = [t for t in all_types if t not in selected_types]
        if len(remaining_types) >= 4:
            extra_types = random.sample(remaining_types, 4)
        else:
            extra_types = random.sample(all_types, 4)
        
        all_devices = selected_types + extra_types
        
        # Убираем дубликаты в правой колонке
        seen_ids = set()
        unique_devices = []
        for device in all_devices:
            if device.id not in seen_ids:
                seen_ids.add(device.id)
                unique_devices.append(device)
        
        all_devices = unique_devices
        random.shuffle(all_devices)

        # 5. Формируем данные и правильные ответы
        sentences_data = []
        correct_answers = {}
        letters = ['А', 'Б', 'В', 'Г', 'Д']
        
        for i, ex in enumerate(selected_examples):
            sentences_data.append({
                'letter': letters[i],
                'text': ex.text,
                'author': ex.author or ''
            })
            
            # Находим правильный индекс
            for idx, device in enumerate(all_devices, 1):
                if device.id == ex.device_type_id:
                    correct_answers[letters[i]] = str(idx)
                    break

        # Формируем названия как список
        device_names_list = []
        for i, device in enumerate(all_devices, 1):
            device_names_list.append((str(i), device.get_id_display()))

        # Сохраняем в сессии
        request.session['task_twotwo_test'] = {
            'correct_answers': correct_answers,
            'device_names_list': device_names_list,
            'all_devices': [d.id for d in all_devices]
        }

        # Генерируем HTML С кнопкой проверки
        html = render_to_string('task_grammatic_twotwo_snippet.html', {
            'sentences': sentences_data,
            'device_names_list': device_names_list,
            'show_check_button': True  # ← TRUE для тренажёров
        })

        return JsonResponse({'html': html})
        
    except Exception as e:
        logger.error(f"Ошибка в задании 22: {str(e)}")
        return JsonResponse({
            'error': 'Ошибка генерации теста'
        }, status=500)

@login_required
def check_task_twotwo_test(request):
    """Проверяет ответы ученика по заданию 22."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Метод не поддерживается'}, status=405)

    try:
        data = json.loads(request.body)
        user_answers = data.get('answers', {})
        
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Некорректный формат данных'}, status=400)

    # Получаем эталон из сессии
    session_data = request.session.get('task_twotwo_test')
    if not session_data:
        return JsonResponse({'error': 'Тест не найден. Обновите страницу.'}, status=400)

    correct_answers = session_data.get('correct_answers', {})
    if not correct_answers or len(correct_answers) != 5:
        return JsonResponse({'score': 0})

    # Проверяем ответы
    correct_count = 0
    details = {}
    
    for letter in ['А', 'Б', 'В', 'Г', 'Д']:
        user_answer = user_answers.get(letter, '-')
        correct_answer = correct_answers.get(letter, '-')
        
        is_correct = user_answer == correct_answer
        if is_correct:
            correct_count += 1
            
        details[letter] = {
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct
        }

    # Система баллов ЕГЭ
    if correct_count == 5:
        score = 2
    elif correct_count >= 3:
        score = 1
    else:
        score = 0

    return JsonResponse({
        'score': score,
        'correct_count': correct_count,
        'details': details,
        'total': 5
    })


# ======= ДИАГНОСТИКА  =================================================

# ======= УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ ЗАДАНИЙ С КАРТИНКАМИ ========
def generate_task_with_image(punktum_id, num_sentences=1, add_numbering=True):
    """
    Минималистичная универсальная функция для заданий 16-21
    
    :param punktum_id: '1600', '1700', '2100' и т.д.
    :param num_sentences: количество предложений (5 для 16, 1 для остальных)
    :param add_numbering: True - с нумерацией, False - без
    :return: словарь с данными или None
    """
    # Берем примеры
    examples = PunktumExample.objects.filter(
        punktum__id=punktum_id,
        is_active=True
    ).order_by('?')[:num_sentences]
    
    if not examples:
        return None
    
    task_number = punktum_id[:2]  # '1600' -> '16'
    all_lines = []
    all_correct_symbols = []
    letter_groups = {}
    mask_idx = 1
    
    for ex in examples:
        masked = ex.masked_word
        exp = (ex.explanation or '').strip()
        correct = []
        
        if exp:
            parts = [p.strip() for p in exp.split(',') if p.strip()]
            correct = ['!' if p == '!' else '?' for p in parts]
        
        # Заменяем маски
        mask_count = masked.count(f'*{punktum_id}*')
        for _ in range(mask_count):
            mask_id = f"{task_number}-{mask_idx}"
            masked = masked.replace(f'*{punktum_id}*', f'*{mask_id}*', 1)
            letter_groups[mask_id] = f'punktum_{task_number}'
            mask_idx += 1
        
        # Корректировка если нужно
        if len(correct) != mask_count:
            correct = ['!'] * mask_count
        
        all_lines.append(masked)
        all_correct_symbols.extend(correct)
    
    # Определяем картинку (ДОБАВЛЯЕМ задание 21)
    image_mapping = {
        '1600': 'images/punktum_task_16.webp',
        '1700': 'images/punktum_task_17.webp',
        '1800': 'images/punktum_task_18.webp',
        '1900': 'images/punktum_task_19.webp',
        '2000': 'images/punktum_task_20.webp',
        '2100': 'images/punktum_task_21_0.webp',  # Тире
        '2101': 'images/punktum_task_21_1.webp',  # Двоеточие
        '2102': 'images/punktum_task_21_2.webp',  # Запятые
    }
    
    # Для задания 21 определяем заголовок по типу
    title_mapping = {
        '2100': '21. Кликни на смайлик, выбери подходящий номер пунктограммы для постановки ТИРЕ.',
        '2101': '21. Кликни на смайлик, выбери подходящий номер пунктограммы для постановки ДВОЕТОЧИЯ.',
        '2102': '21. Кликни на смайлик, выбери подходящий номер пунктограммы для постановки ЗАПЯТЫХ.',
    }
    
    result = {
        'lines': all_lines,
        'correct_symbols': all_correct_symbols,
        'letter_groups': letter_groups,
        'subgroup_letters': {f'punktum_{task_number}': ['!', '?']},
        'image_name': image_mapping.get(punktum_id),
        'add_numbering': add_numbering,
        'task_number': task_number,
        'punktum_id': punktum_id,
    }
    
    # Добавляем заголовок для задания 21
    if punktum_id in title_mapping:
        result['title'] = title_mapping[punktum_id]
    
    return result


def generate_starting_diagnostic(request):
    """Генерация входящей диагностической работы (задания 1–27)"""

    try:
        session_data = {}
        context = {}

        # === Задания 1-3 ===
        text_task_1_3, text_questions_1_3 = get_text_analysis_questions('1_3')
        if text_task_1_3:
            context['text_task_1_3'] = text_task_1_3
            context['text_questions_1_3'] = text_questions_1_3
            session_data['answers_1_3'] = {
                str(q.question_number): q.correct_answer for q in text_questions_1_3
            }

        # === Получаем класс пользователя ===
        # user_grade = None
        # if request.user.is_authenticated and hasattr(request.user, 'profile'):
        #     user_grade = request.user.profile.grade
        user_grade = None
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            raw = request.user.profile.grade
            if raw is not None and str(raw).strip():
                try:
                    user_grade = int(str(raw).strip())
                except (TypeError, ValueError):
                    user_grade = None
        
        # === ЗАДАНИЕ 4: ОРФОЭПИЯ ===
        try:
            test_data = OrthoepyWord.generate_test(
                num_options=5,
                correct_min=2,
                correct_max=4,
                user_grade=None,
                test_type='main'
            )
            
            if test_data and test_data.get('variants'):
                context['orthoepy_variants'] = test_data['variants']
                session_data['answer_4'] = test_data['correct_answers']
                session_data['variants_4'] = test_data['variants']
            else:
                logger.warning("⚠️ Задание 4: test_data пустой или нет variants")

        except Exception as e:
            logger.error(f"❌ Ошибка генерации задания 4: {e}")

        # === Задание 5: Паронимы ===
        try:
            erroneous_qs = TaskPaponim.objects.filter(is_active=True, correct_word__gt='')
            correct_qs = TaskPaponim.objects.filter(is_active=True, correct_word__exact='')
            if erroneous_qs.exists() and correct_qs.count() >= 4:
                erroneous = erroneous_qs.order_by('?').first()
                correct_list = list(correct_qs.order_by('?')[:4])
                all_sentences = [erroneous] + correct_list
                random.shuffle(all_sentences)
                context['paponim_sentences'] = all_sentences
                session_data['answer_5'] = erroneous.correct_word
        except Exception as e:
            logger.error(f"Ошибка генерации задания 5: {e}")

        # === Задание 6: Лексика ===
        wordok_exclude = WordOk.objects.filter(is_active=True, task_type='6100').first()
        wordok_replace = WordOk.objects.filter(is_active=True, task_type='6200').first()
        available = []
        if wordok_exclude:
            available.append(('exclude', wordok_exclude))
        if wordok_replace:
            available.append(('replace', wordok_replace))
        if available:
            task_type, wordok = random.choice(available)
            if wordok.correct_variants.strip():
                context['wordok'] = wordok
                context['wordok_task_type'] = task_type
                session_data['answer_6'] = wordok.correct_variants

        # === ЗАДАНИЕ 7: Грамматика ===
        try:
            test_data = CorrectionExercise.generate_correction_test(user_grade=None)
            
            if test_data and test_data.get('words'):
                context['task7_phrases'] = test_data['words']
                context['task7_instruction'] = "В одном из выделенных ниже слов допущена грамматическая ошибка. Исправьте ошибку и запишите слово правильно."
                
                wrong_item = CorrectionExercise.objects.filter(
                    incorrect_text=test_data['incorrect_word'],
                    correct_text=test_data['correct_answer']
                ).first()
                
                if wrong_item and wrong_item.explanation:
                    session_data['answer_7'] = wrong_item.explanation.lower().strip()
                else:
                    session_data['answer_7'] = test_data['correct_answer'].lower().strip()
                    
                logger.info(f"✅ Задание 7: {len(test_data['words'])} вариантов")
            else:
                logger.warning("⚠️ Задание 7: тест не сгенерирован (нет данных)")
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации задания 7: {e}", exc_info=True)

        # === ЗАДАНИЕ 8: Грамматические ошибки ===
        try:
            task8_data = generate_task8_for_diagnostic()
            
            if task8_data and task8_data.get('html'):
                context['task8_html'] = task8_data['html']
                session_data['task8_correct'] = task8_data.get('correct_answers', {})
                logger.info("✅ Задание 8 сгенерировано")
            else:
                logger.warning("⚠️ Задание 8: данные не получены")
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации задания 8: {e}", exc_info=True)

        # === ЗАДАНИЕ 9 ===
        # task9_lines = generate_task9_lines()
        # if task9_lines:
        #     context['task9_lines'] = task9_lines
        #     flat_letters = [letter for line in task9_lines for letter in line.get('expected_letters', [])]
        #     if flat_letters:
        #         session_data['task9_correct'] = flat_letters
        task9_data = generate_task9_lines()
        if task9_data.get('lines'):
            context['task9_lines'] = task9_data['lines']
            flat_letters = [
                letter
                for line in task9_data['lines']
                for letter in line.get('expected_letters', [])
            ]
            if flat_letters:
                session_data['task9_correct'] = flat_letters
            context['task9_letter_groups'] = json.dumps(task9_data.get('letter_groups', {}))
            context['task9_subgroup_letters'] = json.dumps(task9_data.get('subgroup_letters', {}))

        # === ЗАДАНИЕ 10 ===
        task10_data = generate_task10_lines()
        if task10_data['lines']:
            context['task10_lines'] = task10_data['lines']
            session_data['task10_expected_map'] = task10_data['expected_map']
            context['task10_letter_groups'] = json.dumps(task10_data['letter_groups'])
            context['task10_subgroup_letters'] = json.dumps(task10_data['subgroup_letters_map'])

        # === ЗАДАНИЕ 11 ===
        task11_data = generate_task11_lines()
        if task11_data['lines']:
            context['task11_lines'] = task11_data['lines']
            session_data['task11_correct'] = task11_data['expected_letters']
            
            # Передаем ВСЕ данные
            context['task11_letter_groups'] = json.dumps(task11_data['letter_groups'])
            context['task11_subgroup_letters'] = json.dumps(task11_data['subgroup_letters_map'])
            context['task11_subgroup_info'] = json.dumps(task11_data.get('subgroup_info', {}))

        # === ЗАДАНИЕ 12 ===
        task12_data = generate_task12_lines()
        if task12_data['lines']:
            context['task12_lines'] = task12_data['lines']
            session_data['task12_correct'] = task12_data['expected_letters']
            context['task12_letter_groups'] = json.dumps(task12_data['letter_groups'])
            context['task12_subgroup_letters'] = json.dumps(task12_data['subgroup_letters_map'])

        # === ЗАДАНИЕ 13: Слитное/раздельное НЕ ===
        task13_data = generate_task13_lines()
        if task13_data['lines']:
            context['task13_lines'] = task13_data['lines']
            session_data['task13_correct'] = task13_data['expected_letters']
            context['task13_letter_groups'] = json.dumps(task13_data['letter_groups'])
            context['task13_subgroup_letters'] = json.dumps(task13_data['subgroup_letters_map'])

        # === ЗАДАНИЕ 14 ===
        task14_data = generate_task14_lines()
        if task14_data['lines']:
            context['task14_lines'] = task14_data['lines']
            session_data['task14_correct'] = task14_data['expected_letters']
            context['task14_letter_groups'] = json.dumps(task14_data['letter_groups'])
            context['task14_subgroup_letters'] = json.dumps(task14_data['subgroup_letters_map'])
            
        # === ЗАДАНИЕ 15 ===
        task15_data = generate_task15_lines()
        if task15_data['lines']:
            context['task15_lines'] = task15_data['lines']
            session_data['task15_correct'] = task15_data['expected_letters']
            context['task15_letter_groups'] = json.dumps(task15_data['letter_groups'])
            context['task15_subgroup_letters'] = json.dumps(task15_data['subgroup_letters_map'])

        # === ЗАДАНИЕ 16: ПУНКТОГРАММА ===
        task16_data = generate_task_with_image(
            punktum_id='1600',
            num_sentences=5,      # 5 предложений для задания 16
            add_numbering=True    # с нумерацией 1), 2), 3)...
        )

        if task16_data:
            context['task16_data'] = task16_data
            session_data['task16_correct'] = task16_data['correct_symbols']
            # Для совместимости
            context['task16_lines'] = task16_data['lines']
            context['task16_letter_groups'] = json.dumps(task16_data['letter_groups'])
            context['task16_subgroup_letters'] = json.dumps(task16_data['subgroup_letters'])

        # === ЗАДАНИЕ 17: ПУНКТОГРАММА ===
        task17_data = generate_task_with_image(
            punktum_id='1700',
            num_sentences=1,      # 1 предложение для задания 17
            add_numbering=False   # без нумерации
        )

        if task17_data:
            context['task17_data'] = task17_data
            session_data['task17_correct'] = task17_data['correct_symbols']
            # Для совместимости
            context['task17_lines'] = task17_data['lines']
            context['task17_letter_groups'] = json.dumps(task17_data['letter_groups'])
            context['task17_subgroup_letters'] = json.dumps(task17_data['subgroup_letters'])

        # === ЗАДАНИЕ 18: с абзацами ===
        task18_data = generate_task18_with_paragraphs()  # Новая функция!

        if task18_data:
            context['task18_data'] = task18_data
            session_data['task18_correct'] = task18_data['correct_symbols']
            # Для совместимости
            context['task18_lines'] = task18_data['lines']
            context['task18_letter_groups'] = json.dumps(task18_data['letter_groups'])
            context['task18_subgroup_letters'] = json.dumps(task18_data['subgroup_letters'])
            # Для шаблона с абзацами
            context['task18_structured_examples'] = task18_data.get('structured_examples', [])
            context['task18_is_punktum_with_paragraphs'] = task18_data.get('is_punktum_with_paragraphs', False)

        # === ЗАДАНИЕ 19: ПУНКТОГРАММА ===
        task19_data = generate_task_with_image(
            punktum_id='1900',
            num_sentences=1,      # 1 предложение для задания 19
            add_numbering=False   # без нумерации
        )

        if task19_data:
            context['task19_data'] = task19_data
            session_data['task19_correct'] = task19_data['correct_symbols']
            # Для совместимости
            context['task19_lines'] = task19_data['lines']
            context['task19_letter_groups'] = json.dumps(task19_data['letter_groups'])
            context['task19_subgroup_letters'] = json.dumps(task19_data['subgroup_letters'])

        # === ЗАДАНИЕ 20: ПУНКТОГРАММА ===
        task20_data = generate_task_with_image(
            punktum_id='2000',
            num_sentences=1,      # 1 предложение для задания 20
            add_numbering=False   # без нумерации
        )

        if task20_data:
            context['task20_data'] = task20_data
            session_data['task20_correct'] = task20_data['correct_symbols']
            # Для совместимости
            context['task20_lines'] = task20_data['lines']
            context['task20_letter_groups'] = json.dumps(task20_data['letter_groups'])
            context['task20_subgroup_letters'] = json.dumps(task20_data['subgroup_letters'])

        # === ЗАДАНИЕ 21: ДИНАМИЧЕСКОЕ (ТИРЕ/ДВОЕТОЧИЕ/ЗАПЯТЫЕ) ===
        try:
            task21_data = generate_task21_for_diagnostic()
            
            if task21_data and task21_data.get('lines'):
                context['task21_data'] = task21_data
                session_data['task21_correct'] = task21_data.get('correct_symbols', [])
                
                # Для совместимости с JS-скриптами
                context['task21_letter_groups'] = json.dumps(task21_data.get('letter_groups', {}))
                context['task21_subgroup_letters'] = json.dumps(task21_data.get('subgroup_letters', {}))
                
                logger.info(f"✅ Задание 21: вариант {task21_data.get('variant_id', 'unknown')}, {len(task21_data.get('lines', []))} строк")
            else:
                logger.warning("⚠️ Задание 21: данные не получены")
                
        except Exception as e:
            logger.error(f"❌ Ошибка генерации задания 21: {e}", exc_info=True)


        # === ЗАДАНИЕ 22: Средства выразительности ===
        try:
            task22_data = generate_task_twotwo_for_diagnostic()
            if task22_data and task22_data.get('html'):
                context['task22_html'] = task22_data['html']
                session_data['task22_correct'] = task22_data.get('correct_answers', {})

        except Exception as e:
            logger.error(f"❌ Ошибка задания 22: {e}", exc_info=True)


        # === Задания 23–26 (текст и вопросы) ===
        text_task_23_26 = None
        text_questions_23_26 = []
        text_task_23_26, text_questions_23_26 = get_text_analysis_questions('23_26')

        if text_task_23_26 and text_questions_23_26:
            # Текст для отображения в шаблоне
            context['task23_27_text'] = text_task_23_26.text_content

            # Преобразуем QuerySet вопросов в удобный для шаблона словарь
            questions_dict = {}
            for q in text_questions_23_26:
                q_data = {
                    'text': q.question_text,
                    'type': q.question_type,
                }
                if q.question_type in ['multiple_choice', 'text_characteristics']:
                    q_data['choices'] = [
                        opt.option_text
                        for opt in q.options.all().order_by('option_number')
                    ]
                questions_dict[str(q.question_number)] = q_data

            context['task23_27_questions'] = questions_dict

            # Сохраняем правильные ответы в сессию для проверки
            session_data['answers_23_26'] = {
                str(q.question_number): q.correct_answer
                for q in text_questions_23_26
            }

        # === Сохраняем в сессию ===
        request.session['starting_diagnostic'] = session_data

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.method == 'POST'
        
        if is_ajax:
            # Если запрос из JS, отдаем только сниппет в JSON
            html = render_to_string('diagnostic_snippet.html', context, request=request)
            return JsonResponse({'html': html})
        else:
            # Если это обычный переход по ссылке (GET), отдаем ПОЛНУЮ страницу со стилями
            return render(request, 'diagnostic_full_page.html', context)

    except Exception as e:
        logger.error(f"Критическая ошибка генерации диагностики: {e}", exc_info=True)
        return render(request, 'diagnostic_full_page.html', {'error': str(e)})


    
def check_starting_diagnostic(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        # УБИРАЕМ лишние переменные
        data = json.loads(request.body)
        user_answers_dict = data.get('answers', {})
        session = request.session.get('starting_diagnostic')
        
        if not session:
            return JsonResponse({'error': 'Сессия устарела'}, status=400)

        results = {}
        total_score = 0
        max_score = 0

         # === Задания 1–3 ===
        answers_1_3 = session.get('answers_1_3', {})

        for q_num_str, correct in answers_1_3.items():
            # Получаем ответ пользователя (может быть строкой или списком)
            user_ans_raw = user_answers_dict.get(q_num_str, '')
            
            # Обрабатываем по-разному в зависимости от типа
            if isinstance(user_ans_raw, list):
                # Для чекбоксов — объединяем в строку
                user_ans = ''.join(str(x) for x in user_ans_raw)
            else:
                # Для текстовых полей — строка
                user_ans = str(user_ans_raw).strip()
            
            if not user_ans:
                continue
            
            is_correct = False
            q_num = int(q_num_str)
            
            if q_num == 1:
                # Задание 1: варианты через / 
                # Используем _normalize_text, чтобы "в связи с" == "всвязис"
                correct_variants = [v.strip() for v in correct.split('/')]
                user_normalized = _normalize_text(user_ans)
                correct_normalized = [_normalize_text(v) for v in correct_variants]
                is_correct = user_normalized in correct_normalized
            else:
                # Задания 2 и 3 (чекбоксы с цифрами)
                user_sorted = ''.join(sorted(user_ans))
                correct_sorted = ''.join(sorted(correct))
                is_correct = user_sorted == correct_sorted
            
            results[q_num_str] = {'is_correct': is_correct}
            total_score += int(is_correct)
            max_score += 1
            

        # === Задание 4: Орфоэпия ===
        if 'answer_4' in session:
            # Получаем правильные ответы и все варианты
            correct_answers = session['answer_4']  # список правильных
            all_variants = session.get('variants_4', [])  # все 5 вариантов
            
            # Получаем выбранные пользователем варианты (массив)
            user_selected = user_answers_dict.get('4', [])
            
            # Нормализуем для сравнения
            normalized_correct = set(_normalize_text(x) for x in correct_answers)
            normalized_selected = set(_normalize_text(x) for x in user_selected)
            
            # Формируем результат для КАЖДОГО варианта
            variant_results = {}
            for i, variant in enumerate(all_variants, 1):
                normalized = _normalize_text(variant)
                is_correct_variant = normalized in normalized_correct
                was_selected = normalized in normalized_selected
                
                variant_results[f'4-{i}'] = {
                    'variant_text': variant,
                    'is_correct': is_correct_variant,
                    'was_selected': was_selected,
                }
            
            # Правило ЕГЭ: 1 балл только если ВСЕ правильные выбраны и НИЧЕГО лишнего
            is_perfect = normalized_selected == normalized_correct
            
            results['4'] = {
                'is_correct': is_perfect,
                'score': 1 if is_perfect else 0,
                'variant_results': variant_results,
            }
            
            total_score += 1 if is_perfect else 0
            max_score += 1

        # === Задание 5: Паронимы ===
        if 'answer_5' in session:
            correct = session['answer_5']
            user_ans = user_answers_dict.get('5', '').strip()
            if user_ans:
                is_correct = _normalize_text(user_ans) == _normalize_text(correct)
                results['5'] = {'is_correct': is_correct}
                total_score += int(is_correct)
                max_score += 1

        # === Задание 6: Лексика ===
        if 'answer_6' in session:
            correct = session['answer_6']
            user_ans = user_answers_dict.get('6', '').strip()
            if user_ans:
                variants = [v.strip() for v in correct.split(',') if v.strip()]
                is_correct = _normalize_text(user_ans) in [_normalize_text(v) for v in variants]
                results['6'] = {'is_correct': is_correct}
                total_score += int(is_correct)
                max_score += 1

        # === Задание 7: Грамматика ===
        if 'answer_7' in session:
            correct = session['answer_7'].strip().lower()
            user_ans = user_answers_dict.get('7', '').strip().lower()
            user_words_list = user_ans.split()
            user_word = user_words_list[-1] if user_words_list else ''
            is_correct = _normalize_text(user_word) == _normalize_text(correct)
            results['7'] = {'is_correct': is_correct}
            total_score += int(is_correct)
            max_score += 1

        # === ЗАДАНИЕ 8: Грамматические ошибки ===
        task8_correct = session.get('task8_correct', {})

        if task8_correct:
            task8_correct_count = 0
            task8_details = {}
            
            letters = ['А', 'Б', 'В', 'Г', 'Д']
            for letter in letters:
                key = f"8-{letter}"
                user_answer = user_answers_dict.get(key, '-')
                correct_answer = task8_correct.get(letter, '')
                
                is_correct = (user_answer != '-' and 
                            user_answer == correct_answer)
                
                task8_details[key] = {
                    'is_correct': is_correct,
                    'user_answer': user_answer,
                    'correct_answer': correct_answer
                }
                
                if is_correct:
                    task8_correct_count += 1
            
            # Правила баллов для задания 8 (ТАК ЖЕ КАК ДЛЯ 22):
            # 5 правильных = 2 балла
            # 3-4 правильных = 1 балл
            # 0-2 правильных = 0 баллов
            if task8_correct_count == 5:
                final_score = 2
            elif task8_correct_count >= 3:  # ← ИЗМЕНИТЬ НА >= 3
                final_score = 1
            else:
                final_score = 0
            
            results['8'] = {
                'is_correct': final_score > 0,
                'score': final_score,
                'correct_count': task8_correct_count,
                'max_score': 2,
                'details': task8_details
            }
            
            # Добавляем детальные результаты для подсветки
            results.update({k: {'is_correct': v['is_correct']} 
                        for k, v in task8_details.items()})
            
            total_score += final_score
            max_score += 2  # Максимум 2 балла для задания 8

        # === ЗАДАНИЕ 9: НОВОЕ ФОРМАТИРОВАНИЕ ===
        if 'task9_correct' in session:
            
            # Получаем правильные буквы из сессии
            expected_letters = session['task9_correct']
            
            # Собираем ответы пользователя для заданий 9-1, 9-2, ..., 9-15
            user_answers_for_9 = []
            total_masks = len(expected_letters)  # Должно быть 15, но проверяем
            
            for i in range(1, total_masks + 1):
                key = f"9-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                # Нормализуем ответ: убираем пробелы, приводим к нижнему регистру
                user_answer = str(user_answer).strip().lower()
                user_answers_for_9.append(user_answer)
            
            # Проверяем каждую букву
            task9_correct_count = 0
            task9_results = {}
            
            for i in range(total_masks):
                key = f"9-{i+1}"
                user_letter = user_answers_for_9[i]
                correct_letter = expected_letters[i].lower() if i < len(expected_letters) else ''
                
                is_correct = (user_letter != "😊" and user_letter != '' and 
                             user_letter == correct_letter)
                
                task9_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task9_correct_count += 1
            
            # Определяем, сколько баллов давать за задание 9
            # Если всего 15 масок, то 1 балл за все правильные
            task9_score = 0
            if total_masks == 15:
                # 1 балл за все 15 правильных
                is_task9_all_correct = (task9_correct_count == 15)
                if is_task9_all_correct:
                    task9_score = 1
                    results['9'] = {'is_correct': True}
                else:
                    results['9'] = {'is_correct': False}
            else:
                # Альтернативная логика: частичные баллы
                # Например, 1 балл за 12+ правильных из 15
                required_for_full = min(12, total_masks)
                if task9_correct_count >= required_for_full:
                    task9_score = 1
                    results['9'] = {'is_correct': True}
                else:
                    results['9'] = {'is_correct': False}
            
            # Добавляем детальные результаты для подсветки
            results.update(task9_results)
            
            total_score += task9_score
            max_score += 1  # Задание 9 дает максимум 1 балл
            
        # === ЗАДАНИЕ 10 ===
        if 'task10_expected_map' in session:
            expected_map = session['task10_expected_map']
            
            task10_correct_count = 0
            task10_results = {}
            
            for key, correct_letter in expected_map.items():
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip().lower()
                correct_clean = str(correct_letter).strip().lower()
                
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_clean)
                
                task10_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task10_correct_count += 1
            
            # 1 балл только если все маски заполнены верно
            task10_score = 1 if task10_correct_count == len(expected_map) else 0
            results['10'] = {'is_correct': task10_score == 1}
            
            # Добавляем детальные результаты для подсветки
            results.update(task10_results)
            
            total_score += task10_score
            max_score += 1
            
        # === ЗАДАНИЕ 11 ===
        if 'task11_correct' in session:
            expected_letters = session['task11_correct']
            total_masks = len(expected_letters)
            
            task11_correct_count = 0
            task11_results = {}
            
            for i in range(1, total_masks + 1):
                key = f"11-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip()  # не lower — сравнение точное
                correct_letter = expected_letters[i - 1] if i <= len(expected_letters) else ""
                
                is_correct = (user_clean != "😊" and user_clean != "" and
                             user_clean == correct_letter)
                
                task11_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task11_correct_count += 1
            
            # 1 балл только если все маски заполнены верно
            task11_score = 1 if task11_correct_count == total_masks else 0
            results['11'] = {'is_correct': task11_score == 1}
            
            # Добавляем детальные результаты для подсветки
            results.update(task11_results)
            
            total_score += task11_score
            max_score += 1

        # === ЗАДАНИЕ 12 ===
        if 'task12_correct' in session:
            expected_letters = session['task12_correct']
            total_masks = len(expected_letters)  # Должно быть 10 (5 строк × 2 примера)
            
            task12_correct_count = 0
            task12_results = {}
            
            for i in range(1, total_masks + 1):
                key = f"12-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip().lower()
                correct_letter = expected_letters[i - 1] if i <= len(expected_letters) else ""
                
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_letter)
                
                task12_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task12_correct_count += 1
            
            # 1 балл только если все маски заполнены верно
            task12_score = 1 if task12_correct_count == total_masks else 0
            results['12'] = {'is_correct': task12_score == 1}
            
            # Добавляем детальные результаты для подсветки
            results.update(task12_results)
            
            total_score += task12_score
            max_score += 1

        # === ЗАДАНИЕ 13 ===
        if 'task13_correct' in session:
            expected_letters = session['task13_correct']
            total_masks = len(expected_letters)
            task13_correct_count = 0
            task13_results = {}
            
            for i in range(1, total_masks + 1):
                key = f"13-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip().lower()
                correct_letter = expected_letters[i - 1] if i <= len(expected_letters) else ""
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_letter)
                task13_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task13_correct_count += 1
            
            # 1 балл только если все маски заполнены верно
            task13_score = 1 if task13_correct_count == total_masks else 0
            results['13'] = {'is_correct': task13_score == 1}
            results.update(task13_results)
            total_score += task13_score
            max_score += 1

        # === ЗАДАНИЕ 14 ===
        if 'task14_correct' in session:
            expected_letters = session['task14_correct']
            total_masks = len(expected_letters)
            
            task14_correct_count = 0
            task14_results = {}
            
            for i in range(1, total_masks + 1):
                key = f"14-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip().lower()
                correct_letter = expected_letters[i - 1] if i <= len(expected_letters) else ""
                
                # Нормализация: \ → |
                if user_clean == '\\':
                    user_clean = '|'
                if correct_letter == '\\':
                    correct_letter = '|'
                
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_letter)
                
                task14_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task14_correct_count += 1
            
            # 1 балл за все правильные
            task14_score = 1 if task14_correct_count == total_masks else 0
            results['14'] = {'is_correct': task14_score == 1}
            results.update(task14_results)
            
            total_score += task14_score
            max_score += 1

        # === ЗАДАНИЕ 15 ===
        if 'task15_correct' in session:
            expected_letters = session['task15_correct']
            total_masks = len(expected_letters)
            
            task15_correct_count = 0
            task15_results = {}
            
            for i in range(1, total_masks + 1):
                key = f"15-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip().lower()
                correct_letter = expected_letters[i - 1] if i <= len(expected_letters) else ""
                
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_letter)
                
                task15_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task15_correct_count += 1
            
            # 1 балл за все правильные (в задании 15 обычно 1 балл за все маски в предложении)
            task15_score = 1 if task15_correct_count == total_masks else 0
            results['15'] = {'is_correct': task15_score == 1}
            results.update(task15_results)
            
            total_score += task15_score
            max_score += 1

        # === ЗАДАНИЕ 16: Пунктуация ===
        if 'task16_correct' in session:
            expected_symbols = session['task16_correct']
            
            task16_correct_count = 0
            task16_results = {}
            
            for i in range(1, len(expected_symbols) + 1):
                key = f"16-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip()
                
                # Нормализация
                if user_clean == ',':
                    user_clean = '!'
                elif user_clean in ['х', 'x', '?']:
                    user_clean = '?'
                
                correct_symbol = expected_symbols[i-1] if i <= len(expected_symbols) else '?'
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_symbol)
                
                task16_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task16_correct_count += 1
            
            # 1 балл за все правильные
            task16_score = 1 if task16_correct_count == len(expected_symbols) else 0
            results['16'] = {'is_correct': task16_score == 1}
            results.update(task16_results)
            
            total_score += task16_score
            max_score += 1

        # === ЗАДАНИЕ 17: Пунктуация ===
        if 'task17_correct' in session:
            expected_symbols = session['task17_correct']
            
            task17_correct_count = 0
            task17_results = {}
            
            for i in range(1, len(expected_symbols) + 1):
                key = f"17-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip()
                
                # Нормализация
                if user_clean == ',':
                    user_clean = '!'
                elif user_clean in ['х', 'x', '?']:
                    user_clean = '?'
                
                correct_symbol = expected_symbols[i-1] if i <= len(expected_symbols) else '?'
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_symbol)
                
                task17_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task17_correct_count += 1
            
            # 1 балл за все правильные
            task17_score = 1 if task17_correct_count == len(expected_symbols) else 0
            results['17'] = {'is_correct': task17_score == 1}
            results.update(task17_results)
            
            total_score += task17_score
            max_score += 1

        # === ЗАДАНИЕ 18: Пунктуация ===
        if 'task18_correct' in session:
            expected_symbols = session['task18_correct']
            
            task18_correct_count = 0
            task18_results = {}
            
            for i in range(1, len(expected_symbols) + 1):
                key = f"18-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip()
                
                # Нормализация
                if user_clean == ',':
                    user_clean = '!'
                elif user_clean in ['х', 'x', '?']:
                    user_clean = '?'
                
                correct_symbol = expected_symbols[i-1] if i <= len(expected_symbols) else '?'
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_symbol)
                
                task18_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task18_correct_count += 1
            
            # 1 балл за все правильные
            task18_score = 1 if task18_correct_count == len(expected_symbols) else 0
            results['18'] = {'is_correct': task18_score == 1}
            results.update(task18_results)
            
            total_score += task18_score
            max_score += 1

        # === ЗАДАНИЕ 19: Пунктуация ===
        if 'task19_correct' in session:
            expected_symbols = session['task19_correct']
            
            task19_correct_count = 0
            task19_results = {}
            
            for i in range(1, len(expected_symbols) + 1):
                key = f"19-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip()
                
                # Нормализация
                if user_clean == ',':
                    user_clean = '!'
                elif user_clean in ['х', 'x', '?']:
                    user_clean = '?'
                
                correct_symbol = expected_symbols[i-1] if i <= len(expected_symbols) else '?'
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_symbol)
                
                task19_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task19_correct_count += 1
            
            # 1 балл за все правильные
            task19_score = 1 if task19_correct_count == len(expected_symbols) else 0
            results['19'] = {'is_correct': task19_score == 1}
            results.update(task19_results)
            
            total_score += task19_score
            max_score += 1

        # === ЗАДАНИЕ 20: Пунктуация ===
        if 'task20_correct' in session:
            expected_symbols = session['task20_correct']
            
            task20_correct_count = 0
            task20_results = {}
            
            for i in range(1, len(expected_symbols) + 1):
                key = f"20-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip()
                
                # Нормализация
                if user_clean == ',':
                    user_clean = '!'
                elif user_clean in ['х', 'x', '?']:
                    user_clean = '?'
                
                correct_symbol = expected_symbols[i-1] if i <= len(expected_symbols) else '?'
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_symbol)
                
                task20_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task20_correct_count += 1
            
            # 1 балл за все правильные
            task20_score = 1 if task20_correct_count == len(expected_symbols) else 0
            results['20'] = {'is_correct': task20_score == 1}
            results.update(task20_results)
            
            total_score += task20_score
            max_score += 1

        # === ЗАДАНИЕ 21: Пунктуация (динамическое) ===
        if 'task21_correct' in session:
            expected_symbols = session['task21_correct']
            
            task21_correct_count = 0
            task21_results = {}
            
            for i in range(1, len(expected_symbols) + 1):
                key = f"21-{i}"
                user_answer = user_answers_dict.get(key, "😊")
                user_clean = str(user_answer).strip()
                
                # Нормализация (задание 21 использует те же символы)
                if user_clean == ',':
                    user_clean = '!'
                elif user_clean in ['х', 'x', '?']:
                    user_clean = '?'
                
                correct_symbol = expected_symbols[i-1] if i <= len(expected_symbols) else '?'
                is_correct = (user_clean != "😊" and user_clean != "" and
                            user_clean == correct_symbol)
                
                task21_results[key] = {'is_correct': is_correct}
                if is_correct:
                    task21_correct_count += 1
            
            # 1 балл за все правильные
            task21_score = 1 if task21_correct_count == len(expected_symbols) else 0
            results['21'] = {'is_correct': task21_score == 1}
            results.update(task21_results)
            
            total_score += task21_score
            max_score += 1

        # === ЗАДАНИЕ 22: Средства выразительности ===
        task22_correct = session.get('task22_correct', {})

        if task22_correct:
            task22_score = 0
            task22_details = {}
            task22_correct_count = 0
            
            letters = ['А', 'Б', 'В', 'Г', 'Д']
            for letter in letters:
                key = f"22-{letter}"
                user_answer = user_answers_dict.get(key, '-')
                correct_answer = task22_correct.get(letter, '')
                
                is_correct = (user_answer != '-' and 
                            user_answer == correct_answer)
                
                task22_details[key] = {
                    'is_correct': is_correct,
                    'user_answer': user_answer,
                    'correct_answer': correct_answer
                }
                
                if is_correct:
                    task22_correct_count += 1
            
            # Все 5 правильных = 2 балла, 3 или 4 правильных = 1 балл, 0-2 правильных = 0 баллов
            
            if task22_correct_count == 5:
                final_score = 2
            elif task22_correct_count >= 3:
                final_score = 1
            else:
                final_score = 0
            
            results['22'] = {
                'is_correct': final_score > 0,  # True если есть хоть 1 балл
                'score': final_score,
                'correct_count': task22_correct_count,
                'max_score': 2,
                'details': task22_details
            }
            
            # Добавляем детальные результаты для подсветки
            results.update({k: {'is_correct': v['is_correct']} 
                        for k, v in task22_details.items()})
            
            total_score += final_score
            max_score += 2  # Максимум 2 балла для задания 22

        # === Задания 23–26 ===
        answers_23_26 = session.get('answers_23_26', {})

        for q_num_str, correct in answers_23_26.items():
            q_num = int(q_num_str)
            
            # Получаем ответ пользователя (может быть строкой или списком)
            user_ans_raw = user_answers_dict.get(q_num_str, '')
            
            # Обрабатываем по-разному в зависимости от типа
            if isinstance(user_ans_raw, list):
                # Для чекбоксов — объединяем в строку
                user_ans = ''.join(str(x) for x in user_ans_raw)
            else:
                # Для текстовых полей — строка
                user_ans = str(user_ans_raw).strip()
            
            if not user_ans:
                continue
            
            is_correct = False
            
            if q_num in (23, 24):
                # Чекбоксы: сравниваем отсортированные цифры
                user_sorted = ''.join(sorted(user_ans))
                correct_sorted = ''.join(sorted(correct))
                is_correct = user_sorted == correct_sorted
            
            elif q_num == 25:
                # Фразеологизм: варианты через | (в тренажере используется |)
                # Но в БД у вас может быть /
                correct_variants = []
                
                # Сначала пробуем /
                if '/' in correct:
                    correct_variants = [v.strip() for v in correct.split('/')]
                # Потом пробуем |
                elif '|' in correct:
                    correct_variants = [v.strip() for v in correct.split('|')]
                else:
                    correct_variants = [correct.strip()]
                
                # Убираем пробелы для сравнения
                user_norm = user_ans.lower().replace(' ', '')
                variants_norm = [v.lower().replace(' ', '') for v in correct_variants]
                
                is_correct = user_norm in variants_norm
            
            elif q_num == 26:
                # Номера предложений: варианты через | (в тренажере)
                correct_variants = []
                if '|' in correct:
                    correct_variants = [v.strip() for v in correct.split('|')]
                elif '/' in correct:
                    correct_variants = [v.strip() for v in correct.split('/')]
                else:
                    correct_variants = [correct.strip()]
                
                # Сравниваем цифры
                is_correct = user_ans in correct_variants
            
            results[q_num_str] = {'is_correct': is_correct}
            total_score += int(is_correct)
            max_score += 1

        return JsonResponse({
            'results': results,
            'total_score': total_score,
            'max_score': max_score
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)


def get_text_analysis_questions(task_type='1_3'):
    """
    Возвращает TextAnalysisTask и вопросы для указанного типа.
    task_type: '1_3' или '23_26'
    """
    required_numbers = [1, 2, 3] if task_type == '1_3' else [23, 24, 25, 26]
    tasks = TextAnalysisTask.objects.filter(is_active=True, task_type=task_type)
    for task in tasks:
        qs = task.questions.filter(question_number__in=required_numbers)
        if qs.count() == len(required_numbers):
            return task, list(qs.order_by('question_number'))
    return None, []



# ======= Задание 4  =================================================
def get_orthoepy_example():
    """Возвращает случайный активный пример орфоэпии."""
    return OrthoepyWord.objects.filter(is_active=True).first()

# ======= Задание 8  =================================================
def generate_task8_for_diagnostic():
    """
    Генерирует задание 8 для диагностики, используя существующую логику
    """
    from .models import TaskGrammaticEightExample
    
    try:
        # Используем статический метод модели для генерации теста
        test_data = TaskGrammaticEightExample.generate_task_eight_test()
        
        if not test_data:
            logger.warning("⚠️ generate_task_eight_test вернул None")
            return None
        
        # Проверяем, что есть все необходимые данные
        if not test_data.get('sentences') or not test_data.get('error_type_names'):
            logger.warning("⚠️ В test_data нет sentences или error_type_names")
            return None
        
        # Формируем данные для шаблона
        sentences = []
        for i, item in enumerate(test_data['sentences'], 1):
            sentences.append({
                'position': str(i),
                'text': item['text']
            })
        
        # Создаем mapping: буква -> номер предложения
        correct_answers = {}
        answer_key = test_data.get('answer_key', {})  # {id_предложения: 'А' или None}
        
        # Находим для каждой буквы (А-Д) номер предложения
        for sentence_id, letter in answer_key.items():
            if letter:  # Если не None (предложение с ошибкой)
                for i, sent_item in enumerate(test_data['sentences'], 1):
                    if str(sent_item['id']) == str(sentence_id):
                        correct_answers[letter] = str(i)
                        break
        
        # Генерируем HTML
        html = render_to_string('task_grammatic_eight.html', {
            'error_type_names': test_data.get('error_type_names', {}),
            'sentences': sentences,
            'show_check_button': False  # Для диагностики не нужна кнопка
        })
        
        return {
            'html': html,
            'correct_answers': correct_answers,  # {'А': '1', 'Б': '2', ...}
            'test_data': test_data
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка в generate_task8_for_diagnostic: {e}", exc_info=True)
        return None


# ======= Задание 9 =================================================
def generate_task9_lines():
    """
    Генерирует 5 строк для задания 9 с группировкой букв.
    Возвращает: dict с 'lines', 'letter_groups', 'subgroup_letters'
    """
    from random import randint, sample, shuffle, choice
    import re
    
    # === НОВАЯ СТРУКТУРА: 5 чётких групп ===
    letter_groups_config = [
        {
            'letters': ('о', 'а', 'е', 'и', 'я', 'у', 'ю'),
            'orth_ids': ['1_11', '2_11'],
            'name': 'group1'
        },
        {
            'letters': ('о', 'а'),
            'orth_ids': ['12', '13', '26', '27', '271'],
            'name': 'group2'
        },
        {
            'letters': ('е', 'и', 'я'),
            'orth_ids': ['24'],
            'name': 'group3'
        },
        {
            'letters': ('ё', 'о'),
            'orth_ids': ['14'],
            'name': 'group4'
        },
        {
            'letters': ('и', 'ы'),
            'orth_ids': ['15'],
            'name': 'group5'
        }
    ]

    # === Шаг 1: Выбираем, сколько строк будет uniform (2–4) ===
    uniform_count = randint(2, 4)
    line_indices = list(range(len(letter_groups_config)))
    uniform_indices = set(sample(line_indices, uniform_count))

    lines = []
    flat_index = 1
    letter_groups_map = {}      # Для скрипта в шаблоне: {"9-1": "group1", ...}
    subgroup_letters_map = {}   # Для скрипта в шаблоне: {"group1": ["о","а"], ...}

    # === Шаг 2: Генерируем ровно 5 строк — по одной на каждую группу ===
    for i, group in enumerate(letter_groups_config):
        # Преобразуем orth_ids в целые числа для запроса к БД
        orth_ids = []
        for oid in group['orth_ids']:
            base_id = oid.split('_')[0] if '_' in oid else oid
            try:
                orth_ids.append(int(base_id))
            except ValueError:
                continue

        if not orth_ids:
            continue

        # Получаем примеры для этой группы
        examples_qs = OrthogramExample.objects.filter(
            orthogram_id__in=orth_ids,
            is_active=True
        ).order_by('?')[:30]

        # Собираем валидные примеры
        valid_examples = []
        for ex in examples_qs:
            correct_letter = extract_correct_letter(ex.text, ex.masked_word)
            if correct_letter and len(correct_letter) == 1:
                valid_examples.append((ex, correct_letter.lower()))

        if len(valid_examples) < 3:
            continue

        # Решаем: делать ли строку с одинаковыми буквами?
        make_uniform = i in uniform_indices
        
        if make_uniform:
            # Строка с одинаковыми буквами во всех словах
            examples_by_letter = {}
            for ex, letter in valid_examples:
                if letter not in examples_by_letter:
                    examples_by_letter[letter] = []
                examples_by_letter[letter].append(ex)
            
            selected_letter = None
            selected_examples = []
            
            for letter, ex_list in examples_by_letter.items():
                if len(ex_list) >= 3:
                    selected_letter = letter
                    selected_examples = sample(ex_list, 3)
                    break
            
            if selected_letter:
                examples = selected_examples
                letters = [selected_letter] * 3
                is_uniform = True
            else:
                # Fallback: любые 3 примера
                selected = sample(valid_examples, 3)
                examples, letters = zip(*selected)
                is_uniform = False
        else:
            # Обычная строка: разные буквы в словах
            attempts = 0
            selected = []
            while attempts < 10:
                selected = sample(valid_examples, 3)
                letters_in_line = [letter for _, letter in selected]
                if len(set(letters_in_line)) >= 2:
                    break
                attempts += 1
            
            if attempts >= 10:
                selected = sample(valid_examples, 3)
            
            examples, letters = zip(*selected)
            is_uniform = False

        # Формируем строку с масками *9-1*, *9-2* и т.д.
        parts = []
        for ex in examples:
            # ← ИСПРАВЛЕНО: заменяем ЛЮБУЮ маску *...* на *9-N*
            masked = re.sub(r'\*[^*]+\*', f'*9-{flat_index}*', ex.masked_word, count=1)
            parts.append(masked)
            
            # Заполняем letter_groups_map для frontend
            letter_groups_map[f'9-{flat_index}'] = group['name']
            flat_index += 1

        display_line = ', '.join(parts)
        lines.append({
            'examples': list(examples),
            'expected_letters': list(letters),
            'display_line': display_line,
            'available_letters': list(group['letters']),
            'group_name': group['name'],
            'is_uniform': is_uniform
        })

    # Заполняем subgroup_letters_map
    for group in letter_groups_config:
        subgroup_letters_map[group['name']] = list(group['letters'])

    # ← ИСПРАВЛЕНО: возвращаем dict с метаданными
    return {
        'lines': lines[:5],
        'letter_groups': letter_groups_map,
        'subgroup_letters': subgroup_letters_map
    }

# ======= Задание 10 =================================================
def generate_task10_lines():
    """
    Генерирует 5 строк для задания 10 ЕГЭ.
    - 2-4 строки с одинаковыми буквами во всех словах (uniform)
    - Остальные строки с разными буквами
    """
    from random import choice, sample, shuffle, randint
    from django.db.models import Q
    
    # === 1. Определяем, сколько строк будет uniform (2-4) ===
    uniform_count = randint(2, 4)
    
    # === 2. Конфигурация подгрупп ===
    SUBGROUPS = [
        {'key': 'sz', 'letters': ['з', 'с'], 'orth_ids': ['10', '11']},
        {'key': 'ao', 'letters': ['а', 'о'], 'orth_ids': ['10']},
        {'key': 'dt', 'letters': ['д', 'т'], 'orth_ids': ['10']},
        {'key': 'ыи', 'letters': ['и', 'ы'], 'orth_ids': ['28']},
        {'key': 'еи', 'letters': ['е', 'и'], 'orth_ids': ['29']},
        {'key': 'ъь', 'letters': ['ъ', 'ь', '/'], 'orth_ids': ['6']},
    ]
    
    # === 3. Загружаем примеры для каждой подгруппы ===
    all_examples = {}
    for group in SUBGROUPS:
        examples = []
        for orth_id in group['orth_ids']:
            qs = OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True
            ).order_by('?')[:50]
            
            for ex in qs:
                correct = extract_correct_letter(ex.text, ex.masked_word)
                if not correct:
                    continue
                    
                # Нормализуем букву
                if orth_id == '6':
                    letter = '/' if correct == '' else correct
                else:
                    letter = correct.lower()
                
                if letter in group['letters']:
                    examples.append((ex, letter, orth_id))
        
        if len(examples) >= 3:
            all_examples[group['key']] = examples
    
    if len(all_examples) < 2:
        raise ValueError("Недостаточно данных для задания 10")
    
    # === 4. Выбираем 5 разных подгрупп (или повторяем при нехватке) ===
    available_keys = list(all_examples.keys())
    shuffle(available_keys)
    selected_keys = (available_keys * 2)[:5]  # гарантирует 5 элементов
    
    # === 5. Определяем, какие строки будут uniform ===
    line_indices = list(range(5))
    uniform_indices = set(sample(line_indices, uniform_count))
    
    # === 6. Генерация строк ===
    lines = []
    expected_map = {}
    letter_groups_map = {}
    mask_index = 1
    
    for i, key in enumerate(selected_keys):
        examples = all_examples[key]
        is_uniform_line = i in uniform_indices
        
        if is_uniform_line:
            # === СТРОКА С ОДИНАКОВЫМИ БУКВАМИ ===
            # Группируем примеры по буквам
            by_letter = {}
            for ex, letter, orth_id in examples:
                by_letter.setdefault(letter, []).append((ex, letter, orth_id))
            
            # Ищем букву с ≥3 примерами
            chosen_letter = None
            chosen_examples = None
            for letter, lst in by_letter.items():
                if len(lst) >= 3:
                    chosen_letter = letter
                    chosen_examples = sample(lst, 3)
                    break
            
            if chosen_letter is None:
                # Fallback: берём любые 3 примера с одной буквой (повторяем первую)
                chosen_examples = sample(examples, 3)
                chosen_letter = chosen_examples[0][1]
                # Делаем все буквы одинаковыми
                chosen_examples = [(ex, chosen_letter, orth_id) for ex, _, orth_id in chosen_examples]
        else:
            # === СТРОКА С РАЗНЫМИ БУКВАМИ ===
            # Собираем примеры с разными буквами
            attempts = 0
            chosen_examples = []
            while attempts < 20 and len(chosen_examples) < 3:
                # Пробуем найти 3 примера с разными буквами
                by_letter_temp = {}
                for ex, letter, orth_id in examples:
                    by_letter_temp.setdefault(letter, []).append((ex, letter, orth_id))
                
                # Если есть минимум 2 разные буквы
                if len(by_letter_temp) >= 2:
                    # Берем по примеру из разных букв
                    different_letters = list(by_letter_temp.keys())
                    shuffle(different_letters)
                    
                    chosen_examples = []
                    for letter in different_letters[:min(3, len(different_letters))]:
                        ex_list = by_letter_temp[letter]
                        chosen_examples.append(sample(ex_list, 1)[0])
                    
                    # Если набрали меньше 3, добиваем любыми
                    while len(chosen_examples) < 3:
                        extra = sample(examples, 1)[0]
                        if extra not in chosen_examples:
                            chosen_examples.append(extra)
                    break
                attempts += 1
            
            if not chosen_examples:
                # Fallback: любые 3 примера
                chosen_examples = sample(examples, 3)
        
        # === 7. Формируем строку и сохраняем данные ===
        parts = []
        expected_letters_in_line = []
        
        for ex, letter, orth_id in chosen_examples:
            mask_id = f"10_{orth_id}-{mask_index}"
            
            # Заменяем маску
            masked = re.sub(r'\*\d+(?:_\d+)?\*', f'*{mask_id}*', ex.masked_word, count=1)
            parts.append(masked)
            
            # Сохраняем для проверки
            expected_map[mask_id] = letter
            expected_letters_in_line.append(letter)
            
            # Сохраняем группу для этой маски
            letter_groups_map[mask_id] = key
            
            mask_index += 1
        
        display_line = ', '.join(parts)
        
        # Проверяем, действительно ли строка uniform
        actual_is_uniform = len(set(expected_letters_in_line)) == 1
        
        lines.append({
            'display_line': display_line,
            'expected_letters': expected_letters_in_line,
            'is_uniform': actual_is_uniform  # Для отладки
        })
    
    # === 8. Проверяем итоговое распределение ===
    uniform_lines_count = sum(1 for line in lines if len(set(line['expected_letters'])) == 1)
    
    return {
        'lines': lines[:5],
        'expected_map': expected_map,
        'letter_groups': letter_groups_map,  # key -> 'sz', 'ao', 'dt', etc.
        
        # ДОБАВЛЯЕМ: маппинг подгруппа -> буквы для JS
        'subgroup_letters_map': {
            'sz': ['з', 'с'],
            'ao': ['а', 'о'],
            'dt': ['д', 'т'],
            'ыи': ['и', 'ы'],
            'еи': ['е', 'и'],
            'ъь': ['ъ', 'ь', '/']
        }
    }

# ======= Задание 11 =================================================
def generate_task11_lines():
    """
    Генерирует 5 строк для задания 11 (суффиксы) с гарантированным разнообразием.
    - Гарантирует минимум 3 разные подгруппы из 6 возможных
    - 2-4 строки с одинаковыми буквами
    """
    from random import choice, sample, shuffle, randint
    
    # === 1. Определяем uniform строки ===
    uniform_count = randint(2, 4)
    
    # === 2. ТОЧНЫЕ ПОДГРУППЫ ===
    SUFFIX_SUBGROUPS = [
        {'key': 'e_i_ya', 'letters': ['е', 'и', 'я'], 'orth_ids': ['31', '34', '35', '48', '60', '61', '610']},
        {'key': 'yo_o', 'letters': ['ё', 'о'], 'orth_ids': ['37']},
        {'key': 'o_y', 'letters': ['о', 'ы'], 'orth_ids': ['485']},  # Нужно проверить в БД
        {'key': 'a_o', 'letters': ['а', 'о'], 'orth_ids': ['481', '482', '483', '484']},
        {'key': 'ch_shch', 'letters': ['ч', 'щ'], 'orth_ids': ['33']},
        {'key': 'k_sk', 'letters': ['к', 'ск'], 'orth_ids': ['39']}
    ]
    
    # === 3. Загружаем примеры для КАЖДОЙ подгруппы ===
    subgroup_data = {}
    available_subgroups = []
    
    for subgroup in SUFFIX_SUBGROUPS:
        examples = []
        for orth_id in subgroup['orth_ids']:
            qs = OrthogramExample.objects.filter(
                orthogram_id=orth_id,
                is_active=True
            ).order_by('?')[:30]  # Берем больше для выборки
            
            for ex in qs:
                correct = extract_correct_letter(ex.text, ex.masked_word)
                if not correct:
                    continue
                    
                letter = correct.lower()
                # Для группы к/ск нужно обработать "ск" как одну букву
                if subgroup['key'] == 'k_sk' and letter == 'ск':
                    examples.append((ex, 'ск', orth_id, subgroup['key']))
                elif letter in subgroup['letters']:
                    examples.append((ex, letter, orth_id, subgroup['key']))
        
        if len(examples) >= 2:  # Минимум 2 примера для строки
            subgroup_data[subgroup['key']] = {
                'subgroup': subgroup,
                'examples': examples
            }
            available_subgroups.append(subgroup['key'])
    
    if len(available_subgroups) < 3:  # Нужно минимум 3 разные подгруппы
        # Fallback: используем то, что есть
        if not available_subgroups:
            return {'lines': [], 'expected_letters': [], 'letter_groups': {}}
    
    # === 4. ВЫБОР ПОДГРУПП С ГАРАНТИЕЙ РАЗНООБРАЗИЯ ===
    selected_subgroup_keys = []
    
    # Шаг 1: Выбираем минимум 3 РАЗНЫЕ подгруппы
    if len(available_subgroups) >= 3:
        # Берем 3 разные подгруппы
        different_keys = sample(available_subgroups, 3)
        selected_subgroup_keys.extend(different_keys)
    else:
        # Если меньше 3, используем все доступные
        selected_subgroup_keys.extend(available_subgroups)
    
    # Шаг 2: Добиваем до 5 строк (можно повторять, но не подряд одинаковые)
    while len(selected_subgroup_keys) < 5:
        # Выбираем подгруппу, отличную от последней выбранной
        last_key = selected_subgroup_keys[-1] if selected_subgroup_keys else None
        candidates = [k for k in available_subgroups if k != last_key]
        
        if candidates:
            selected_subgroup_keys.append(choice(candidates))
        else:
            selected_subgroup_keys.append(choice(available_subgroups))
    
    # === 5. Определяем uniform строки ===
    line_indices = list(range(5))
    uniform_indices = set(sample(line_indices, uniform_count))
    
    # === 6. Генерация строк ===
    lines = []
    expected_letters = []
    letter_groups = {}
    mask_index = 1
    
    for i, subgroup_key in enumerate(selected_subgroup_keys):
        if subgroup_key not in subgroup_data:
            continue
            
        data = subgroup_data[subgroup_key]
        examples = data['examples']
        is_uniform_line = i in uniform_indices
        
        if is_uniform_line:
            # СТРОКА С ОДИНАКОВЫМИ БУКВАМИ
            by_letter = {}
            for ex, letter, orth_id, gkey in examples:
                by_letter.setdefault(letter, []).append((ex, letter, orth_id, gkey))
            
            chosen_letter = None
            chosen_examples = None
            
            # Пытаемся найти букву с ≥2 примерами
            for letter, lst in by_letter.items():
                if len(lst) >= 2:
                    chosen_letter = letter
                    chosen_examples = sample(lst, 2)
                    break
            
            if chosen_letter is None:
                # Fallback: любые 2 примера
                chosen_examples = sample(examples, 2)
                chosen_letter = chosen_examples[0][1]
                # Делаем одинаковыми
                chosen_examples = [(ex, chosen_letter, orth_id, gkey) 
                                 for ex, _, orth_id, gkey in chosen_examples]
        else:
            # СТРОКА С РАЗНЫМИ БУКВАМИ
            attempts = 0
            chosen_examples = []
            
            while attempts < 30 and len(chosen_examples) < 2:
                by_letter_temp = {}
                for ex, letter, orth_id, gkey in examples:
                    by_letter_temp.setdefault(letter, []).append((ex, letter, orth_id, gkey))
                
                if len(by_letter_temp) >= 2:
                    # Берем 2 РАЗНЫЕ буквы
                    different_letters = list(by_letter_temp.keys())
                    shuffle(different_letters)
                    
                    chosen_examples = []
                    for letter in different_letters[:2]:
                        ex_list = by_letter_temp[letter]
                        chosen_examples.append(sample(ex_list, 1)[0])
                    break
                
                attempts += 1
            
            if not chosen_examples or len(chosen_examples) < 2:
                # Extreme fallback
                chosen_examples = sample(examples, min(2, len(examples)))
        
        # Формируем строку
        parts = []
        line_expected_letters = []
        
        for ex, letter, orth_id, gkey in chosen_examples:
            mask_id = f"11-{mask_index}"
            
            # Заменяем маску
            masked = re.sub(r'\*\d+(?:_\d+)?\*', f'*{mask_id}*', ex.masked_word, count=1)
            parts.append(masked)
            
            expected_letters.append(letter)
            line_expected_letters.append(letter)
            letter_groups[mask_id] = subgroup_key
            
            mask_index += 1
        
        display_line = ', '.join(parts)
        
        actual_is_uniform = len(set(line_expected_letters)) == 1
        
        lines.append({
            'display_line': display_line,
            'expected_letters': line_expected_letters,
            'subgroup_key': subgroup_key,
            'is_uniform': actual_is_uniform
        })
    
    # === 7. Проверяем разнообразие ===
    unique_subgroups = set([line['subgroup_key'] for line in lines])
    uniform_lines_count = sum(1 for line in lines if line['is_uniform'])

    # === 8. Подготовка данных ===
    subgroup_letters_map = {
        'e_i_ya': ['е', 'и', 'я'],
        'yo_o': ['ё', 'о'],
        'o_y': ['о', 'ы'],
        'a_o': ['а', 'о'],
        'ch_shch': ['ч', 'щ'],
        'k_sk': ['к', 'ск'],
        'full': ['е', 'и', 'я', 'а', 'о', 'ё', 'ч', 'щ', 'к', 'ск', 'ы']
    }
    
    return {
        'lines': lines[:5],
        'expected_letters': expected_letters,
        'letter_groups': letter_groups,
        'subgroup_letters_map': subgroup_letters_map
    }


# ======= Задание 12 =================================================
def generate_task12_lines():
    """
    Генерирует 5 строк для задания 12 (суффиксы причастий и глаголов).
    - 2-4 строки с одинаковыми буквами в обоих примерах
    - 5 строк, по 2 примера в каждой
    - Использует орфограммы: 25, 49, 50, 51, 511, 512, 513
    """
    
    # === 1. Определяем uniform строки ===
    uniform_count = randint(2, 4)

    # === 2. ГРУППЫ ОРФОГРАММ ДЛЯ ЗАДАНИЯ 12 ===
    # Орфограммы и их возможные буквы:
    # 25, 49: ['е', 'у', 'ю', 'и', 'а', 'я'] - суффиксы причастий и глаголов
    # 50: ['е', 'и'] - суффиксы глаголов
    # 51: ['а', 'я', 'и', 'е'] - суффиксы глаголов
    # 511, 512, 513: вариации суффиксов
    
    # Сгруппируем по буквенному составу для удобства
    ORTH_GROUPS = [
        {
            'key': 'group1',
            'letters': ['е', 'у', 'ю', 'и', 'а', 'я'],
            'orth_ids': ['25', '49'],
            'name': 'е/у/ю/и/а/я (суффиксы причастий)'
        },
        {
            'key': 'group2',
            'letters': ['е', 'и'],
            'orth_ids': ['50'],
            'name': 'е/и (суффиксы глаголов)'
        },
        {
            'key': 'group3',
            'letters': ['а', 'я', 'и', 'е'],
            'orth_ids': ['51'],
            'name': 'а/я/и/е (суффиксы глаголов)'
        },
        {
            'key': 'group4',
            'letters': ['е', 'и', 'а', 'я'],
            'orth_ids': ['512'],
            'name': 'е/и/а/я (суффиксы)'
        },
        {
            'key': 'group5',
            'letters': ['е', 'и', 'я'],
            'orth_ids': ['513'],
            'name': 'е/и/я (суффиксы)'
        }
    ]
    
    # Также можно использовать орфограмму 511, если она есть в БД
    ORTH_ALL_IDS = ['25', '49', '50', '51', '511', '512', '513']
    
    # === 3. Загружаем примеры из БД ===
    all_examples = []
    for orth_id in ORTH_ALL_IDS:
        qs = OrthogramExample.objects.filter(
            orthogram_id=orth_id,
            is_active=True
        ).order_by('?')[:30]  # Берем больше для выборки
        
        for ex in qs:
            correct = extract_correct_letter(ex.text, ex.masked_word)
            if not correct:
                continue
                
            letter = correct.lower()
            all_examples.append({
                'example': ex,
                'letter': letter,
                'orth_id': orth_id
            })
    
    if len(all_examples) < 10:  # Нужно минимум 10 примеров (5 строк × 2 примера)
        return {
            'lines': [],
            'expected_letters': [],
            'letter_groups': {},
            'subgroup_letters_map': {}
        }
    
    # === 4. Группируем примеры по буквам ===
    examples_by_letter = {}
    for item in all_examples:
        letter = item['letter']
        if letter not in examples_by_letter:
            examples_by_letter[letter] = []
        examples_by_letter[letter].append(item)
    
    # Проверяем, какие буквы имеют минимум 2 примера
    available_letters = [letter for letter, items in examples_by_letter.items() 
                        if len(items) >= 2]
    
    # === 5. Определяем uniform строки ===
    line_indices = list(range(5))
    uniform_indices = set(sample(line_indices, uniform_count))
    
    # === 6. Генерация строк ===
    lines = []
    expected_letters = []  # Плоский список для всех масок
    letter_groups = {}  # mask_id -> группа букв (для JS)
    mask_index = 1
    
    for i in range(5):  # 5 строк
        is_uniform_line = i in uniform_indices
        
        if is_uniform_line:
            # СТРОКА С ОДИНАКОВЫМИ БУКВАМИ
            # Выбираем букву, у которой есть минимум 2 примера
            suitable_letters = [letter for letter in available_letters 
                              if len(examples_by_letter.get(letter, [])) >= 2]
            
            if suitable_letters:
                chosen_letter = choice(suitable_letters)
                chosen_items = sample(examples_by_letter[chosen_letter], 2)
            else:
                # Fallback: любые 2 примера
                chosen_items = sample(all_examples, 2)
                chosen_letter = chosen_items[0]['letter']
                # Делаем одинаковыми
                chosen_items = [{
                    'example': item['example'],
                    'letter': chosen_letter,
                    'orth_id': item['orth_id']
                } for item in chosen_items]
        else:
            # СТРОКА С РАЗНЫМИ БУКВАМИ
            attempts = 0
            chosen_items = []
            
            while attempts < 30 and len(chosen_items) < 2:
                # Выбираем 2 примера с разными буквами
                temp_items = sample(all_examples, min(2, len(all_examples)))
                letters_in_line = [item['letter'] for item in temp_items]
                
                if len(set(letters_in_line)) >= 2:  # Минимум 2 разные буквы
                    chosen_items = temp_items
                    break
                
                attempts += 1
            
            if not chosen_items:
                # Extreme fallback
                chosen_items = sample(all_examples, min(2, len(all_examples)))
        
        # Формируем строку
        parts = []
        line_expected_letters = []
        
        for item in chosen_items:
            mask_id = f"12-{mask_index}"
            
            # Заменяем маску в примере
            ex = item['example']
            masked_word = ex.masked_word
            # Заменяем исходную маску на нашу
            masked = re.sub(r'\*\d+(?:_\d+)?\*', f'*{mask_id}*', masked_word, count=1)
            parts.append(masked)
            
            # Сохраняем ожидаемую букву
            expected_letters.append(item['letter'])
            line_expected_letters.append(item['letter'])
            
            # Определяем группу букв для этой маски
            # Находим к какой группе относится орфограмма
            orth_id = item['orth_id']
            group_key = 'full'  # по умолчанию
            for group in ORTH_GROUPS:
                if orth_id in group['orth_ids']:
                    group_key = group['key']
                    break
            
            letter_groups[mask_id] = group_key
            mask_index += 1
        
        display_line = ', '.join(parts)
        
        actual_is_uniform = len(set(line_expected_letters)) == 1
        
        lines.append({
            'display_line': display_line,
            'expected_letters': line_expected_letters,
            'is_uniform': actual_is_uniform
        })
    
    # === 7. Проверяем итоги ===
    uniform_lines_count = sum(1 for line in lines if line['is_uniform'])
    
    # === 8. Подготовка данных для фронтенда ===
    # Создаем маппинг групп -> буквы
    subgroup_letters_map = {}
    for group in ORTH_GROUPS:
        subgroup_letters_map[group['key']] = group['letters']
    
    # Добавляем fallback группу со всеми возможными буквами
    all_possible_letters = set()
    for group in ORTH_GROUPS:
        all_possible_letters.update(group['letters'])
    subgroup_letters_map['full'] = list(all_possible_letters)
    
    return {
        'lines': lines[:5],  # Гарантируем ровно 5 строк
        'expected_letters': expected_letters,
        'letter_groups': letter_groups,
        'subgroup_letters_map': subgroup_letters_map
    }

# ======= Задание 13 =================================================
def generate_task13_lines():
    """
    Генерирует 5 предложений для задания 13 (слитное/раздельное НЕ).
    Условия ЕГЭ: 5 строк, в каждой по 1 примеру
    2-4 строки с одинаковым написанием НЕ (все слитно или все раздельно)
    Остальные строки с разным написанием
    """
    from random import sample, randint, choice, shuffle
    
    TASK13_ORTHOGRAMS = [21, 32, 36, 46, 54, 56, 57, 58, 581, 582]
    
    # Собираем все примеры
    all_examples = []
    for orth_id in TASK13_ORTHOGRAMS:
        examples_qs = OrthogramExample.objects.filter(
            orthogram_id=orth_id,
            is_active=True
        ).order_by('?')[:30]  # Берем больше для выборки
        
        for ex in examples_qs:
            correct = extract_correct_letter(ex.text, ex.masked_word)
            # Нормализуем: пустая строка или '/' - слитное написание
            # '|' или '\' - раздельное написание
            if correct in ['|', '/', '\\', '', ' ']:
                # Приводим к двум типам: '|' (раздельное) и '' (слитное)
                normalized = '|' if correct in ['|', '\\'] else ''
                all_examples.append({
                    'example': ex,
                    'correct': normalized,
                    'orth_id': orth_id,
                    'original_correct': correct
                })
    
    if len(all_examples) < 5:
        return {'lines': [], 'expected_letters': [], 'letter_groups': {}, 'subgroup_letters_map': {'ne': ['|', '/']}}
    
    # === 1. Определяем сколько строк будет с одинаковым написанием ===
    uniform_count = randint(2, 4)
    
    # === 2. Группируем примеры по типу написания ===
    examples_by_type = {'|': [], '': []}  # | - раздельно, '' - слитно
    
    for item in all_examples:
        letter_type = item['correct']
        if letter_type in examples_by_type:
            examples_by_type[letter_type].append(item)
    
    # === 3. Выбираем тип для uniform строк ===
    # Случайно выбираем, будут ли uniform строки все раздельные или все слитные
    uniform_type = choice(['|', ''])
    
    # Если выбранного типа недостаточно примеров, берем другой
    if len(examples_by_type[uniform_type]) < uniform_count:
        uniform_type = '|' if uniform_type == '' else ''
    
    # Если все равно недостаточно, уменьшаем uniform_count
    if len(examples_by_type[uniform_type]) < uniform_count:
        uniform_count = min(uniform_count, len(examples_by_type[uniform_type]))
    
    # === 4. Выбираем примеры для uniform строк ===
    uniform_items = []
    if uniform_count > 0 and examples_by_type[uniform_type]:
        uniform_items = sample(examples_by_type[uniform_type], uniform_count)
        # Удаляем выбранные из доступных
        for item in uniform_items:
            if item in examples_by_type[uniform_type]:
                examples_by_type[uniform_type].remove(item)
    
    # === 5. Выбираем примеры для non-uniform строк ===
    non_uniform_needed = 5 - uniform_count
    
    # Собираем все оставшиеся примеры
    remaining_items = examples_by_type['|'] + examples_by_type['']
    
    # Для non-uniform строк нужно минимум 2 разных типа
    # Сначала пробуем взять примеры противоположного типа
    opposite_type = '|' if uniform_type == '' else ''
    
    non_uniform_items = []
    
    # Пытаемся набрать разнообразные примеры
    if non_uniform_needed > 0:
        # Сначала берем из противоположного типа
        if examples_by_type[opposite_type]:
            take_from_opposite = min(non_uniform_needed, len(examples_by_type[opposite_type]))
            non_uniform_items.extend(sample(examples_by_type[opposite_type], take_from_opposite))
            non_uniform_needed -= take_from_opposite
        
        # Если нужно еще, добираем из любого типа (но стараемся разнообразить)
        if non_uniform_needed > 0:
            # Собираем все оставшиеся
            all_remaining = examples_by_type['|'] + examples_by_type['']
            # Убираем уже выбранные
            all_remaining = [item for item in all_remaining if item not in non_uniform_items]
            
            if all_remaining:
                take_count = min(non_uniform_needed, len(all_remaining))
                non_uniform_items.extend(sample(all_remaining, take_count))
    
    # === 6. Объединяем все выбранные примеры ===
    all_selected = uniform_items + non_uniform_items
    
    # Если набрали меньше 5, добиваем любыми
    if len(all_selected) < 5:
        shortfall = 5 - len(all_selected)
        # Берем любые примеры, которых еще нет в списке
        remaining_all = [item for item in all_examples if item not in all_selected]
        if remaining_all:
            all_selected.extend(sample(remaining_all, min(shortfall, len(remaining_all))))
    
    # Перемешиваем строки, чтобы uniform не были сгруппированы
    shuffle(all_selected)
    
    # === 7. Формируем финальные 5 строк ===
    lines = []
    expected_letters = []
    letter_groups = {}
    mask_index = 1
    
    for i, item in enumerate(all_selected[:5]):  # Берем ровно 5
        ex = item['example']
        correct_letter = item['correct']  # '|' или ''
        original_correct = item['original_correct']
        orth_id = item['orth_id']
        
        mask_id = f"13-{mask_index}"
        
        # Заменяем маску
        masked = re.sub(rf'\*{orth_id}\*', f'*{mask_id}*', ex.masked_word, count=1)
        
        # Для отображения сохраняем оригинальный правильный символ
        display_correct = original_correct if original_correct else ''
        expected_letters.append(display_correct)
        letter_groups[mask_id] = 'ne'
        
        mask_index += 1
        
        lines.append(masked)
    
    # === 8. Проверяем итоговое распределение ===
    uniform_lines = 0
    for i in range(len(all_selected[:5])):
        item = all_selected[i]
        if item in uniform_items:
            uniform_lines += 1
    
    return {
        'lines': lines,  # 5 строк, по одному примеру в каждой
        'expected_letters': expected_letters,
        'letter_groups': letter_groups,
        'subgroup_letters_map': {
            'ne': ['|', '/']  # Варианты для выпадающего списка
        }
    }

# ======= Задание 14 =================================================
def generate_task14_lines():
    """
    Генерирует 5 предложений для задания 14 (слитное/раздельное/дефисное написание).
    Берет случайные 5 примеров из орфограммы 1400.
    """
    from random import sample
    
    # Берем 5 случайных активных примеров
    examples = OrthogramExample.objects.filter(
        orthogram_id=1400,
        is_active=True
    ).order_by('?')[:5]
    
    if len(examples) < 5:
        # Можно вернуть меньше или использовать дубли
        examples = list(examples)  # Берем что есть
    
    lines = []
    expected_letters = []
    letter_groups = {}
    mask_index = 1
    
    for ex in examples:
        # Извлекаем правильные символы из explanation или text
        explanation_text = (ex.explanation or '').strip()
        
        if explanation_text:
            # Парсим explanation
            parts = []
            clean_text = explanation_text.replace(' ', '').replace('\n', '').replace('\r', '')
            for char in clean_text.split(','):
                if char in ['|', '/', '-']:
                    parts.append(char)
        else:
            # Извлекаем из text
            parts = extract_from_text_and_masks(ex.text, ex.masked_word, 1400)
        
        # Заменяем маски в предложении
        masked_word = ex.masked_word
        line_parts = []
        
        while f'*1400*' in masked_word:
            mask_id = f"14-{mask_index}"
            
            # Заменяем маску
            masked_word = masked_word.replace(f'*1400*', f'*{mask_id}*', 1)
            
            # Сохраняем правильный ответ
            if parts:
                expected_letters.append(parts.pop(0))
            else:
                expected_letters.append('|')  # Fallback
            
            letter_groups[mask_id] = 'preposition'
            mask_index += 1
        
        lines.append(masked_word)
    
    return {
        'lines': lines[:5],  # Гарантируем максимум 5
        'expected_letters': expected_letters,
        'letter_groups': letter_groups,
        'subgroup_letters_map': {
            'preposition': ['|', '/', '-']  # Варианты для выпадающего списка
        }
    }

# ======= Задание 15 =================================================
def generate_task15_lines():
    """
    Генерирует 1 предложение для задания 15 (Н/НН в суффиксах).
    Берет 1 пример из орфограммы 1500.
    """
    # Берем 1 случайный активный пример
    example = OrthogramExample.objects.filter(
        orthogram_id=1500,
        is_active=True
    ).order_by('?').first()
    
    if not example:
        return {'lines': [], 'expected_letters': [], 'letter_groups': {}, 'subgroup_letters_map': {}}
    
    # Извлекаем правильные символы
    explanation_text = (example.explanation or '').strip()
    expected_letters = []
    letter_groups = {}
    mask_index = 1
    
    if explanation_text:
        # Парсим explanation
        clean_text = explanation_text.replace(' ', '').replace('\n', '').replace('\r', '')
        for part in clean_text.split(','):
            if part in ['н', 'нн']:
                expected_letters.append(part)
    else:
        # Fallback: извлекаем из text или correct_letters
        if example.correct_letters:
            clean_cl = example.correct_letters.replace(' ', '').replace('\n', '').replace('\r', '')
            for part in clean_cl.split(','):
                if part in ['н', 'нн']:
                    expected_letters.append(part)
        else:
            # Крайний fallback
            expected_letters = ['н', 'нн', 'н', 'нн'][:example.masked_word.count('*1500*')]
    
    # Заменяем маски в предложении
    masked_word = example.masked_word
    lines = []
    
    while f'*1500*' in masked_word:
        mask_id = f"15-{mask_index}"
        
        # Заменяем маску
        masked_word = masked_word.replace(f'*1500*', f'*{mask_id}*', 1)
        
        letter_groups[mask_id] = 'nn'
        mask_index += 1
    
    lines.append(masked_word)

    return {
        'lines': lines,
        'expected_letters': expected_letters,
        'letter_groups': letter_groups,
        'subgroup_letters_map': {
            'nn': ['н', 'нн']  # Варианты для выпадающего списка
        }
    }

# ======= Задание 18 функция деления на абзацы =======================
def generate_task18_with_paragraphs():
    """
    Задание 18 с абзацами (как в тренажерах)
    """
    punktum_id = '1800'
    
    # Берем 1 пример для задания 18
    example = PunktumExample.objects.filter(
        punktum__id=punktum_id,
        is_active=True
    ).order_by('?').first()
    
    if not example:
        return None
    
    # Разбиваем masked_word на абзацы по символу новой строки
    paragraphs = [p.strip() for p in example.masked_word.split('\n') if p.strip()]
    
    if not paragraphs:
        # Fallback: если нет абзацев, используем обычный формат
        return generate_task_with_image(punktum_id, 1, False)
    
    # Заменяем маски в каждом абзаце
    mask_index = 1
    processed_paragraphs = []
    correct_symbols = []
    
    explanation_text = (example.explanation or '').strip()
    if explanation_text:
        # Парсим explanation для получения правильных символов
        parts = [p.strip() for p in explanation_text.split(',') if p.strip()]
        for part in parts:
            correct_symbols.append('!' if part == '!' else '?')
    
    # Обрабатываем каждый абзац
    for para in paragraphs:
        # Считаем маски в этом абзаце
        mask_count_in_para = para.count(f'*{punktum_id}*')
        
        # Заменяем маски
        for _ in range(mask_count_in_para):
            mask_id = f"18-{mask_index}"
            para = para.replace(f'*{punktum_id}*', f'*{mask_id}*', 1)
            mask_index += 1
        
        processed_paragraphs.append(para)
    
    # Проверяем соответствие количества
    total_masks = mask_index - 1
    if len(correct_symbols) != total_masks:
        correct_symbols = ['!'] * total_masks
    
    # Подготавливаем данные
    letter_groups = {}
    for i in range(1, total_masks + 1):
        mask_id = f"18-{i}"
        letter_groups[mask_id] = 'punktum_18'
    
    # Для шаблона: structured_examples должен быть списком списков
    # Каждый пример - список абзацев
    structured_examples = [processed_paragraphs]  # Один пример с несколькими абзацами
    
    return {
        'structured_examples': structured_examples,  # Ключевое поле для шаблона!
        'lines': processed_paragraphs,               # Для совместимости
        'correct_symbols': correct_symbols,
        'letter_groups': letter_groups,
        'subgroup_letters': {'punktum_18': ['!', '?']},
        'image_name': 'images/punktum_task_18.webp',
        'add_numbering': False,
        'task_number': '18',
        'is_punktum_with_paragraphs': True,          # Флаг для шаблона
    }

# ======= Задание 21 - динамическое формирование =====================
def generate_task21_for_diagnostic():
    """
    Генерация задания 21 для диагностики
    """
    import random
    
    # Выбираем случайный вариант
    variants = ['2100', '2101', '2102']
    chosen_variant = random.choice(variants)
    
    # Используем существующую функцию для тренажеров
    # Или копируем ее логику
    
    # Берем пример из БД
    example = PunktumExample.objects.filter(
        punktum__id=chosen_variant,
        is_active=True
    ).order_by('?').first()
    
    if not example:
        return None
    
    # Разбиваем на абзацы если нужно
    paragraphs = [p.strip() for p in example.masked_word.split('\n') if p.strip()]
    
    # Обработка Explanation
    explanation_text = (example.explanation or '').strip()
    correct_symbols = []
    
    if explanation_text:
        parts = [p.strip() for p in explanation_text.split(',') if p.strip()]
        correct_symbols = parts  # Номера пунктограмм как есть
    
    # Заменяем маски
    mask_index = 1
    processed_paragraphs = []
    
    for para in paragraphs:
        while f'*{chosen_variant}*' in para:
            mask_id = f"21-{mask_index}"
            para = para.replace(f'*{chosen_variant}*', f'*{mask_id}*', 1)
            mask_index += 1
        processed_paragraphs.append(para)
    
    # Получаем доступные номера пунктограмм
    try:
        punktum = Punktum.objects.get(id=chosen_variant)
        allowed_letters = [letter.strip() for letter in punktum.letters.split(',')]
    except:
        # Fallback
        allowed_letters = {
            '2100': ['5', '8', '8.1', '9.2', '10', '13', '16', '18'],
            '2101': ['5', '9.1', '19'],
            '2102': ['2', '4.0', '4.1', '4.2', '5', '6', '7', '11', '12', '13', '14', '15', '16', '17']
        }.get(chosen_variant, ['5', '8', '9.1', '9.2', '10'])
    
    # Определяем заголовок
    titles = {
        '2100': '21. Кликни на смайлик, выбери подходящий номер пунктограммы для постановки ТИРЕ.',
        '2101': '21. Кликни на смайлик, выбери подходящий номер пунктограммы для постановки ДВОЕТОЧИЕ.',
        '2102': '21. Кликни на смайлик, выбери подходящий номер пунктограммы для постановки ЗАПЯТЫХ.',
    }
    
    return {
        'lines': processed_paragraphs,
        'correct_symbols': correct_symbols,
        'letter_groups': {f"21-{i+1}": 'punktum_21' for i in range(len(correct_symbols))},
        'subgroup_letters': {'punktum_21': allowed_letters},
        'image_name': f'images/punktum_task_21_{variants.index(chosen_variant)}.webp',
        'title': titles.get(chosen_variant),
        'variant_id': chosen_variant,
        'variant_index': variants.index(chosen_variant),
        'add_numbering': False,
        'task_number': '21',
        'is_punktum_exercise': True,
    }


# ======= Задание 22 - динамическое формирование =====================
def generate_task_twotwo_for_diagnostic():
    """Генерация задания 22 для диагностики"""
    try:
        # 1-5. Сбор данных (оставляем как есть)
        all_types = list(TaskGrammaticTwoTwo.objects.filter(is_active=True))
        if len(all_types) < 5:
            return None

        # 2. Выбираем 5 уникальных типов
        selected_types = []
        attempts = 0
        while len(selected_types) < 5 and attempts < 50:
            device = random.choice(all_types)
            if device not in selected_types:
                if TaskGrammaticTwoTwoExample.objects.filter(
                    device_type=device,
                    is_active=True
                ).exists():
                    selected_types.append(device)
            attempts += 1

        if len(selected_types) < 5:
            return None

        # 3. Выбираем уникальные примеры
        examples_qs = TaskGrammaticTwoTwoExample.objects.filter(is_active=True)
        selected_examples = []
        used_example_ids = set()

        for t in selected_types:
            type_examples = list(examples_qs.filter(device_type=t).exclude(id__in=used_example_ids))
            if not type_examples:
                type_examples = list(examples_qs.exclude(id__in=used_example_ids))
            if not type_examples:
                used_example_ids.clear()
                type_examples = list(examples_qs.filter(device_type=t))

            if type_examples:
                example = random.choice(type_examples)
                selected_examples.append(example)
                used_example_ids.add(example.id)

        if len(selected_examples) < 5:
            return None

        # 4. Добавляем еще 4 случайных средства
        remaining_types = [t for t in all_types if t not in selected_types]
        if len(remaining_types) >= 4:
            extra_types = random.sample(remaining_types, 4)
        else:
            extra_types = random.sample(all_types, 4)

        all_devices = selected_types + extra_types

        # Убираем дубликаты
        seen_ids = set()
        unique_devices = []
        for device in all_devices:
            if device.id not in seen_ids:
                seen_ids.add(device.id)
                unique_devices.append(device)

        all_devices = unique_devices
        random.shuffle(all_devices)

        # 5. Формируем данные и правильные ответы
        correct_answers = {}
        letters = ['А', 'Б', 'В', 'Г', 'Д']

        for i, ex in enumerate(selected_examples):
            if ex.device_type is None:
                logger.warning(f"Пример {ex.id} не имеет device_type, пропускаем")
                continue
            example_type_id = ex.device_type.id

            for idx, device in enumerate(all_devices, 1):
                if device.id == example_type_id:
                    correct_answers[letters[i]] = str(idx)
                    break

        # 6. Формируем данные для шаблона
        sentences_data = []
        for i, ex in enumerate(selected_examples):
            sentences_data.append({
                'text': ex.text,
                'author': ex.author or ''
            })

        device_names_list = []
        for i, device in enumerate(all_devices, 1):
            try:
                name = device.get_id_display()
            except AttributeError:
                name = str(device)
            device_names_list.append((str(i), name))

        # 7. Рендерим шаблон (ВМЕСТО ручной генерации HTML)
        html = render_to_string('task_grammatic_twotwo_snippet.html', {
            'sentences': sentences_data,
            'device_names_list': device_names_list,
            'show_check_button': False  # Для диагностики кнопка не нужна
        })

        return {
            'html': html,
            'correct_answers': correct_answers,
            'all_devices': [d.id for d in all_devices]
        }

    except Exception as e:
        logger.error(f"Ошибка генерации задания 22 для диагностики: {e}", exc_info=True)
        return None

# ========================================================================
# ОГЭ — ДИАГНОСТИКА (11 заданий)
# ========================================================================

def oge_diagnostic_page(request):
    """Страница ОГЭ-диагностики."""
    return render(request, 'diagnostic_oge.html')


def get_oge_text_analysis_questions(task_type):
    """
    Возвращает OgeTextAnalysisTask и вопросы для указанного типа.
    task_type: '1_2' (задания 1,2), '5' (задание 5), '9_10' (задания 9,10), '11' (задание 11)
    """
    number_map = {
        '1_2': [2, 3],
        '5': [6],
        '9_10': [10, 11],
        '11': [12],
    }
    required_numbers = number_map.get(task_type, [])
    if not required_numbers:
        return None, []

    tasks = OgeTextAnalysisTask.objects.filter(is_active=True).order_by('?')
    for task in tasks:
        qs = task.questions.filter(question_number__in=required_numbers)
        if qs.count() == len(required_numbers):
            return task, list(qs.order_by('question_number'))
    return None, []


def generate_oge_task3_matching():
    """
    Генерирует задание 3 ОГЭ (сопоставление правил и предложений).
    """
    from .models import OgeTaskGrammaticEight, OgeTaskGrammaticEightExample

    # Берем ровно 3 правила
    rules = list(OgeTaskGrammaticEight.objects.filter(is_active=True).order_by('id')[:3])
    if len(rules) < 3:
        return None

    # Берем ровно 5 предложений
    all_selected = list(OgeTaskGrammaticEightExample.objects.filter(is_active=True).order_by('id')[:5])
    if len(all_selected) < 5:
        return None

    letters = ['А', 'Б', 'В']
    type_to_letter = {rules[i].id: letters[i] for i in range(3)}

    error_type_names = {
        type_to_letter[t.id]: str(t)
        for t in rules
    }

    sentences = []
    correct_answers = {}
    # Предложения идут строго по порядку 1..5
    for i, item in enumerate(all_selected, 1):
        sentences.append({'position': str(i), 'text': item.text})
        if item.has_error and item.error_type_id in type_to_letter:
            correct_answers[type_to_letter[item.error_type_id]] = str(i)

    return {
        'correct_answers': correct_answers,
        'error_type_names': error_type_names,
        'sentences': sentences,
    }


def generate_oge_task4_with_image(punktum_id, num_sentences=1, add_numbering=False, is_for_quiz=None, override_letters=None):
    """
    Универсальная функция для пунктуационных заданий ОГЭ (задание 4).
    Поддерживает тире, двоеточие, запятую, КАВЫЧКИ.
    """
    query_kwargs = {
        'punktum__id': punktum_id,
        'is_active': True
    }
    if is_for_quiz is not None:
        query_kwargs['is_for_quiz'] = is_for_quiz

    examples = OgePunktumExample.objects.filter(**query_kwargs).order_by('?')[:num_sentences]

    if not examples:
        return None

    task_number = '5'
    all_lines = []
    all_correct_symbols = []
    letter_groups = {}
    mask_idx = 1

    for ex in examples:
        masked = ex.masked_word
        exp = (ex.explanation or '').strip()
        correct = []

        if exp:
            if ' ' in exp:
                parts = [p.strip() for p in exp.split(' ') if p.strip()]
            else:
                parts = [p.strip() for p in exp.split(',')]
                
            correct = []
            for p in parts:
                if p in (':', '«»', '—', ','):
                    correct.append(p)
                else:
                    correct.append(p)

        mask_count = masked.count(f'*{punktum_id}*')
        for _ in range(mask_count):
            mask_id = f"{task_number}-{mask_idx}"
            masked = masked.replace(f'*{punktum_id}*', f'*{mask_id}*', 1)
            letter_groups[mask_id] = f'punktum_{task_number}'
            mask_idx += 1

        if len(correct) != mask_count:
            correct = ['!'] * mask_count

        all_lines.append(masked)
        all_correct_symbols.extend(correct)

    if override_letters:
        letters = override_letters
    else:
        try:
            from main.models import OgePunktum
            punktum = OgePunktum.objects.get(id=punktum_id)
            letters = punktum.get_letters_list()
        except Exception:
            letters = ['5', '8', 'дз']

    # Для ОГЭ задания 4: картинки по типу знака
    image_mapping = {
        '2100': 'images/punktum_task_OGE_0.webp',  # Тире (общее)
        '2101': 'images/punktum_task_OGE_1.webp',  # Двоеточие (общее)
        '2102': 'images/punktum_task_OGE_2.webp',  # Запятые (общее)
        '2103': 'images/punktum_task_21_3.webp',  # Кавычки
        '8': 'images/punktum_task_OGE_8.webp',    # Тире (пунктограмма 8)
        '18': 'images/punktum_task_OGE_18.webp',   # Тире (пунктограмма 18)
        '19': 'images/punktum_task_OGE_19.webp',   # Двоеточие (пунктограмма 19)
    }

    title_mapping = {
        '2100': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ТИРЕ.',
        '2101': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ДВОЕТОЧИЯ.',
        '2102': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ЗАПЯТЫХ.',
        '2103': '5. Кликни на смайлик, выбери подходящий знак для постановки КАВЫЧЕК.',
        '8': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ТИРЕ.',
        '18': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ТИРЕ.',
        '19': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ДВОЕТОЧИЯ.',
    }

    # Набор файлов-картинок, которые реально существуют в static/images
    _existing_comma_images = {
        '2': 'images/punktum_task_OGE_02.webp',
        '3': 'images/punktum_task_OGE_3.webp',
        '4': 'images/punktum_task_OGE_4.webp',
        '6': 'images/punktum_task_OGE_67.webp',
        '7': 'images/punktum_task_OGE_67.webp',
        '11': 'images/punktum_task_OGE_1114.webp',
        '12': 'images/punktum_task_OGE_1114.webp',
        '13': 'images/punktum_task_OGE_1114.webp',
        '14': 'images/punktum_task_OGE_1114.webp',
        '15': 'images/punktum_task_OGE_15.webp',
    }
    comma_ids = ['2', '3', '4', '6', '7', '11', '12', '13', '14', '15']
    for c_id in comma_ids:
        image_mapping[c_id] = _existing_comma_images.get(c_id, 'images/punktum_task_OGE_2.webp')
        title_mapping[c_id] = '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ЗАПЯТЫХ.'

    # Формируем подпись пунктограммы (только для конкретных, не общих)
    general_ids = {'2100', '2101', '2102', '2103', 'mixed_dash_colon'}
    punktum_label = f'{punktum_id} пунктограмма' if punktum_id not in general_ids else ''

    result = {
        'lines': all_lines,
        'correct_symbols': all_correct_symbols,
        'letter_groups': letter_groups,
        'subgroup_letters': {f'punktum_{task_number}': letters},
        'image_name': image_mapping.get(punktum_id),
        'add_numbering': add_numbering,
        'task_number': task_number,
        'punktum_id': punktum_id,
        'punktum_label': punktum_label,
    }

    if punktum_id in title_mapping:
        result['title'] = title_mapping[punktum_id]

    return result


def generate_oge_diagnostic(request):
    """Генерация ОГЭ-диагностики (11 заданий)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        session_data = {}
        context = {}

        user_grade = None
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            user_grade = request.user.profile.grade

        # === Задания 2, 3: Чекбоксы (из OgeTextAnalysisTask) ===
        text_task_1_2, text_questions_1_2 = get_oge_text_analysis_questions('1_2')
        if text_task_1_2:
            context['text_task_1_2'] = text_task_1_2
            context['text_questions_1_2'] = text_questions_1_2
            session_data['answers_1_2'] = {
                str(q.question_number): q.correct_answer for q in text_questions_1_2
            }

        # === Задание 4: Синтаксический анализ (Сопоставление) ===
        task3_data = generate_oge_task3_matching()
        if task3_data:
            context['task3_error_type_names'] = task3_data.get('error_type_names', {})
            context['task3_sentences'] = task3_data.get('sentences', [])
            session_data['task3_correct'] = task3_data['correct_answers']

        # === Задание 5: Пунктуация — смайлики ===
        available_punktum_ids = list(
            OgePunktumExample.objects.filter(is_active=True)
            .values_list('punktum_id', flat=True)
            .distinct()
        )
        selected_type = random.choice(available_punktum_ids) if available_punktum_ids else None
        task4_data = generate_oge_task4_with_image(
            punktum_id=selected_type,
            num_sentences=1,
            add_numbering=False
        )
        if task4_data:
            context['task4_data'] = task4_data
            session_data['task4_correct'] = task4_data['correct_symbols']
            context['task4_letter_groups'] = json.dumps(task4_data['letter_groups'])
            context['task4_subgroup_letters'] = json.dumps(task4_data['subgroup_letters'])

        # === Задание 6: Чекбокс (из OgeTextAnalysisTask) ===
        text_task_5, text_questions_5 = get_oge_text_analysis_questions('5')
        if text_task_5:
            context['text_task_5'] = text_task_5
            context['text_questions_5'] = text_questions_5
            session_data['answers_5'] = {
                str(q.question_number): q.correct_answer for q in text_questions_5
            }

        # === Задание 7: Смайлики букв (из OgeOrthogramExample) ===
        try:
            oge_orth_examples = list(
                OgeOrthogramExample.objects.filter(is_active=True).order_by('?')[:3]
            )
            if oge_orth_examples:
                task6_lines = []
                task6_expected = []
                task6_letter_groups = {}
                task6_subgroup_letters = {}
                mask_idx = 1
                for ex in oge_orth_examples:
                    masked = ex.masked_word
                    orth_id = str(ex.orthogram_id)
                    # correct_letters: "а|а/о,а|а/о,ь|ь/ъ,..." — correct|choices per position
                    correct_letters_raw = (ex.correct_letters or '').split(',')
                    # Count how many *orth_id* masks are in this example
                    import re
                    mask_pattern = f'*{orth_id}*'
                    num_masks = masked.count(mask_pattern)
                    for pos in range(num_masks):
                        mask_id = f"6-{mask_idx}"
                        masked = masked.replace(mask_pattern, f'*{mask_id}*', 1)
                        # Parse per-position data
                        if pos < len(correct_letters_raw):
                            raw = correct_letters_raw[pos].strip()
                            if '|' in raw:
                                correct_letter, choices_str = raw.split('|', 1)
                                choices = [c.strip() for c in choices_str.split('/')]
                            else:
                                correct_letter = raw
                                choices = ex.orthogram.get_letters_list()
                        else:
                            correct_letter = ''
                            choices = ex.orthogram.get_letters_list()
                        task6_letter_groups[mask_id] = f'orth_{mask_idx}'
                        task6_subgroup_letters[f'orth_{mask_idx}'] = choices
                        task6_expected.append(correct_letter)
                        mask_idx += 1
                    task6_lines.append({'display_line': masked})

                context['task6_lines'] = task6_lines
                session_data['task6_correct'] = task6_expected
                context['task6_letter_groups'] = json.dumps(task6_letter_groups)
                context['task6_subgroup_letters'] = json.dumps(task6_subgroup_letters)
        except Exception as e:
            logger.error(f"Ошибка генерации задания 6 ОГЭ: {e}")

        # === Задание 8: Инпут — раскройте скобки (из OgeCorrectionExercise) ===
        try:
            task7_item = OgeCorrectionExercise.objects.filter(is_active=True).order_by('?').first()
            if task7_item:
                context['task7_word'] = task7_item.incorrect_text       # «вишня»
                context['task7_sentence'] = task7_item.explanation      # Для украшения десерта... (вишня).
                session_data['answer_7'] = task7_item.correct_text.lower().strip()  # вишен
        except Exception as e:
            logger.error(f"Ошибка генерации задания 7 ОГЭ: {e}")

        # === Задание 9: Инпут — словосочетание (из OgeWordOk) ===
        try:
            wordok = OgeWordOk.objects.filter(is_active=True).order_by('?').first()
            if wordok and wordok.correct_variants.strip():
                context['wordok_8'] = wordok
                session_data['answer_8'] = wordok.correct_variants
        except Exception as e:
            logger.error(f"Ошибка генерации задания 8 ОГЭ: {e}")

        # === Задания 10, 11: Чекбоксы по тексту (из OgeTextAnalysisTask) ===
        text_task_9_10, text_questions_9_10 = get_oge_text_analysis_questions('9_10')
        if text_task_9_10:
            context['text_task_9_10'] = text_task_9_10
            context['text_questions_9_10'] = text_questions_9_10
            session_data['answers_9_10'] = {
                str(q.question_number): q.correct_answer for q in text_questions_9_10
            }

        # === Задание 12: Инпут по тексту (из OgeTextAnalysisTask) ===
        text_task_11, text_questions_11 = get_oge_text_analysis_questions('11')
        if text_task_11:
            context['text_task_11'] = text_task_11
            context['text_questions_11'] = text_questions_11
            session_data['answers_11'] = {
                str(q.question_number): q.correct_answer for q in text_questions_11
            }

        # === Сохраняем в сессию ===
        request.session['oge_diagnostic'] = session_data

        # === Рендерим шаблон ===
        html = render_to_string('diagnostic_oge_snippet.html', context)
        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка генерации ОГЭ-диагностики: {e}", exc_info=True)
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)


def generate_oge_task5_mixed_dash_colon(is_for_quiz=None):
    """
    Смешанное задание: 5 предложений из тире (8, 18) и двоеточия (19).
    Случайно: 2 тире + 3 двоеточия или 3 тире + 2 двоеточия.
    Варианты ответов: — и :
    """
    import random

    dash_ids = ['8', '18']
    colon_ids = ['19']

    # Случайный набор: 2+3 или 3+2
    if random.choice([True, False]):
        num_dash, num_colon = 2, 3
    else:
        num_dash, num_colon = 3, 2

    query_kwargs = {'is_active': True}
    if is_for_quiz is not None:
        query_kwargs['is_for_quiz'] = is_for_quiz

    dash_examples = list(
        OgePunktumExample.objects.filter(
            punktum__id__in=dash_ids,
            **query_kwargs
        ).order_by('?')[:num_dash]
    )
    colon_examples = list(
        OgePunktumExample.objects.filter(
            punktum__id__in=colon_ids,
            **query_kwargs
        ).order_by('?')[:num_colon]
    )

    all_examples = dash_examples + colon_examples
    random.shuffle(all_examples)

    if not all_examples:
        return None

    task_number = '5'
    all_lines = []
    all_correct_symbols = []
    letter_groups = {}
    mask_idx = 1

    for ex in all_examples:
        masked = ex.masked_word
        punktum_id = str(ex.punktum_id)

        # Определяем правильный символ: тире или двоеточие
        if punktum_id in dash_ids:
            correct_symbol = '—'
        else:
            correct_symbol = ':'

        mask_count = masked.count(f'*{punktum_id}*')
        for _ in range(mask_count):
            mask_id = f"{task_number}-{mask_idx}"
            masked = masked.replace(f'*{punktum_id}*', f'*{mask_id}*', 1)
            letter_groups[mask_id] = 'punktum_5_mixed'
            all_correct_symbols.append(correct_symbol)
            mask_idx += 1

        all_lines.append(masked)

    letters = ['—', ':']

    return {
        'lines': all_lines,
        'correct_symbols': all_correct_symbols,
        'letter_groups': letter_groups,
        'subgroup_letters': {'punktum_5_mixed': letters},
        'image_name': 'images/punktum_task_OGE_1819.webp',
        'add_numbering': False,
        'task_number': task_number,
        'punktum_id': 'mixed_dash_colon',
        'punktum_label': '',
        'title': '5. Кликни по смайликам, выбери подходящий знак для постановки ТИРЕ или ДВОЕТОЧИЯ.',
    }




def generate_oge_single_task(request):
    """Генерация отдельных заданий ОГЭ (4, 5, 6, 7, 8, 9, 10-12) для 9 класса"""
    if request.method != 'POST':
        logger.warning(f'❌ Метод не POST')  # ← ДОБАВИТЬ
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        data = json.loads(request.body)
        task_number = str(data.get('task_number', ''))
        logger.info(f'📥 Запрос задания {task_number} ОГЭ')  # ← ДОБАВИТЬ
        
        session_data = request.session.get('oge_diagnostic', {})
        context = {}
        template_name = f'diagnostic_oge_task{task_number}_snippet.html'
        
        # === ЗАДАНИЕ 4: Синтаксический анализ (сопоставление) ===
        if task_number == '4':
            logger.info('📊 Генерация задания 4')  # ← ДОБАВИТЬ
            
            task3_data = generate_oge_task3_matching()
            if task3_data:
                context['task3_error_type_names'] = task3_data.get('error_type_names', {})
                context['task3_sentences'] = task3_data.get('sentences', [])
                session_data['task3_correct'] = task3_data['correct_answers']
        
        # === ЗАДАНИЕ 5: Пунктуация (смайлики) ===
        elif task_number.startswith('5_'):
            import random
            punktum_id_raw = task_number.replace('5_', '')
            
            # === СПЕЦИАЛЬНЫЙ РЕЖИМ: Тире/двоеточие (смешанный) ===
            if punktum_id_raw == 'mixed_dash_colon':
                task4_data = generate_oge_task5_mixed_dash_colon(is_for_quiz=False)
                if task4_data:
                    context['task4_data'] = task4_data
                    session_data['task4_correct'] = task4_data['correct_symbols']
                    context['task4_letter_groups'] = json.dumps(task4_data['letter_groups'])
                    context['task4_subgroup_letters'] = json.dumps(task4_data['subgroup_letters'])
                    template_name = 'diagnostic_oge_task5_snippet.html'
                else:
                    return JsonResponse({'error': 'Нет данных для задания 5'}, status=404)
            
            # === ОБЫЧНЫЙ РЕЖИМ: одна пунктограмма ===
            else:
                choices_map = {
                    '2100': ['8', '18'],
                    '2101': ['19'],
                    '2102': ['2', '3', '4', '6', '7', '11', '12', '13', '14', '15'],
                    '6_7': ['6', '7'],
                    '11_14': ['11', '12', '13', '14'],
                }
                
                # Переопределение вариантов ответа для общих управлений
                override_letters_map = {
                    '2100': ['5', '8', '8.1', '9.2', '10', '18', 'дз'],
                    '2101': ['5', '9.1', '19', 'дз'],
                    '2102': ['2', '3', '4.0', '4.1', '4.2', '5', '6', '7', '10', '11', '12', '13', '14', '15', '17', 'дз'],
                    '19': ['19.1', '19.2', '19.3'],
                }
                
                override_letters = override_letters_map.get(punktum_id_raw)
                punktum_id = punktum_id_raw
                is_general = punktum_id_raw in ('2100', '2101', '2102', '2103', '6_7', '11_14')
                
                # Выбираем конкретную пунктограмму из карты
                while punktum_id in choices_map:
                    punktum_id = random.choice(choices_map[punktum_id])
                
                task4_data = generate_oge_task4_with_image(
                    punktum_id=punktum_id,
                    num_sentences=1,
                    add_numbering=False,
                    is_for_quiz=None,
                    override_letters=override_letters
                )
                
                if task4_data:
                    # Для общего управления — статичная картинка и заголовок
                    if is_general:
                        _general_images = {
                            '2100': 'images/punktum_task_OGE_0.webp',
                            '2101': 'images/punktum_task_OGE_1.webp',
                            '2102': 'images/punktum_task_OGE_2.webp',
                        }
                        _general_titles = {
                            '2100': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ТИРЕ.',
                            '2101': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ДВОЕТОЧИЯ.',
                            '2102': '5. Кликни по смайликам, выбери подходящий номер пунктограммы для постановки ЗАПЯТЫХ.',
                        }
                        if punktum_id_raw in _general_images:
                            task4_data['image_name'] = _general_images[punktum_id_raw]
                        if punktum_id_raw in _general_titles:
                            task4_data['title'] = _general_titles[punktum_id_raw]
                    
                    context['task4_data'] = task4_data
                    session_data['task4_correct'] = task4_data['correct_symbols']
                    context['task4_letter_groups'] = json.dumps(task4_data['letter_groups'])
                    context['task4_subgroup_letters'] = json.dumps(task4_data['subgroup_letters'])
                    template_name = 'diagnostic_oge_task5_snippet.html'
                else:
                    return JsonResponse({'error': 'Нет данных для задания 5'}, status=404)
        
        # === ЗАДАНИЕ 6: Лексические нормы (чекбоксы) ===
        elif task_number == '6':
            logger.info('📊 Генерация задания 6')  # ← ДОБАВИТЬ
            
            text_task_5, text_questions_5 = get_oge_text_analysis_questions('5')
            if text_task_5:
                context['text_task_5'] = text_task_5
                context['text_questions_5'] = text_questions_5
                session_data['answers_5'] = {
                    str(q.question_number): q.correct_answer for q in text_questions_5
                }
            else:
                logger.error('❌ Нет данных для задания 6')  # ← ДОБАВИТЬ
                return JsonResponse({'error': 'Нет данных для задания 6'}, status=404)
        
        # === ЗАДАНИЕ 7: Орфография (смайлики букв) ===
        elif task_number == '7':
            oge_orth_examples = list(
                OgeOrthogramExample.objects.filter(is_active=True).order_by('?')[:3]
            )
            if oge_orth_examples:
                task6_lines = []
                task6_expected = []
                task6_letter_groups = {}
                task6_subgroup_letters = {}
                mask_idx = 1
                
                for ex in oge_orth_examples:
                    masked = ex.masked_word
                    orth_id = str(ex.orthogram_id)
                    correct_letters_raw = (ex.correct_letters or '').split(',')
                    
                    import re
                    mask_pattern = f'*{orth_id}*'
                    num_masks = masked.count(mask_pattern)
                    
                    for pos in range(num_masks):
                        mask_id = f"6-{mask_idx}"
                        masked = masked.replace(mask_pattern, f'*{mask_id}*', 1)
                        
                        if pos < len(correct_letters_raw):
                            raw = correct_letters_raw[pos].strip()
                            if '|' in raw:
                                correct_letter, choices_str = raw.split('|', 1)
                                choices = [c.strip() for c in choices_str.split('/')]
                            else:
                                correct_letter = raw
                                choices = ex.orthogram.get_letters_list()
                        else:
                            correct_letter = ''
                            choices = ex.orthogram.get_letters_list()
                        
                        task6_letter_groups[mask_id] = f'orth_{mask_idx}'
                        task6_subgroup_letters[f'orth_{mask_idx}'] = choices
                        task6_expected.append(correct_letter)
                        mask_idx += 1
                    
                    task6_lines.append({'display_line': masked})
                
                context['task6_lines'] = task6_lines
                session_data['task6_correct'] = task6_expected
                context['task6_letter_groups'] = json.dumps(task6_letter_groups)
                context['task6_subgroup_letters'] = json.dumps(task6_subgroup_letters)
            else:
                return JsonResponse({'error': 'Нет данных для задания 7'}, status=404)
        
        # === ЗАДАНИЕ 8: Раскройте скобки (инпут) ===
        elif task_number == '8':
            task7_item = OgeCorrectionExercise.objects.filter(is_active=True).order_by('?').first()
            if task7_item:
                context['task7_word'] = task7_item.incorrect_text
                context['task7_sentence'] = task7_item.explanation
                session_data['answer_7'] = task7_item.correct_text.lower().strip()
            else:
                return JsonResponse({'error': 'Нет данных для задания 8'}, status=404)
        
        # === ЗАДАНИЕ 9: Лексические нормы (инпут) ===
        elif task_number == '9':
            wordok = OgeWordOk.objects.filter(is_active=True).order_by('?').first()
            if wordok and wordok.correct_variants.strip():
                context['wordok_8'] = wordok
                session_data['answer_8'] = wordok.correct_variants
            else:
                return JsonResponse({'error': 'Нет данных для задания 9'}, status=404)
        
        # === ЗАДАНИЯ 10-12: Текстовый анализ ===
        elif task_number == '10-12':
            text_task_9_10, text_questions_9_10 = get_oge_text_analysis_questions('9_10')
            if text_task_9_10:
                context['text_task_9_10'] = text_task_9_10
                context['text_questions_9_10'] = text_questions_9_10
                session_data['answers_9_10'] = {
                    str(q.question_number): q.correct_answer for q in text_questions_9_10
                }
            
            text_task_11, text_questions_11 = get_oge_text_analysis_questions('11')
            if text_task_11:
                context['text_task_11'] = text_task_11
                context['text_questions_11'] = text_questions_11
                session_data['answers_11'] = {
                    str(q.question_number): q.correct_answer for q in text_questions_11
                }
            
            if not text_task_9_10 and not text_task_11:
                return JsonResponse({'error': 'Нет данных для заданий 10-12'}, status=404)
        
        # === НЕИЗВЕСТНОЕ ЗАДАНИЕ ===
        else:
            return JsonResponse({'error': 'Неизвестное задание'}, status=400)
        
        # Сохраняем сессию
        request.session['oge_diagnostic'] = session_data
        
        # Рендерим шаблон
        html = render_to_string(template_name, context)
        return JsonResponse({'html': html})
    
    except Exception as e:
        logger.error(f"Ошибка генерации задания {task_number} ОГЭ: {e}", exc_info=True)
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)


def check_oge_diagnostic(request):
    """Проверка ОГЭ-диагностики (11 заданий). Возвращает аналитику и полные правильные ответы."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        user_answers_dict = data.get('answers', {})
        session = request.session.get('oge_diagnostic')

        if not session:
            return JsonResponse({'error': 'Сессия устарела'}, status=400)

        results = {}
        total_score = 0
        max_score = 0
        analytics_parts = []

        def process_checkbox_task(answers_dict, task_q_nums):
            nonlocal total_score, max_score
            for q_num_str, correct in answers_dict.items():
                if int(q_num_str) not in task_q_nums: continue
                user_ans_raw = user_answers_dict.get(q_num_str, '')
                if isinstance(user_ans_raw, list):
                    user_ans = ''.join(str(x) for x in user_ans_raw)
                else:
                    user_ans = str(user_ans_raw).strip()

                q_num = int(q_num_str)
                is_correct = False
                correct_str = correct
                
                if q_num == 1:
                    correct_variants = [v.strip() for v in correct.split('/')]
                    is_correct = user_ans.lower() in [v.lower() for v in correct_variants]
                    correct_str = correct_variants[0]
                else:
                    user_sorted = ''.join(sorted(user_ans))
                    correct_sorted = ''.join(sorted(correct))
                    is_correct = user_sorted == correct_sorted

                score = 1 if is_correct else 0
                max_s = 1
                
                # Задание 6 - Орфограммы
                extras = ''
                if q_num == 6:
                    from main.models import OgeQuestionOption
                    options = OgeQuestionOption.objects.filter(question__question_number=6).order_by('option_number')
                    orth_parts = []
                    for opt in options:
                        if opt.orthogram_numbers:
                            orth_parts.append(f"{opt.option_number} - {opt.orthogram_numbers}")
                    if orth_parts:
                        extras = "ОРФОГРАММЫ:<br>" + "<br>".join(orth_parts)

                results[q_num_str] = {
                    'is_correct': is_correct,
                    'score': score,
                    'max_score': max_s,
                    'correct_answer': correct_str,
                    'extras': extras
                }
                total_score += score
                max_score += max_s
                analytics_parts.append((q_num, is_correct))

        # === Задания 2–3, 6, 10–11 ===
        process_checkbox_task(session.get('answers_1_2', {}), [2, 3])
        process_checkbox_task(session.get('answers_5', {}), [6])
        process_checkbox_task(session.get('answers_9_10', {}), [10, 11])

        # === Задание 4: Выпадающие списки ===
        task3_correct = session.get('task3_correct', {})
        if task3_correct:
            task3_correct_count = 0
            task3_details = {}
            letters = ['А', 'Б', 'В']
            correct_pairs = []
            for letter in letters:
                key = f"4-{letter}"
                user_answer = user_answers_dict.get(key, '-')
                correct_answer = task3_correct.get(letter, '')
                if correct_answer:
                    correct_pairs.append(f"{letter} - {correct_answer}")
                is_correct = (str(user_answer).strip() != '-' and str(user_answer).strip() == str(correct_answer).strip())
                task3_details[key] = {'is_correct': is_correct}
                if is_correct:
                    task3_correct_count += 1

            final_score = 1 if task3_correct_count == 3 else 0

            results['4'] = {
                'is_correct': final_score > 0,
                'score': final_score,
                'max_score': 1,
                'correct_answer': ""
            }
            results.update({k: {'is_correct': v['is_correct']} for k, v in task3_details.items()})
            total_score += final_score
            max_score += 1
            analytics_parts.append((4, final_score > 0))

        # === Задание 5: Пунктуация (смайлики) ===
        if 'task4_correct' in session:
            expected_symbols = session['task4_correct']
            task4_correct_count = 0
            task4_results = {}
            for i in range(1, len(expected_symbols) + 1):
                key = f"5-{i}"
                user_answer = user_answers_dict.get(key, '😊')
                user_clean = str(user_answer).strip()
                correct_symbol = expected_symbols[i-1] if i <= len(expected_symbols) else '?'
                is_correct = (user_clean != '😊' and user_clean != '' and user_clean == correct_symbol)
                task4_results[key] = {'is_correct': is_correct}
                if is_correct: task4_correct_count += 1

            task4_score = 1 if task4_correct_count == len(expected_symbols) else 0
            results['5'] = {
                'is_correct': task4_score == 1,
                'score': task4_score, 'max_score': 1,
                'correct_answer': ""
            }
            results.update(task4_results)
            total_score += task4_score
            max_score += 1
            analytics_parts.append((5, task4_score == 1))

        # === Задание 7: Смайлики букв ===
        if 'task6_correct' in session:
            expected_letters = session['task6_correct']
            total_masks = len(expected_letters)
            task6_correct_count = 0
            task6_results = {}
            for i in range(1, total_masks + 1):
                key = f"6-{i}"
                user_answer = user_answers_dict.get(key, '😊')
                user_clean = str(user_answer).strip().lower()
                correct_letter = expected_letters[i - 1].lower() if i <= len(expected_letters) else ''
                is_correct = (user_clean != '😊' and user_clean != '' and user_clean == correct_letter)
                task6_results[key] = {'is_correct': is_correct}
                if is_correct: task6_correct_count += 1

            task6_score = 1 if task6_correct_count == total_masks else 0
            results['7'] = {
                'is_correct': task6_score == 1,
                'score': task6_score, 'max_score': 1,
                'correct_answer': ""
            }
            results.update(task6_results)
            total_score += task6_score
            max_score += 1
            analytics_parts.append((7, task6_score == 1))

        # === Задание 8: Инпут ===
        if 'answer_7' in session:
            correct = session['answer_7'].strip().lower()
            user_ans = user_answers_dict.get('8', '').strip().lower()
            user_words_list = user_ans.split()
            user_word = user_words_list[-1] if user_words_list else ''
            is_correct = _normalize_text(user_word) == _normalize_text(correct)
            score = 1 if is_correct else 0
            results['8'] = {
                'is_correct': is_correct, 'score': score, 'max_score': 1,
                'correct_answer': correct
            }
            total_score += score
            max_score += 1
            analytics_parts.append((8, is_correct))

        # === Задание 9: Инпут (лексика) ===
        if 'answer_8' in session:
            correct = session['answer_8']
            user_ans = user_answers_dict.get('9', '').strip()
            variants = [v.strip() for v in correct.split(',') if v.strip()]
            is_correct = _normalize_text(user_ans) in [_normalize_text(v) for v in variants]
            score = 1 if is_correct else 0
            results['9'] = {
                'is_correct': is_correct, 'score': score, 'max_score': 1,
                'correct_answer': variants[0] if variants else correct
            }
            total_score += score
            max_score += 1
            analytics_parts.append((9, is_correct))

        # === Задание 12: Инпут по тексту ===
        answers_11 = session.get('answers_11', {})
        for q_num_str, correct in answers_11.items():
            user_ans = str(user_answers_dict.get(q_num_str, '')).strip()
            correct_variants = [v.strip() for v in correct.split('/')]
            is_correct = user_ans.lower() in [v.lower() for v in correct_variants]
            score = 1 if is_correct else 0
            results[q_num_str] = {
                'is_correct': is_correct, 'score': score, 'max_score': 1,
                'correct_answer': correct_variants[0] if correct_variants else correct
            }
            total_score += score
            max_score += 1
            analytics_parts.append((int(q_num_str), is_correct))

        # Формируем строку аналитики: 1+ 2- 3+ 4- ...
        analytics_parts.sort(key=lambda x: x[0])
        analytics_str = ' '.join(
            f"{num}+" if correct else f"{num}-"
            for num, correct in analytics_parts
        )

        return JsonResponse({
            'results': results,
            'total_score': total_score,
            'max_score': max_score,
            'analytics': analytics_str,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)


# === ФИКСИРОВАННЫЕ ТЕСТЫ ЕГЭ досрок ! ===
FIXTURES_DIR = Path(__file__).parent / 'fixtures'

def load_test_fixture(test_code):
    """Загружает JSON-фикстуру теста"""
    
    # Маппинг: 'код_из_URL' : 'реальное_имя_файла_без_.json'
    file_mapping = {
        'dosrok-2026': 'test_fix_ege_2',
        'demo-2026': 'test_fixdemo_ege_2026',
        'test_fixdiagnostic_ege_2027': 'test_fixdiagnostic_ege_2027',
    }
    
    filename = file_mapping.get(test_code, test_code)
    fixture_path = FIXTURES_DIR / f'{filename}.json'
    
    if not fixture_path.exists():
        return None
        
    try:
        with open(fixture_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def _build_test_fix_context(request, test_code):
    """Загружает фикстуру теста и строит контекст + сессионные данные.
    Возвращает (context, test_data) или HttpResponse с ошибкой.
    """
    test_data = load_test_fixture(test_code)
    if not test_data:
        return None, None

    tasks = test_data.get('tasks', {})
    correct_answers = test_data.get('correct_answers', {}).copy()

    # === ЗАДАНИЯ 1-3 (текст + вопросы) ===
    task13 = tasks.get('1_3', {})
    raw_text = task13.get('text', '')
    task13_paragraphs = [p.strip() for p in raw_text.split('\n') if p.strip()]

    questions_1_3 = {}
    for q_num, q_data in task13.get('questions', {}).items():
        q_text = q_data.get('text', '')
        q_type = q_data.get('type', 'text')

        if q_type == 'multiple_choice' and 'choices' in q_data:
            questions_1_3[q_num] = {
                'text': q_data.get('instruction', q_text),
                'type': q_type,
                'choices': q_data['choices']
            }
        else:
            import re
            parts = re.split(r'(?=\d+\))', q_text)
            variants = [p.strip() for p in parts if p.strip()]
            if len(variants) > 1:
                questions_1_3[q_num] = {
                    'text': variants[0],
                    'type': 'text',
                    'variants': variants[1:]
                }
            else:
                questions_1_3[q_num] = {'text': q_text, 'type': q_type}

    # === ЗАДАНИЯ 4-7 ===
    task4_data = tasks.get('4', {})
    task4_text = task4_data.get('text', '')
    task4_choices = task4_data.get('choices', [])
    if 'correct_answer' in task4_data:
        correct_answers['4'] = task4_data['correct_answer']

    task5_data = tasks.get('5', {})
    task5_text = task5_data.get('text', '')
    task5_sentences = task5_data.get('sentences', [])

    task6_data = tasks.get('6', {})
    task6_instruction = task6_data.get('instruction', '')
    task6_text = task6_data.get('text', '')

    task7_data = tasks.get('7', {})
    task7_instruction = task7_data.get('instruction', '')
    task7_phrases = task7_data.get('phrases', [])

    # === ЗАДАНИЕ 8 ===
    task8_html = ''
    task8_data = tasks.get('8', {})
    if task8_data:
        error_type_names = {e['letter']: e['name'] for e in task8_data.get('errors', [])}
        sentences = [
            {'position': str(s['number']), 'text': s['text']}
            for s in task8_data.get('sentences', [])
        ]
        task8_html = render_to_string('task_grammatic_eight.html', {
            'error_type_names': error_type_names,
            'sentences': sentences,
            'show_check_button': False
        })
        request.session[f'{test_code}_task8_matches'] = task8_data.get('correct_matches', {})

    # === ЗАДАНИЯ 9-21 ===
    task_lines_data = {}
    task_letter_groups = {}
    task_subgroup_letters = {}
    task21_image_name = ''

    for task_num in range(9, 22):
        task_key = str(task_num)
        if task_key in tasks:
            task_data = tasks[task_key]
            if 'expected' in task_data:
                for i, expected_val in enumerate(task_data['expected'], start=1):
                    correct_answers[f'{task_num}-{i}'] = expected_val
            task_lines_data[task_num] = task_data.get('lines', [])
            task_letter_groups[task_num] = task_data.get('letter_groups', {})
            task_subgroup_letters[task_num] = task_data.get('subgroup_letters', {})
            if task_num == 21:
                task21_image_name = task_data.get('image_name', '')

    # === ЗАДАНИЕ 22 ===
    task22_html = ''
    task22_data = tasks.get('22', {})
    if task22_data:
        sentences = []
        for ex in task22_data.get('examples', []):
            sentences.append({
                'letter': ex.get('letter', ''),
                'text': ex.get('text', ''),
                'author': ex.get('author', '')
            })
        device_names_list = []
        for term in task22_data.get('terms', []):
            device_names_list.append((str(term.get('number', '')), term.get('name', '')))
        task22_html = render_to_string('task_grammatic_twotwo_snippet.html', {
            'sentences': sentences,
            'device_names_list': device_names_list,
            'show_check_button': False
        })
        request.session[f'{test_code}_task22_matches'] = task22_data.get('correct_matches', {})

    # === ЗАДАНИЯ 23-27 ===
    task23_27 = tasks.get('23_27', {})
    task23_27_text = task23_27.get('text', '')
    task23_27_questions = task23_27.get('questions', {})
    for q_num, q_data in task23_27_questions.items():
        if 'correct_answer' in q_data:
            correct_answers[str(q_num)] = q_data['correct_answer']

    context = {
        'test_name': test_data.get('test_name', test_code),
        'test_code': test_code,
        'max_score': test_data.get('max_score', 50),
        'task13_paragraphs': task13_paragraphs,
        'task13_questions': questions_1_3,
        'task4_text': task4_text,
        'task4_choices': task4_choices,
        'task5_text': task5_text,
        'task5_sentences': task5_sentences,
        'task6_instruction': task6_instruction,
        'task6_text': task6_text,
        'task7_instruction': task7_instruction,
        'task7_phrases': task7_phrases,
        'task8_html': task8_html,
        'task9_lines': task_lines_data.get(9, []),
        'task10_lines': task_lines_data.get(10, []),
        'task11_lines': task_lines_data.get(11, []),
        'task12_lines': task_lines_data.get(12, []),
        'task13_lines': task_lines_data.get(13, []),
        'task14_lines': task_lines_data.get(14, []),
        'task15_lines': task_lines_data.get(15, []),
        'task16_lines': task_lines_data.get(16, []),
        'task17_lines': task_lines_data.get(17, []),
        'task18_lines': task_lines_data.get(18, []),
        'task19_lines': task_lines_data.get(19, []),
        'task20_lines': task_lines_data.get(20, []),
        'task21_lines': task_lines_data.get(21, []),
        'task21_image_name': task21_image_name,
        'task9_letter_groups': json.dumps(task_letter_groups.get(9, {})),
        'task9_subgroup_letters': json.dumps(task_subgroup_letters.get(9, {})),
        'task10_letter_groups': json.dumps(task_letter_groups.get(10, {})),
        'task10_subgroup_letters': json.dumps(task_subgroup_letters.get(10, {})),
        'task11_letter_groups': json.dumps(task_letter_groups.get(11, {})),
        'task11_subgroup_letters': json.dumps(task_subgroup_letters.get(11, {})),
        'task12_letter_groups': json.dumps(task_letter_groups.get(12, {})),
        'task12_subgroup_letters': json.dumps(task_subgroup_letters.get(12, {})),
        'task13_letter_groups': json.dumps(task_letter_groups.get(13, {})),
        'task13_subgroup_letters': json.dumps(task_subgroup_letters.get(13, {})),
        'task14_letter_groups': json.dumps(task_letter_groups.get(14, {})),
        'task14_subgroup_letters': json.dumps(task_subgroup_letters.get(14, {})),
        'task15_letter_groups': json.dumps(task_letter_groups.get(15, {})),
        'task15_subgroup_letters': json.dumps(task_subgroup_letters.get(15, {})),
        'task16_letter_groups': json.dumps(task_letter_groups.get(16, {})),
        'task16_subgroup_letters': json.dumps(task_subgroup_letters.get(16, {})),
        'task17_letter_groups': json.dumps(task_letter_groups.get(17, {})),
        'task17_subgroup_letters': json.dumps(task_subgroup_letters.get(17, {})),
        'task18_letter_groups': json.dumps(task_letter_groups.get(18, {})),
        'task18_subgroup_letters': json.dumps(task_subgroup_letters.get(18, {})),
        'task19_letter_groups': json.dumps(task_letter_groups.get(19, {})),
        'task19_subgroup_letters': json.dumps(task_subgroup_letters.get(19, {})),
        'task20_letter_groups': json.dumps(task_letter_groups.get(20, {})),
        'task20_subgroup_letters': json.dumps(task_subgroup_letters.get(20, {})),
        'task21_letter_groups': json.dumps(task_letter_groups.get(21, {})),
        'task21_subgroup_letters': json.dumps(task_subgroup_letters.get(21, {})),
        'task22_html': task22_html,
        'task23_27_text': task23_27_text,
        'task23_27_questions': task23_27_questions,
    }

    request.session[f'{test_code}_correct'] = correct_answers
    return context, test_data


@login_required
@ensure_csrf_cookie
def test_fix_ege(request, test_code):
    """View для досрочных вариантов ЕГЭ"""
    if request.method == 'POST':
        return check_test_fix_ege(request, test_code)

    context, test_data = _build_test_fix_context(request, test_code)
    if context is None:
        return render(request, 'test_fix_ege/test_fix_ege.html', {
            'test_name': test_code.replace('-', ' ').title(),
            'max_score': 0,
            'message': 'Этот вариант находится в разработке и скоро появится.'
        })

    return render(request, 'test_fix_ege/test_fix_ege.html', context)


@ensure_csrf_cookie
def diagnostic_fix_ege(request):
    """Входящая диагностика ЕГЭ — фиксированный вариант из фикстуры"""
    test_code = 'test_fixdiagnostic_ege_2027'
    if request.method == 'POST':
        return check_test_fix_ege(request, test_code)

    context, test_data = _build_test_fix_context(request, test_code)
    if context is None:
        return render(request, 'test_fix_ege/test_fixdiagnostic_ege.html', {
            'test_name': 'Диагностика',
            'max_score': 0,
            'message': 'Диагностика находится в разработке.'
        })

    return render(request, 'test_fix_ege/test_fixdiagnostic_ege.html', context)


def check_test_fix_ege(request, test_code):
    """Проверка фикс-теста (оптимизированная версия)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST-запросы'}, status=405)
    
    try:
        data = json.loads(request.body)
        user_answers = data.get('answers', {})
        
        # Загружаем эталонные данные из сессии
        correct = request.session.get(f'{test_code}_correct', {})
        task8_matches = request.session.get(f'{test_code}_task8_matches', {})
        task22_matches = request.session.get(f'{test_code}_task22_matches', {})
        
        if not correct:
            return JsonResponse({'error': 'Нет данных для проверки. Пожалуйста, обновите страницу.'}, status=400)
        
        results = {}
        total_score = 0
        
        # 1. БАЗОВАЯ ПРОВЕРКА ВСЕХ ОТВЕТОВ (включая подзадачи вида '9-1', '8_А' и т.д.)
        for q_num, correct_answer in correct.items():
            user_ans = user_answers.get(q_num, '')
            
            if isinstance(correct_answer, list):
                # Нормализация для списков (например, несколько вариантов в задании 4)
                user_list = user_ans if isinstance(user_ans, list) else [user_ans]
                user_set = {str(x).strip().lower() for x in user_list if x}
                correct_set = {str(x).strip().lower() for x in correct_answer}
                is_correct = user_set == correct_set
            else:
                is_correct = str(user_ans).strip().lower() == str(correct_answer).strip().lower()
            
            results[str(q_num)] = {'is_correct': is_correct}
            total_score += 1 if is_correct else 0

        # 2. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ для заданий с соответствием (8 и 22)
        def process_matching_task(task_num, matches_dict):
            nonlocal total_score
            letters = ['А', 'Б', 'В', 'Г', 'Д']
            correct_count = 0
            
            for letter in letters:
                key = f'{task_num}_{letter}'
                user_ans = user_answers.get(key, '').strip()
                correct_ans = matches_dict.get(letter, '')
                
                # Балл засчитывается только если ответ дан И он совпадает
                is_correct = bool(user_ans and user_ans == correct_ans)
                results[key] = {'is_correct': is_correct}
                
                if is_correct:
                    correct_count += 1
            
            # Вычитаем 5 баллов, которые были ошибочно начислены в цикле №1 за каждую подзадачу
            total_score -= 5 
            
            # Начисляем реальный балл по критериям ЕГЭ
            if correct_count == 5:
                score = 2
            elif correct_count >= 3:
                score = 1
            else:
                score = 0
                
            total_score += score
            
            results[str(task_num)] = {
                'is_correct': correct_count == 5,
                'score': score,
                'correct_count': correct_count,
                'max_possible': 5
            }

        # Применяем логику к заданиям 8 и 22
        if task8_matches:
            process_matching_task(8, task8_matches)
        if task22_matches:
            process_matching_task(22, task22_matches)

        # 3. АГРЕГАЦИЯ ЗАДАНИЙ 9–21 (и 21_1, 21_2)
        # Вместо 13 одинаковых блоков используем цикл
        for task_num in range(9, 22):
            task_keys = [k for k in results.keys() if str(k).startswith(f'{task_num}-')]
            if task_keys:
                is_task_correct = all(results[k]['is_correct'] for k in task_keys)
                
                # Корректируем счет: вычитаем N баллов за подзадачи, добавляем 1 за задание целиком
                total_score = total_score - len(task_keys) + (1 if is_task_correct else 0)
                results[str(task_num)] = {'is_correct': is_task_correct}

        # Отдельная обработка для подвариантов 21 (если они есть в фикстуре)
        for sub_task in ['21_1', '21_2']:
            sub_keys = [k for k in results.keys() if str(k).startswith(f'{sub_task}-')]
            if sub_keys:
                is_sub_correct = all(results[k]['is_correct'] for k in sub_keys)
                total_score = total_score - len(sub_keys) + (1 if is_sub_correct else 0)
                results[sub_task] = {'is_correct': is_sub_correct}

        # 4. ПОЛУЧЕНИЕ MAX_SCORE
        # Мы берем его напрямую из фикстуры. Он там уже правильный (например, 50).
        # Старая логика вычитания из него подзадач была ошибочной и искажала максимум.
        test_data = load_test_fixture(test_code)
        max_score = test_data.get('max_score', 50) if test_data else 50
        
        logger.info(f"Проверка {test_code}: Score {total_score}/{max_score}")

        if 'diagnostic' in test_code and request.user.is_authenticated:
            prof, _ = UserProfile.objects.get_or_create(user=request.user)
            if prof.level == 0:
                month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                used = DiagnosticAttempt.objects.filter(
                    user=request.user, is_completed=True, created_at__gte=month_start
                ).count()
                if used >= 1:
                    return JsonResponse({
                        'paywall': True,
                        'message': 'Бесплатная диагностика этого месяца использована. На платных тарифах диагностики безлимитны.',
                    }, status=403)

        # === Сохранение попытки (только для диагностических тестов) ===
        attempt_payload = {}
        if 'diagnostic' in test_code:
            try:
                if not request.session.session_key:
                    request.session.save()

                # Задача тронута, если пользователь дал непустой ответ
                # (структура ключей: '1', '8_А', '9-1' и т.д.)
                def _touched(n):
                    s = str(n)
                    if s in user_answers:
                        v = user_answers[s]
                        if isinstance(v, list):
                            return any(str(x).strip() for x in v)
                        return bool(str(v).strip())
                    if any(str(user_answers.get(f'{s}_{L}', '')).strip() for L in 'АБВГД'):
                        return True
                    pref = f'{s}-'
                    return any(
                        str(k).startswith(pref) and str(user_answers[k]).strip()
                        for k in user_answers
                    )

                # Считаем балл и слабые ТОЛЬКО по тронутым заданиям 1..26
                primary_score = 0
                weak = []
                for n in range(1, 27):
                    r = results.get(str(n))
                    if not r or not _touched(n):
                        continue          # пропустил → не ошибка и не балл
                    if 'score' in r:      # задания с градацией (8, 22)
                        primary_score += r['score']
                        if r['score'] == 0:
                            weak.append(n)
                    elif r.get('is_correct'):
                        primary_score += 1
                    else:
                        weak.append(n)

                primary, secondary = compute_primary_secondary(
                    {'results': results, 'user_answers': user_answers})

                diagnostic_type = request.session.get('diagnostic_type', '')
                max_primary = test_data.get('max_score', 50) if test_data else 50

                attempt = DiagnosticAttempt.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    session_key=request.session.session_key,
                    test_code=test_code,
                    diagnostic_type=diagnostic_type,
                    primary_score=primary,
                    max_primary_score=max_primary,
                    score=secondary,
                    max_score=100,
                    answers_data={'results': results, 'user_answers': user_answers},
                    weak_topics=weak,
                    is_completed=True,
                )
                attempt_payload = {
                    'attempt_id': str(attempt.id),
                    'access_code': attempt.access_code,
                    'needs_registration': not request.user.is_authenticated,
                }
            except Exception as e:
                logger.error(f"Не удалось сохранить попытку диагностики: {e}")

        return JsonResponse({
            'results': results,
            'total_score': total_score,
            'max_score': max_score,
            'test_name': test_data.get('test_name', test_code) if test_data else test_code,
            **attempt_payload,
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        return JsonResponse({'error': 'Неверный формат данных'}, status=400)
    except Exception as e:
        logger.error(f"Server Error: {e}\n{traceback.format_exc()}")
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# === ФИКСИРОВАННЫЕ ТЕСТЫ ЕГЭ ! ДЕМО ! ===
@login_required
@ensure_csrf_cookie
def test_fixdemo_ege(request, test_code):
    test_data = load_test_fixture(test_code)
    if not test_data:
        return render(request, '404.html', {'error': 'Файл теста не найден или повреждён'}, status=404)

    tasks = test_data.get('tasks', {})
    test_name = test_data.get('test_name', 'Демоверсия ЕГЭ')
    max_score = test_data.get('max_score', 50)

    # ==========================================================
    # 1. ОБРАБОТКА POST (ПРОВЕРКА)
    # ==========================================================
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_answers = data.get('answers', {})
            results = {}
            total_score = 0

            # --- Задания 1-3 ---
            t13 = tasks.get('1_3', {})
            correct_1_3 = t13.get('correct_answers', {})
            if isinstance(correct_1_3, list):
                correct_1_3 = {str(i+1): correct_1_3[i] for i in range(len(correct_1_3))}
            
            for q in ['1', '2', '3']:
                ua = user_answers.get(q, '').strip().lower()
                ca = correct_1_3.get(q)
                if ca is None: continue
                
                if isinstance(ca, list):
                    is_c = ua in [str(x).strip().lower() for x in ca]
                else:
                    is_c = ua == str(ca).strip().lower()
                    
                results[q] = {'is_correct': is_c}
                if is_c: total_score += 1

            # --- Задания 4, 5, 7 (простые текстовые ответы) ---
            for t_num in ['4', '5', '7']:
                task = tasks.get(t_num, {})
                ua = user_answers.get(t_num, '').strip().lower()
                # Поддержка разных ключей в JSON для гибкости
                ca = task.get('correct_answer') or task.get('correct_words') or task.get('correct_word')
                if isinstance(ca, list): ca = ca[0] if ca else ''
                
                is_c = ua == str(ca).strip().lower() if ca else False
                results[t_num] = {'is_correct': is_c}
                if is_c: total_score += 1

            # --- Задание 6 (Демо: part1 / part2) ---
            t6 = tasks.get('6', {})
            if 'part1' in t6:
                a1 = user_answers.get('6', '').strip().lower()
                a2 = user_answers.get('6_alt', '').strip().lower()
                c1 = t6['part1'].get('correct_words') or t6['part1'].get('correct_answers', [])
                c2 = t6['part2'].get('correct_words') or t6['part2'].get('correct_answers', [])
                
                if isinstance(c1, str): c1 = [c1]
                if isinstance(c2, str): c2 = [c2]
                
                is_c = (a1 in [str(x).strip().lower() for x in c1]) or (a2 in [str(x).strip().lower() for x in c2])
            else:
                ca = t6.get('correct_words') or t6.get('correct_answers', [])
                if isinstance(ca, str): ca = [ca]
                ua = user_answers.get('6', '').strip().lower()
                is_c = ua in [str(x).strip().lower() for x in ca]
                
            results['6'] = {'is_correct': is_c}
            if is_c: total_score += 1

            # --- Задание 8 (Соответствие, 0-2 балла) ---
            task8 = tasks.get('8', {})
            matches = task8.get('correct_matches') or task8.get('matches') or task8.get('answers') or {}
            if isinstance(matches, list) and len(matches) >= 5:
                matches = {letter: str(matches[i]) for i, letter in enumerate(['А','Б','В','Г','Д'])}
            
            correct_count_8 = 0
            for letter in ['А','Б','В','Г','Д']:
                key = f'8_{letter}'
                user_ans = user_answers.get(key, '').strip()
                correct_ans = str(matches.get(letter, '')).strip()
                is_correct = bool(user_ans and user_ans == correct_ans)
                results[key] = {'is_correct': is_correct}
                if is_correct: correct_count_8 += 1
                
            score_8 = 2 if correct_count_8 == 5 else (1 if correct_count_8 >= 3 else 0)
            results['8'] = {'is_correct': correct_count_8 == 5, 'score': score_8, 'correct_count': correct_count_8}
            total_score += score_8

            # --- Задания 13 и 14 (Смайлики с вариантами, 1 балл за задание целиком) ---
            for base in ['13', '14']:
                task = tasks.get(base, {})
                if not task: continue
                
                expected = {}
                if 'expected' in task:
                    raw = task['expected']
                    if isinstance(raw, list): expected = {str(i+1): v for i, v in enumerate(raw)}
                    elif isinstance(raw, dict): expected = raw
                    elif isinstance(raw, str): expected = {'1': raw}
                elif 'variants' in task:
                    idx = 1
                    for var in task['variants']:
                        var_exp = var.get('expected', [])
                        if isinstance(var_exp, list):
                            for val in var_exp:
                                expected[str(idx)] = val
                                idx += 1
                        elif isinstance(var_exp, str):
                            expected[str(idx)] = var_exp
                            idx += 1
                
                if not expected: continue

                task_correct_count = 0
                task_total_subtasks = len(expected)
                
                for sub_id, ca in expected.items():
                    k = f'{base}-{sub_id}'
                    ua = user_answers.get(k, '').strip()
                    is_c = ua == str(ca).strip()
                    results[k] = {'is_correct': is_c}
                    if is_c: task_correct_count += 1

                all_correct = (task_correct_count == task_total_subtasks) and task_total_subtasks > 0
                results[base] = {'is_correct': all_correct}
                if all_correct: total_score += 1

            # --- Задания 9-12, 15-21 (Обычные смайлики, 1 балл за задание целиком) ---
            for base in range(9, 22):
                if base in [13, 14]: continue # Уже обработаны выше
                task = tasks.get(str(base), {})
                if not task: continue
                
                expected = task.get('expected', {})
                if isinstance(expected, list) and expected and isinstance(expected[0], list):
                    flat_expected, counter = {}, 1
                    for variant_expected in expected:
                        for val in variant_expected:
                            flat_expected[str(counter)] = val
                            counter += 1
                    expected = flat_expected
                elif isinstance(expected, list):
                    expected = {str(i+1): expected[i] for i in range(len(expected))}
                elif isinstance(expected, str):
                    expected = {"1": expected}
                
                if not isinstance(expected, dict): continue

                task_correct_count = 0
                task_total_subtasks = len(expected)
                
                for sub_id, ca in expected.items():
                    k = f'{base}-{sub_id}'
                    ua = user_answers.get(k, '').strip()
                    is_c = ua == str(ca).strip()
                    results[k] = {'is_correct': is_c}
                    if is_c: task_correct_count += 1

                all_correct = (task_correct_count == task_total_subtasks) and task_total_subtasks > 0
                results[str(base)] = {'is_correct': all_correct}
                if all_correct: total_score += 1

            # --- Задания 21_1 и 21_2 (Специфичные для демо) ---
            for sub_task in ['21_1', '21_2']:
                task = tasks.get(sub_task, {})
                if not task: continue
                
                expected = task.get('expected', {})
                if isinstance(expected, list):
                    expected = {str(i+1): expected[i] for i in range(len(expected))}
                if not isinstance(expected, dict): continue

                task_correct_count = 0
                task_total_subtasks = len(expected)
                
                for sub_id, ca in expected.items():
                    k = f'{sub_task}-{sub_id}'
                    ua = user_answers.get(k, '').strip()
                    is_c = ua == str(ca).strip()
                    results[k] = {'is_correct': is_c}
                    if is_c: task_correct_count += 1

                all_correct = (task_correct_count == task_total_subtasks) and task_total_subtasks > 0
                results[sub_task] = {'is_correct': all_correct}
                if all_correct: total_score += 1

            # --- Задание 22 (Соответствие, 0-2 балла) ---
            task22 = tasks.get('22', {})
            matches_22 = task22.get('correct_matches', {})
            if matches_22:
                correct_count_22 = 0
                for letter in ['А', 'Б', 'В', 'Г', 'Д']:
                    key = f'22_{letter}'
                    user_ans = user_answers.get(key, '').strip()
                    correct_ans = str(matches_22.get(letter, '')).strip()
                    is_correct = bool(user_ans and user_ans == correct_ans)
                    results[key] = {'is_correct': is_correct}
                    if is_correct: correct_count_22 += 1
                
                score_22 = 2 if correct_count_22 == 5 else (1 if correct_count_22 >= 3 else 0)
                results['22'] = {
                    'is_correct': correct_count_22 == 5,
                    'score': score_22,
                    'correct_count': correct_count_22,
                    'max_possible': 5
                }
                total_score += score_22

            # --- Задания 23-26 (Текстовые поля из 23_27) ---
            task23_27 = tasks.get('23_27', {})
            questions = task23_27.get('questions', {})
            for t in ['23', '24', '25', '26']:
                q_data = questions.get(t, {})
                ua = user_answers.get(t, '').strip().lower()
                ca = q_data.get('correct_answer', '')
                if isinstance(ca, list): ca = ca[0] if ca else ''
                is_c = ua == str(ca).strip().lower() if ca else False
                results[t] = {'is_correct': is_c}
                if is_c: total_score += 1

            # --- Задание 27 (Сочинение) ---
            essay_val = user_answers.get('27', '').strip()
            if essay_val.isdigit():
                essay_score = int(essay_val)
                if 0 <= essay_score <= 22:
                    total_score += essay_score
                    results['27'] = {'is_correct': True, 'score': essay_score}

            return JsonResponse({
                'total_score': total_score,
                'max_score': max_score,
                'results': results
            })

        except Exception as e:
            return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)

    # ==========================================================
    # 2. ОБРАБОТКА GET (ОТРИСОВКА СТРАНИЦЫ)
    # ==========================================================
    raw_text = tasks.get('1_3', {}).get('text', '')
    
    # === Правильная обработка заданий 1-3 для шаблона ===
    questions_1_3 = {}
    for q_num, q_data in tasks.get('1_3', {}).get('questions', {}).items():
        q_text = q_data.get('text', '')
        q_type = q_data.get('type', 'text')
        
        if q_type == 'multiple_choice' and 'choices' in q_data:
            questions_1_3[q_num] = {
                'text': q_data.get('instruction', q_text),
                'type': q_type,
                'choices': q_data['choices']
            }
        else:
            import re
            parts = re.split(r'(?=\d+\))', q_text)
            variants = [p.strip() for p in parts if p.strip()]
            if len(variants) > 1:
                questions_1_3[q_num] = {'text': variants[0], 'type': 'text', 'variants': variants[1:]}
            else:
                questions_1_3[q_num] = {'text': q_text, 'type': q_type}

    # Задание 8 - генерация HTML
    task8_data = tasks.get('8', {})
    task8_html = ''
    if task8_data:
        error_type_names = {e['letter']: e['name'] for e in task8_data.get('errors', [])}
        sentences = [{'position': str(s['number']), 'text': s['text']} for s in task8_data.get('sentences', [])]
        
        task8_html = render_to_string('task_grammatic_eight.html', {
            'error_type_names': error_type_names,
            'sentences': sentences,
            'show_check_button': False  # ← ЯВНО False
        })
        
        # Сохраняем правильные ответы в сессию для последующей проверки
        request.session[f'{test_code}_task8_matches'] = task8_data.get('correct_matches', {})

  
    context = {
        'test_name': test_name,
        'max_score': max_score,
        'task13_paragraphs': [p.strip() for p in raw_text.split('\n') if p.strip()],
        'task13_questions': questions_1_3, # <-- ИСПРАВЛЕНО
        'task4': tasks.get('4', {}),
        'task5': tasks.get('5', {}),
        'task6': tasks.get('6', {}),
        'task7': tasks.get('7', {}),
        # 'task8': tasks.get('8', {}),

        # Передаем сгенерированный HTML
        'task8_html': task8_html, 
        # ================================================

        'task23_27_text': tasks.get('23_27', {}).get('text', ''),
        'task23_27_questions': tasks.get('23_27', {}).get('questions', {}),
    }



    # Задания 13 и 14 (с вариантами ИЛИ)
    for num in ['13', '14']:
        task_data = tasks.get(num, {})
        variants = task_data.get('variants', [])
        if not variants and task_data.get('lines'):
            variants = [{'lines': task_data.get('lines', [])}]
        
        context[f'task{num}_variants'] = variants
        context[f'task{num}_letter_groups'] = json.dumps(task_data.get('letter_groups', {}))
        context[f'task{num}_subgroup_letters'] = json.dumps(task_data.get('subgroup_letters', {}))

    # Задания 9-21 (ИСКЛЮЧАЯ 13 и 14, чтобы не перезаписать variants)
    for num in range(9, 22):
        if num in [13, 14]:
            continue
        task = tasks.get(str(num), {})
        if not task: continue
        
        context[f'task{num}_lines'] = task.get('lines', [])
        context[f'task{num}_letter_groups'] = json.dumps(task.get('letter_groups', {}))
        context[f'task{num}_subgroup_letters'] = json.dumps(task.get('subgroup_letters', {}))
        
        if num == 21:
            context['task21_image_name'] = task.get('image_name', '')

    # Специфичные задания 21_1 и 21_2
    for sub in ['21_1', '21_2']:
        task = tasks.get(sub, {})
        if task:
            context[f'{sub}_lines'] = task.get('lines', [])
            context[f'{sub}_image_name'] = task.get('image_name', '')
            context[f'{sub}_letter_groups'] = json.dumps(task.get('letter_groups', {}))
            context[f'{sub}_subgroup_letters'] = json.dumps(task.get('subgroup_letters', {}))

    # Задание 22 - генерация HTML через сниппет
    task22 = tasks.get('22', {})
    if task22:
        sentences = []
        for ex in task22.get('examples', []):
            sentences.append({
                'letter': ex.get('letter', ''),
                'text': ex.get('text', ''),
                'author': ex.get('author', '')
            })
        
        device_names_list = []
        for term in task22.get('terms', []):
            device_names_list.append((str(term.get('number', '')), term.get('name', '')))
        
        task22_html = render_to_string('task_grammatic_twotwo_snippet.html', {
            'sentences': sentences,
            'device_names_list': device_names_list,
            'show_check_button': False
        })
        context['task22_html'] = task22_html
        request.session[f'{test_code}_task22_matches'] = task22.get('correct_matches', {})


    return render(request, 'test_fix_ege/test_fixdemo_ege.html', context)


def diagnostic_starting(request, diagnostic_type):
    """Стартовая страница диагностики с мотивирующим текстом"""
    
    if diagnostic_type == 'starting':
        title = "Входящая диагностика"
        motivation_text = (
            "Добросовестное выполнение позволит:\n"
            "◆ оценить уровень знаний,\n"
            "◆ определить сильные и слабые стороны,\n"
            "◆ провести встречу с преподавателем с максимальной пользой."
        )
    elif diagnostic_type == 'current':
        title = "Текущая диагностика"
        motivation_text = (
            "Регулярная тренировка помогает:\n"
            "◆ сделать правила привычными,\n"
            "◆ оценить уровень знаний на сегодня,\n"
            "◆ выявить пробелы."
        )
    elif diagnostic_type == 'final':
        title = "Итоговая диагностика"
        motivation_text = (
            "Итоговый тест:\n"
            "◆ оценка уровня знаний перед экзаменом,\n"
            "◆ самая точная корректировка пробелов,\n"
            "◆ желаем удачи!"
        )
    else:
        return HttpResponse("Неверный тип диагностики", status=400)

    # КРИТИЧЕСКИ ВАЖНО: передаём diagnostic_type в шаблон
    return render(request, 'diagnostic_starting.html', {
        'title': title,
        'motivation_text': motivation_text,
        'diagnostic_type': diagnostic_type
    })

def start_diagnostic_test(request, diagnostic_type):
    """Запуск диагностики — перенаправление на страницу генерации теста"""
    if diagnostic_type in ['starting', 'current', 'final']:
        # 1. Сохраняем тип диагностики в сессии (чтобы генератор или аналитика знали, какой это тест)
        request.session['diagnostic_type'] = diagnostic_type
        
        # 2. Перенаправляем на view, который генерирует тест и рендерит diagnostic_snippet.html
        return redirect('generate_starting_diagnostic')
    else:
        return HttpResponse("Неверный тип диагностики", status=400)


@teacher_required
def diagnostic_list(request):
    """Реестр всех завершённых диагностик — точка входа преподавателя."""
    attempts = (
        DiagnosticAttempt.objects.filter(is_completed=True)
        .select_related('user')
        .order_by('-created_at')
    )
    return render(request, 'test_fix_ege/diagnostic_list.html', {'attempts': attempts})


def _collect_user_answer(user_answers, num):
    """Собирает сырые ответы ученика по номеру задания в читаемую строку.
    Ключи вида '8', '8_А', '9-1' группируются под заданием 8 / 9."""
    s = str(num)
    parts = []
    for k in sorted(user_answers.keys(), key=lambda x: (len(x), x)):
        v = user_answers.get(k, '')
        if isinstance(v, list):
            v = ', '.join(str(i) for i in v)
        v = str(v).strip()
        if not v:
            continue
        if k == s:
            parts.append(v)
        elif k.startswith(s + '_'):           # подзадачи 8/22: буква
            parts.append(f"{k.split('_', 1)[1]}: {v}")
        elif k.startswith(s + '-'):           # подзадачи 9-21: номер строки
            parts.append(v)
    return '   '.join(parts)


@teacher_required
def diagnostic_review(request, attempt_id):
    """Разбор конкретной диагностики: ответы ученика + заметки + статус."""
    attempt = get_object_or_404(DiagnosticAttempt, id=attempt_id)

    if request.method == 'POST':
        attempt.teacher_notes = request.POST.get('teacher_notes', '').strip()
        if 'mark_reviewed' in request.POST:
            attempt.is_reviewed_by_teacher = True
            attempt.reviewed_at = timezone.now()
        else:
            # сняли галочку — сбрасываем статус (черновик заметок без пометки)
            attempt.is_reviewed_by_teacher = False
            attempt.reviewed_at = None
        attempt.save()
        messages.success(request, 'Разбор сохранён')
        return redirect('diagnostic_review', attempt_id=attempt.id)

    # Собираем представление по заданиям 1..26
    results = attempt.answers_data.get('results', {})
    user_answers = attempt.answers_data.get('user_answers', {})
    weak = set(attempt.weak_topics or [])

    task_view = []
    for n in range(1, 27):
        s = str(n)
        r = results.get(s) or {}
        answer_str = _collect_user_answer(user_answers, n)
        score_info = f"{r.get('score')}/{r.get('max_possible')}" if 'score' in r else None
        task_view.append({
            'num': n,
            'answer': answer_str or '—',
            'is_correct': r.get('is_correct'),
            'score_info': score_info,
            'weak': n in weak,
            'touched': bool(answer_str),
        })

    fixture = load_test_fixture(attempt.test_code)
    work = build_student_work(fixture, attempt.answers_data) if fixture else []

    return render(request, 'test_fix_ege/diagnostic_review.html', {
        'attempt': attempt,
        'task_view': task_view,
        'weak': sorted(weak),
        'work': work,
    })


def _reconstruct_lines(lines, user_answers, results, expected):
    """Вставляет ответы ученика в строки бланка вместо маркеров *(KEY)*.
    Возвращает список готовых HTML-строк (безопасных для |safe)."""
    # эталон по ключу: порядок маркеров в строках == порядок expected
    keys_in_order = []
    for ln in lines:
        keys_in_order += _re.findall(r'\*\(([^)]+)\)\*', ln)
    expected_map = {k: expected[i] for i, k in enumerate(keys_in_order) if i < len(expected)}

    def span_for_key(key):
        ua = _esc(str(user_answers.get(key, '')).strip())
        corr = (results.get(key) or {}).get('is_correct')
        exp = _esc(str(expected_map.get(key, '')))
        if ua:
            cls = 'sw-ok' if corr else 'sw-no'
            hint = '' if corr else f'&nbsp;<span class="sw-exp">({exp})</span>'
            return f'<span class="{cls}">{ua}</span>{hint}'
        return f'<span class="sw-exp">({exp})</span>'

    rendered = []
    for ln in lines:
        parts = _re.split(r'(\*\([^)]+\)\*)', ln)
        out = []
        for p in parts:
            m = _re.fullmatch(r'\*\(([^)]+)\)\*', p)
            if m:
                out.append(span_for_key(m.group(1)))
            else:
                out.append(_esc(p))
        rendered.append(''.join(out))
    return rendered


def _match_rows(task_data, user_answers, results, num, text_field='text'):
    """Строки таблицы соответствия (задания 8 и 22)."""
    matches = task_data.get('correct_matches', {})
    rows = []
    for e in task_data.get('errors', task_data.get('examples', [])):
        letter = e.get('letter', '')
        key = f'{num}_{letter}'
        ua = _esc(str(user_answers.get(key, '')).strip())
        corr = (results.get(key) or {}).get('is_correct')
        rows.append({
            'letter': letter,
            'name': _pyhtml.unescape(str(e.get('name') or e.get(text_field, ''))),
            'user': ua or '—',
            'correct': _esc(str(matches.get(letter, ''))),
            'is_correct': corr,
            'touched': bool(ua),
        })
    return rows

def _ref_lines_from(items):
    """Нумерованный список-справочник: предложения (задание 8) или термины (задание 22)."""
    lines = []
    for i, it in enumerate(items, 1):
        if isinstance(it, dict):
            num = it.get('number', i)
            text = it.get('text') or it.get('name') or ''
        else:
            num, text = i, it
        # Приводим &lt;span ...&gt; к живому <span ...>, чтобы стили применялись единообразно
        text = _pyhtml.unescape(str(text))
        lines.append(f"{num}) {text}")
    return lines



# Формулировки заданий
TASK_INSTRUCTIONS = {
    8: 'Установите соответствие между грамматическими ошибками и предложениями, в которых они допущены: к каждой позиции первого столбца подберите позицию из второго.',
    9: 'Выберите правильную букву, кликнув по смайлику.',
    10: 'Вставьте пропущенные буквы, кликнув по смайлику.',
    11: 'Вставьте пропущенные буквы, кликнув по смайлику.',
    12: 'Вставьте пропущенные буквы, кликнув по смайлику.',
    13: 'Укажите варианты написания НЕ со словом: слитно (/) или раздельно (|), кликнув по смайлику.',
    14: 'Укажите варианты написания: слитно (/), раздельно (|) или через дефис (-), кликнув по смайлику.',
    15: 'Выберите Н или НН в словах, кликнув по смайлику.',
    16: 'Расставьте запятые там, где это нужно (,). Там, где запятые не нужны (х).',
    17: 'Расставьте запятые там, где это нужно (,). Там, где запятые не нужны (х).',
    18: 'Расставьте запятые там, где это нужно (,). Там, где запятые не нужны (х).',
    19: 'Расставьте запятые там, где это нужно (,). Там, где запятые не нужны (х).',
    20: 'Расставьте запятые там, где это нужно (,). Там, где запятые не нужны (х).',
    21: 'Выберите подходящий номер пунктограммы из списка, кликнув по смайлику.',
    22: 'Установите соответствие между средствами выразительности и фрагментами текста: к каждой позиции первого столбца подберите позицию из второго.',
}

# Зеркало конвертации из test_fix_ege.js
CONVERSION_TABLE = {
    0: 0, 1: 3, 2: 5, 3: 8, 4: 10, 5: 12, 6: 15, 7: 17, 8: 20, 9: 22, 10: 24, 11: 27, 12: 29, 13: 32, 14: 34,
    15: 36, 16: 37, 17: 39, 18: 40, 19: 42, 20: 43, 21: 45, 22: 46, 23: 48, 24: 49, 25: 51, 26: 52, 27: 54,
    28: 55, 29: 57, 30: 58, 31: 60, 32: 61, 33: 63, 34: 64, 35: 66, 36: 67, 37: 69, 38: 70, 39: 72, 40: 73,
    41: 75, 42: 78, 43: 81, 44: 83, 45: 86, 46: 89, 47: 91, 48: 94, 49: 97, 50: 100,
}


def compute_primary_secondary(answers_data):
    """Единая формула баллов — зеркало test_fix_ege.js."""
    results = answers_data.get('results', {})
    user_answers = answers_data.get('user_answers', {})
    primary = 0
    for i in range(1, 27):
        if i in (8, 22):
            continue
        if (results.get(str(i)) or {}).get('is_correct'):
            primary += 1
    primary += (results.get('8') or {}).get('score') or 0
    primary += (results.get('22') or {}).get('score') or 0
    try:
        val = int(str(user_answers.get('27', '')).strip())
        if 0 <= val <= 22:
            primary += val
    except (ValueError, TypeError):
        pass
    secondary = CONVERSION_TABLE.get(primary)
    if secondary is None:
        secondary = min(100, 100 + (primary - 50) * 2) if primary > 50 else 100
    return primary, secondary


def build_student_work(fixture, answers_data):
    """Собирает реконструкцию работы ученика по фикстуре + его ответам."""
    tasks = fixture.get('tasks', {})
    ca = fixture.get('correct_answers', {}) or {}
    user_answers = answers_data.get('user_answers', {})
    results = answers_data.get('results', {})
    work = []

    def ua(k):
        return _esc(str(user_answers.get(k, '')).strip())

    def corr(k):
        return (results.get(k) or {}).get('is_correct')

    # --- Задания 1-3 (общий текст + вопросы) ---
    t13 = tasks.get('1_3', {})
    if t13:
        qs = []
        for qn, qd in t13.get('questions', {}).items():
            correct = qd.get('correct_answer') or ca.get(qn)
            qs.append({
                'num': qn, 'text': qd.get('text', ''), 'type': qd.get('type', ''),
                'choices': qd.get('choices', []), 'correct': correct,
                'user': ua(qn), 'is_correct': corr(qn),
            })
        work.append({'kind': 'textblock', 'num': '1–3',
                     'title': 'Задания 1–3. Текст и вопросы',
                     'paragraphs': t13.get('text', ''), 'questions': qs})

    # --- Задание 4 (ударения) ---
    t4 = tasks.get('4', {})
    if t4:
        work.append({'kind': 'choices', 'num': '4',
                     'title': 'Задание 4. Ударения',
                     'instruction': t4.get('text', ''),
                     'choices': t4.get('choices', []),
                     'correct': t4.get('correct_answer', ''),
                     'user': ua('4'), 'is_correct': corr('4')})

    # --- Задание 5 (паронимы) ---
    t5 = tasks.get('5', {})
    if t5:
        work.append({'kind': 'sentences', 'num': '5',
                     'title': 'Задание 5. Паронимы',
                     'instruction': t5.get('text', ''),
                     'sentences': t5.get('sentences', []),
                     'correct': t5.get('correct_word', ''),
                     'user': ua('5'), 'is_correct': corr('5')})

    # --- Задание 6 (лексическая ошибка) ---
    t6 = tasks.get('6', {})
    if t6:
        work.append({'kind': 'exclude', 'num': '6',
                     'title': 'Задание 6. Лексическая ошибка',
                     'instruction': t6.get('instruction', ''),
                     'text': t6.get('text', ''),
                     'correct': ', '.join(t6.get('correct_words', [])),
                     'user': ua('6'), 'is_correct': corr('6')})

    # --- Задание 7 (грамматическая ошибка) ---
    t7 = tasks.get('7', {})
    if t7:
        work.append({'kind': 'phrases', 'num': '7',
                     'title': 'Задание 7. Грамматическая ошибка',
                     'instruction': t7.get('instruction', ''),
                     'phrases': t7.get('phrases', []),
                     'correct': t7.get('correct_word', ''),
                     'user': ua('7'), 'is_correct': corr('7')})

    # --- Задание 8 (соответствие) ---
    t8 = tasks.get('8', {})
    if t8:
        work.append({'kind': 'match', 'num': '8',
                     'title': 'Задание 8. Грамматические нормы',
                     'instruction': TASK_INSTRUCTIONS[8],
                     'rows': _match_rows(t8, user_answers, results, 8),
                     'refs': t8.get('sentences', []),
                     'ref_lines': _ref_lines_from(t8.get('sentences', []))})

    # --- Задания 9-21 (орфография/пунктуация — реконструкция строк) ---
    for n in range(9, 22):
        td = tasks.get(str(n))
        if not td or 'lines' not in td:
            continue
        work.append({'kind': 'lines', 'num': str(n),
                     'title': f'Задание {n}',
                     'instruction': TASK_INSTRUCTIONS.get(n, ''),
                     'rendered_lines': _reconstruct_lines(
                         td['lines'], user_answers, results, td.get('expected', []))})

    # --- Задание 22 (соответствие) ---
    t22 = tasks.get('22', {})
    if t22:
        work.append({'kind': 'match', 'num': '22',
                     'title': 'Задание 22. Средства выразительности',
                     'instruction': TASK_INSTRUCTIONS[22],
                     'rows': _match_rows(t22, user_answers, results, 22, text_field='text'),
                     'refs': t22.get('terms', []),
                     'ref_lines': _ref_lines_from(t22.get('terms', []))})

    # --- Задания 23-26 (текст + вопросы) ---
    t23 = tasks.get('23_27', {})
    if t23:
        qs = []
        for qn, qd in t23.get('questions', {}).items():
            qs.append({'num': qn, 'text': qd.get('text', ''),
                       'choices': qd.get('choices', []),
                       'correct': qd.get('correct_answer') or ca.get(qn),
                       'user': ua(qn), 'is_correct': corr(qn)})
        work.append({'kind': 'textblock', 'num': '23–26',
                     'title': 'Задания 23–26. Текст и вопросы',
                     'paragraphs': t23.get('text', ''), 'questions': qs})

    # --- Задание 27 (самооценка сочинения) ---
    work.append({'kind': 'essay', 'num': '27',
                 'title': 'Задание 27. Средний балл за сочинение',
                 'user': ua('27') or '—'})

    return work


def _L(label, url=None, ext=False):
    """Ссылка недели плана. url=None — заглушка «скоро», ext — внешняя (новая вкладка)."""
    return {'label': label, 'url': url, 'ext': ext}


DOMINO_URL = 'https://app.neurostud.ru/domino/single/ruLangEge'

# === ТРЕКИ ПЛАНА · 10 НЕДЕЛЬ ===
# Выбор по вторичному баллу: < 30 база, 30–78 средний, >= 79 углубление
PLAN_TRACKS = {
    'base': {
        'level': 'Ваш уровень: стартуем с базы',
        'weeks': [
            {'title': 'Части речи. Задание 1. Игра «Морфологическое домино»', 'tasks': [1],
             'links': [_L('Играть в Домино', DOMINO_URL, ext=True)]},
            {'title': 'Текст, лексика. Задания 1–3', 'tasks': [1, 2, 3],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Ударения (1). Задание 4', 'tasks': [4],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Онлайн-словарь ударений', reverse_lazy('orthoepy_trening')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Ударения (2). Задание 4', 'tasks': [4],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Квизы', reverse_lazy('quizzes_ege'))]},
            {'title': 'Паронимы. Задание 5', 'tasks': [5],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Онлайн-словник паронимов'), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Лексические нормы. Задание 6', 'tasks': [6],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Грамматические формы (1). Задание 7', 'tasks': [7],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Квизы', reverse_lazy('quizzes_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Грамматические формы (2). Ловушки ЕГЭ', 'tasks': [7],
             'links': [_L('Горячие квизы', reverse_lazy('quizzes_ege')), _L('Тренажёры', reverse_lazy('trainers_ege'))]},
            {'title': 'Г-С нормы. Задание 8', 'tasks': [8],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Пробник и его разбор в формате диагностики (1–8) и стратегия экзамена', 'tasks': [],
             'links': [_L('Уроки и материалы', reverse_lazy('lessons_ege'))]},
        ],
    },
    'mid': {
        'level': 'Ваш уровень: уверенный — «средний»',
        'weeks': [
            {'title': 'Текст, лексика, служебные ЧР. Задания 1–3', 'tasks': [1, 2, 3],
             'links': [_L('Играть в Домино', DOMINO_URL, ext=True), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Ударения. Задание 4', 'tasks': [4],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Онлайн-словарь ударений', reverse_lazy('orthoepy_trening')), _L('Квизы', reverse_lazy('quizzes_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Паронимы (1). Задание 5', 'tasks': [5],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Онлайн-словник паронимов'), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Паронимы (2). Задание 5', 'tasks': [5],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege'))]},
            {'title': 'Лексические нормы. Задание 6', 'tasks': [6],
             'links': [_L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Грамматические формы (1). Задание 7', 'tasks': [7],
             'links': [_L('Квизы', reverse_lazy('quizzes_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Грамматические формы (2). Ловушки ЕГЭ', 'tasks': [7],
             'links': [_L('Горячие квизы', reverse_lazy('quizzes_ege')), _L('Тренажёры', reverse_lazy('trainers_ege'))]},
            {'title': 'Г-С нормы. Задание 8. Типы ошибок и примеры', 'tasks': [8],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Орфография. Задание 9. Ловушки', 'tasks': [9],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Пробник и его разбор в формате диагностики (1–9) и стратегия экзамена', 'tasks': [],
             'links': [_L('Уроки и материалы', reverse_lazy('lessons_ege'))]},
        ],
    },
    'adv': {
        'level': 'Ваш уровень: уверенный — план с углублением',
        'weeks': [
            {'title': 'Текст, лексика, служебные ЧР и ВК. Задания 1–3', 'tasks': [1, 2, 3],
             'links': [_L('Играть в Домино', DOMINO_URL, ext=True), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Ударения. Задание 4', 'tasks': [4],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Онлайн-словарь ударений', reverse_lazy('orthoepy_trening')), _L('Квизы', reverse_lazy('quizzes_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Паронимы. Задание 5', 'tasks': [5],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Онлайн-словник паронимов'), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Лексические нормы. Задание 6', 'tasks': [6],
             'links': [_L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Грамматические формы (1). Задание 7', 'tasks': [7],
             'links': [_L('Квизы', reverse_lazy('quizzes_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Грамматические формы (2). Ловушки ЕГЭ, сложные случаи', 'tasks': [7],
             'links': [_L('Горячие квизы', reverse_lazy('quizzes_ege')), _L('Тренажёры', reverse_lazy('trainers_ege'))]},
            {'title': 'Г-С нормы. Задание 8. Типы ошибок и примеры', 'tasks': [8],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Орфография. Задание 9. Корни, 3 типа орфограмм', 'tasks': [9],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Орфография. Задание 9. Ловушки', 'tasks': [9],
             'links': [_L('Тренажёры', reverse_lazy('trainers_ege')), _L('Уроки', reverse_lazy('lessons_ege'))]},
            {'title': 'Пробник и его разбор в формате диагностики (1–9) и стратегия экзамена', 'tasks': [],
             'links': [_L('Уроки и материалы', reverse_lazy('lessons_ege'))]},
        ],
    },
}


def build_study_plan(attempt):
    """Выбирает трек плана по вторичному баллу + помечает недели-точки роста."""
    _, secondary = compute_primary_secondary(attempt.answers_data)
    weak = set(attempt.weak_topics or [])

    if secondary < 30:
        track = PLAN_TRACKS['base']
    elif secondary < 79:
        track = PLAN_TRACKS['mid']
    else:
        track = PLAN_TRACKS['adv']

    weeks = []
    for i, w in enumerate(track['weeks'], 1):
        weeks.append({
            'week': i,
            'title': w['title'],
            'links': w['links'],
            'badge': bool(weak & set(w.get('tasks', []))),
        })
    return {'level': track['level'], 'weeks': weeks}



@login_required
def student_review(request, attempt_id):
    """Зеркало ученика: его работа + сводка баллов + личный план + CTA на занятие."""
    attempt = get_object_or_404(DiagnosticAttempt, id=attempt_id)

    # Доступ: только владелец попытки или преподаватель (staff)
    if attempt.user != request.user and not request.user.is_staff:
        return HttpResponseForbidden()

    fixture = load_test_fixture(attempt.test_code)
    work = build_student_work(fixture, attempt.answers_data) if fixture else []
    plan = build_study_plan(attempt)
    primary, secondary = compute_primary_secondary(attempt.answers_data)

    return render(request, 'test_fix_ege/student_review.html', {
        'attempt': attempt,
        'work': work,
        'plan': plan,
        'weak': attempt.weak_topics or [],
        'primary': primary,
        'secondary': secondary,
    })

@csrf_exempt
@login_required
def track_lesson_view(request):
    """Отмечает просмотр урока (раскрытие карточки)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'bad json'}, status=400)
    lesson_code = (data.get('lesson_code') or '').strip()[:100]
    if lesson_code:
        LessonView.objects.get_or_create(user=request.user, lesson_code=lesson_code)
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@login_required
def track_paponim_view(request):
    """Отмечает просмотр карточки паронима."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'bad json'}, status=400)
    paponim_code = (data.get('paponim_code') or '').strip()[:100]
    if paponim_code:
        PaponimView.objects.get_or_create(user=request.user, paponim_code=paponim_code)
    return JsonResponse({'status': 'ok'})


# === БЕЛЫЙ СПИСОК ФАЙЛОВ ДЛЯ СКАЧИВАНИЯ ===
DOWNLOADABLE_FILES = {
    'orthoepy-dict': {
        'filename': 'Орфоэпический_словник_ФИПИ_2027.pdf',
        'display_name': 'Орфоэпический словник ФИПИ 2027',
    },
    'paronyms-dict': {
        'filename': 'Словник_паронимов_ФИПИ.pdf',
        'display_name': 'Словник паронимов ФИПИ',
    },
    # Сюда легко добавить новые файлы:
    # 'stress-dict': {
    #     'filename': 'Словарь_ударений.pdf',
    #     'display_name': 'Словарь ударений',
    # },
}


@login_required
def download_reference_file(request, file_type):
    """
    Универсальная функция скачивания справочных материалов.
    Защищена белым списком — произвольный файл скачать нельзя.
    """
    # 1. Проверяем, что тип файла в белом списке
    file_info = DOWNLOADABLE_FILES.get(file_type)
    if not file_info:
        raise Http404("Файл не найден")
    
    # 2. Формируем путь к файлу
    file_path = os.path.join(
        settings.BASE_DIR,
        'main', 'assistants', 'knowledge_bases', 'russian',
        file_info['filename']
    )
    
    # 3. Проверяем существование файла
    if not os.path.exists(file_path):
        logger.error(f"Файл не найден на диске: {file_path}")
        raise Http404("Файл не найден на сервере")
    
    # 4. Логируем скачивание (полезно для аналитики)
    logger.info(
        f"📥 Скачивание: {file_info['display_name']} | "
        f"Пользователь: {request.user.username} (ID: {request.user.id})"
    )
    
    # 5. Отдаём файл
    return FileResponse(
        open(file_path, 'rb'),
        as_attachment=True,
        filename=file_info['filename'],
        content_type='application/pdf'
    )


# ===== РУБЕЖНЫЕ ТЕСТЫ (ЧЕКПОИНТЫ) ===========================================
CHECKPOINT_MAX_ERRORS = {'cp9': 3}
CHECKPOINT_SESSION = 'checkpoint_9'
CHECKPOINT_FIXTURE_CODE = 'test_fixdiagnostic_ege_2027'
CHECKPOINT_RECOMMEND = {
    '1': ('lessons_ege', 'Уроки 1-3: микротекст и его разбор'),
    '2': ('lessons_ege', 'Уроки 1-3: микротекст и его разбор'),
    '3': ('lessons_ege', 'Уроки 1-3: микротекст и его разбор'),
    '4': ('trainers_ege', 'Тренажёры: орфограммы корней, задание 4'),
    '5': ('paponim_trening', 'Паронимы: словник и тренажёр, задание 5'),
    '6': ('trainers_ege', 'Тренажёры: задание 6'),
    '7': ('trainers_ege', 'Паронимы: словник и задание 7'),
    '8': ('trainers_ege', 'Грамматические основы: задание 8'),
    '9': ('trainers_ege', 'Задание 9: корни и ударения, алфавитные блоки'),
}


def _checkpoint_error_pool(user, exclude=()):
    """Персональный пул слов: ошибки планинга, затем незакрытые ошибки
    задания 9, затем глобально частотные, затем случайные из БД."""
    exclude = set(exclude)
    pool = []
    seen = set()

    def add(ex):
        if ex is None or not ex.is_active or ex.text in seen or ex.text in exclude:
            return
        seen.add(ex.text)
        pool.append(ex)

    uw = (UserWord.objects.filter(user=user, reference_word__isnull=False,
                                  error_count__gt=0)
          .select_related('reference_word').order_by('-error_count'))
    for w in uw:
        add(w.reference_word)

    t9_words = list(Task9WordStat.objects.filter(user=user, in_correction=True)
                    .values_list('word', flat=True))
    if t9_words:
        for ex in OrthogramExample.objects.filter(text__in=t9_words, is_active=True):
            add(ex)

    if len(pool) < 6:
        for ex in OrthogramExample.objects.filter(is_active=True).order_by('-difficulty')[:40]:
            add(ex)
    return pool


def _mask_to_gap(masked_word):
    import re as _re
    return _re.sub(r'\*\d+\*', '…', masked_word)


def _build_checkpoint_task4(user, exclude):
    """Задание 4: 5 строк слов, в 3 пропущена одна и та же буква."""
    from collections import Counter
    pool = _checkpoint_error_pool(user, exclude)
    cnt = Counter()
    for ex in pool:
        letters = [c.strip().lower() for c in (ex.correct_letters or '').split(',')]
        if len(letters) == 1 and letters[0]:
            cnt[letters[0]] += 1
    letter = cnt.most_common(1)[0][0] if cnt else 'а'
    same = [e for e in pool if [c.strip().lower() for c in (e.correct_letters or '').split(',')] == [letter]]
    other = [e for e in pool if e not in same]
    import random
    random.shuffle(same)
    random.shuffle(other)
    chosen_same = same[:3]
    chosen_other = other[:2]
    if len(chosen_same) < 3 or len(chosen_other) < 2:
        return None
    lines = [( _mask_to_gap(e.masked_word), True, e) for e in chosen_same]
    lines += [(_mask_to_gap(e.masked_word), False, e) for e in chosen_other]
    random.shuffle(lines)
    choices = [ln[0] for ln in lines]
    correct = [str(i + 1) for i, ln in enumerate(lines) if ln[1]]
    words = [(ln[2].text, ln[2].orthogram_id, ln[1]) for ln in lines]
    return choices, correct, words, letter


def _paponim_to_html(text):
    import re as _re
    return _re.sub(r'\*\*(.+?)\*\*', r'<u>\1</u>', text)


def _build_checkpoint_task5(user, exclude_roots=()):
    """Задание 5: паронимы — 1 предложение с ошибкой + 4 корректных,
    как в тренажёре (тот же пул TaskPaponim, исключение одинаковых корней)."""
    import random
    exclude_roots = {r for r in exclude_roots if r}
    for quiz_only in (True, False):
        base = TaskPaponim.objects.filter(is_active=True)
        if quiz_only:
            base = base.filter(is_for_quiz=True)
        erroneous_qs = base.exclude(correct_word='')
        if exclude_roots:
            filtered = erroneous_qs.exclude(root__in=exclude_roots)
            if filtered.exists():
                erroneous_qs = filtered
        erroneous = erroneous_qs.order_by('?').first()
        if erroneous is None:
            continue
        correct_qs = base.filter(correct_word='')
        if erroneous.root:
            correct_qs = correct_qs.exclude(root=erroneous.root)
        correct_list = list(correct_qs.order_by('?')[:4])
        if len(correct_list) < 4:
            continue
        sentences = [erroneous] + correct_list
        random.shuffle(sentences)
        lines = [_paponim_to_html(x.text) for x in sentences]
        return lines, erroneous.correct_word.lower().strip(), erroneous.root
    return None


@subscription_required('lessons')
def checkpoint_test(request):
    """Рубежный тест после урока 9 (открывает урок 10). 9 заданий, допуск 3 ошибки."""
    if request.method == 'POST':
        return _checkpoint_check(request)

    context, test_data = _build_test_fix_context(request, CHECKPOINT_FIXTURE_CODE)
    if context is not None:
        moved = request.session.pop(f'{CHECKPOINT_FIXTURE_CODE}_correct', None)
        if moved is not None:
            request.session[f'{CHECKPOINT_SESSION}_correct'] = moved
        moved8 = request.session.pop(f'{CHECKPOINT_FIXTURE_CODE}_task8_matches', None)
        if moved8 is not None:
            request.session[f'{CHECKPOINT_SESSION}_task8_matches'] = moved8
    if context is None:
        return render(request, 'test_fix_ege/checkpoint_test.html', {
            'message': 'Рубежный тест временно недоступен.'})

    used = []
    used_roots = []
    for a in CheckpointAttempt.objects.filter(user=request.user, checkpoint_code='cp9'):
        used += [w.get('word') for w in (a.words_data or [])]
        used_roots += [w.get('root') for w in (a.words_data or []) if w.get('root')]

    t4 = _build_checkpoint_task4(request.user, used)
    t5 = _build_checkpoint_task5(request.user, used_roots)
    cp_words = []
    if t4:
        choices, correct, words, letter = t4
        context['task4_text'] = ('Укажите варианты ответов, в которых пропущена одна '
                                 'и та же буква (номера строк без пробелов):')
        context['task4_choices'] = choices
        context['cp4_words'] = words
        cp_words += [{'task': 4, 'word': w[0], 'orthogram_id': w[1], 'is_target': w[2]}
                     for w in words]
    if t5:
        lines5, answer5, root5 = t5
        context['task5_text'] = ('В одном из приведённых ниже предложений НЕВЕРНО '
                                 'употреблено выделенное слово. Исправьте лексическую '
                                 'ошибку, подобрав к выделенному слову пароним.')
        context['task5_sentences'] = lines5
        cp_words.append({'task': 5, 'word': answer5, 'root': root5, 'is_target': True})

    correct = request.session.get(f'{CHECKPOINT_SESSION}_correct', {})
    if t4:
        correct['4'] = correct_list = t4[1]
    if t5:
        correct['5'] = t5[1]
    request.session[f'{CHECKPOINT_SESSION}_correct'] = correct
    request.session[f'{CHECKPOINT_SESSION}_words'] = cp_words
    request.session.modified = True

    context.update({
        'cp_passed_already': CheckpointAttempt.objects.filter(
            user=request.user, checkpoint_code='cp9', passed=True).exists(),
        'max_errors': CHECKPOINT_MAX_ERRORS['cp9'],
    })
    return render(request, 'test_fix_ege/checkpoint_test.html', context)


def _checkpoint_check(request):
    try:
        data = json.loads(request.body)
        user_answers = data.get('answers', {})
    except Exception:
        return JsonResponse({'error': 'Некорректные данные'}, status=400)

    correct = request.session.get(f'{CHECKPOINT_SESSION}_correct', {})
    task8_matches = request.session.get(f'{CHECKPOINT_SESSION}_task8_matches', {})
    cp_words = request.session.get(f'{CHECKPOINT_SESSION}_words', [])
    if not correct:
        return JsonResponse({'error': 'Сессия устарела, обновите страницу'}, status=400)

    def norm(v):
        return str(v).strip().lower()

    results = {}
    for t in ('1', '2', '3', '5', '6', '7'):
        ca = correct.get(t)
        ua = user_answers.get(t, '')
        if isinstance(ua, list):
            want = {norm(x) for x in ca} if isinstance(ca, list) else {norm(ca)}
            results[t] = {norm(x) for x in ua} == want
        elif isinstance(ca, list):
            results[t] = norm(ua) in {norm(x) for x in ca}
        else:
            results[t] = norm(ua) == norm(ca)

    ca4 = correct.get('4', [])
    ua4 = user_answers.get('4', '')
    user_set = {x.strip() for x in str(ua4).replace(',', ' ').split() if x.strip()}
    results['4'] = user_set == set(ca4)

    ok8 = 0
    for letter in ('А', 'Б', 'В', 'Г', 'Д'):
        letter_ok = (norm(user_answers.get(f'8_{letter}', ''))
                     == norm(task8_matches.get(letter, '')))
        results[f'8_{letter}'] = bool(task8_matches) and letter_ok
        if letter_ok:
            ok8 += 1
    results['8'] = bool(task8_matches) and ok8 == 5

    # Задание 9: подответы вида '9-1', '9-2' (смайлики)
    t9_keys = [k for k in correct if str(k).startswith('9-')]
    err9 = 0
    for k in t9_keys:
        ok = norm(user_answers.get(k, '')) == norm(correct.get(k))
        results[k] = ok
        if not ok:
            err9 += 1
    results['9'] = bool(t9_keys) and err9 == 0

    # Ошибки считаем как есть, без экзаменных баллов: задания 1-7 — по одной,
    # задание 8 — по несобранным позициям соответствия, задание 9 — по строкам.
    err_simple = sum(1 for t in ('1', '2', '3', '4', '5', '6', '7')
                     if not results.get(t))
    err8 = (5 - ok8) if task8_matches else (0 if results['8'] else 1)
    error_count = err_simple + err8 + err9
    correct_count = sum(1 for t in '123456789' if results.get(t))
    passed = error_count <= CHECKPOINT_MAX_ERRORS['cp9']

    words_data = []
    for w in cp_words:
        words_data.append(dict(w))
    for t in ('1', '2', '3', '4', '5', '6', '7', '8', '9'):
        words_data.append({'task': int(t), 'word': '', 'orthogram_id': '',
                           'correct': bool(results.get(t))})

    attempt = CheckpointAttempt.objects.create(
        user=request.user, checkpoint_code='cp9',
        correct_count=correct_count, error_count=error_count, passed=passed,
        answers_data=user_answers,
        results_data={k: {'correct': v} for k, v in results.items()},
        words_data=words_data,
    )
    logger.info(f'Чекпоинт cp9: user={request.user.username} '
                f'{correct_count}/8 passed={passed}')
    return JsonResponse({
        'result_url': reverse('checkpoint_result', args=[attempt.id]),
        'results': {k: {'is_correct': bool(v)} for k, v in results.items()},
        'error_count': error_count,
        'passed': passed,
    })


@subscription_required('lessons')
def checkpoint_result(request, attempt_id):
    attempt = get_object_or_404(CheckpointAttempt, id=attempt_id,
                                user=request.user, checkpoint_code='cp9')
    recommend = []
    for t in ('1', '2', '3', '4', '5', '6', '7', '8', '9'):
        res = (attempt.results_data or {}).get(t, {})
        if not res.get('correct'):
            url_name, label = CHECKPOINT_RECOMMEND[t]
            recommend.append({'task': t, 'label': label, 'url': reverse(url_name)})
    return render(request, 'test_fix_ege/checkpoint_result.html', {
        'attempt': attempt,
        'max_errors': CHECKPOINT_MAX_ERRORS['cp9'],
        'recommend': recommend,
    })
