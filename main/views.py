# main/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.sites.shortcuts import get_current_site
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import re
import json
import logging
from .forms import CustomUserCreationForm, ProfileForm
from .models import UserExample, UserProfile, OrthogramExample, Orthogram, StudentAnswer
from .assistant import NeuroAssistant



logger = logging.getLogger('django')


# === Утилиты ===


def extract_correct_letter(text, masked_word):
    """
    Извлекает символ из text по позиции маски *N* в masked_word.
    Поддерживает: '/', '\\' (раздельно), 'ъ', 'ь' и др.
    """
    try:
        mask_match = re.search(r'\*\d+\*', masked_word)
        if not mask_match:
            return ''

        words_text = text.split()
        words_mask = masked_word.split()

        for i, word_mask in enumerate(words_mask):
            if '*' in word_mask:
                if i >= len(words_text):
                    return ''
                word_text = words_text[i]
                pos = word_mask.index('*')
                if pos < len(word_text):
                    return word_text[pos]
        return ''
    except Exception as e:
        print(f"Ошибка в extract_correct_letter: {e}")
        return ''



# def extract_correct_letter(text, masked_word):
#     """Извлекает правильную букву или символ по позиции маски *N*."""
#     try:
#         match = re.search(r'\*\d+\*', masked_word)
#         if not match:
#             return ''
#         words_in_text = text.split()
#         words_in_masked = masked_word.split()
#         for i, masked_w in enumerate(words_in_masked):
#             if '*' in masked_w and i < len(words_in_text):
#                 mask_match = re.search(r'\*\d+\*', masked_w)
#                 if mask_match:
#                     pos = mask_match.start()
#                     orig_word = words_in_text[i]
#                     if pos < len(orig_word):
#                         return orig_word[pos]
#         return text[0] if text else ''
#     except Exception as e:
#         print(f"Ошибка в extract_correct_letter: {e}")
#         return ''


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


# === Основные представления ===

def index(request):
    return render(request, 'index.html')


def planning_5kl(request):
    return render(request, 'planning_5kl.html')


def planning_6kl(request):
    return render(request, 'planning_6kl.html')


def planning_7kl(request):
    return render(request, 'planning_7kl.html')


def ege(request):
    return render(request, 'ege.html')


# === Аутентификация и профиль ===

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.is_active = False
                user.save()

                current_site = get_current_site(request)
                mail_subject = 'Активируйте ваш аккаунт'
                message = render_to_string('registration/confirm_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': default_token_generator.make_token(user),
                })
                send_mail(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
                messages.success(request, 'Письмо с подтверждением отправлено на вашу почту!')
                return redirect('login')
            except Exception as e:
                logger.error(f"Ошибка при регистрации: {e}")
                messages.error(request, "Произошла ошибка при регистрации. Попробуйте позже.")
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


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
        login(request, user)
        return redirect('index')
    else:
        return render(request, 'registration/invalid_link.html')


@login_required
def profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные успешно сохранены!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'profile.html', {'form': form})


# === API: примеры и данные упражнений ===

@login_required
def save_example(request):
    if request.method == 'POST':
        field_name = request.POST.get('field_name')
        content = request.POST.get('content', '')
        UserExample.objects.update_or_create(
            user=request.user,
            field_name=field_name,
            defaults={'content': content}
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def load_examples(request):
    examples = UserExample.objects.filter(user=request.user).values('field_name', 'content')
    return JsonResponse({item['field_name']: item['content'] for item in examples})


def get_orthogram_letters(request, orth_id):
    try:
        orth = Orthogram.objects.get(id=orth_id)
        letters = [letter.strip() for letter in orth.letters.split(',') if letter.strip()]
        return JsonResponse({'letters': letters})
    except Orthogram.DoesNotExist:
        return JsonResponse({'letters': ['а', 'о', 'е', 'и', 'я']}, status=404)
    except Exception as e:
        logger.error(f"Ошибка при загрузке букв для орфограммы {orth_id}: {e}")
        return JsonResponse({'letters': ['а', 'о', 'е', 'и', 'я']}, status=500)


# === Генерация упражнений ===
@login_required
def generate_exercise(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        orthogram_ids = validate_orthogram_ids(data.get('orthogram_ids', []))
        if not orthogram_ids:
            return JsonResponse({'error': 'Нет корректных ID орфограмм'}, status=400)

        TASK_13_ORTHOGRAMS = {21, 32, 36, 46, 54, 56, 57, 58, 581, 582}
        is_task_13 = set(orthogram_ids).issubset(TASK_13_ORTHOGRAMS)
        total_needed = 5 if is_task_13 else 16

        # Сбор примеров
        user_examples = OrthogramExample.objects.filter(
            orthogram_id__in=orthogram_ids,
            is_user_added=True,
            added_by=request.user,
            is_active=True
        ).order_by('?')[:total_needed]

        remaining = total_needed - user_examples.count()
        common_examples = OrthogramExample.objects.filter(
            orthogram_id__in=orthogram_ids,
            is_user_added=False,
            is_active=True
        ).order_by('?')[:remaining]

        all_examples = list(user_examples) + list(common_examples)
        if not all_examples:
            return JsonResponse({'error': 'Нет доступных слов'}, status=404)

        # Режим по строкам (только для одной орфограммы из TASK_13)
        SPLIT_NE_ORTHOGRAMS = {21, 32, 36, 46, 54, 56, 57, 58, 581, 582}
        is_ne_split_lines = (len(orthogram_ids) == 1 and orthogram_ids[0] in SPLIT_NE_ORTHOGRAMS)

        if is_ne_split_lines:
            words_lines = [ex.masked_word.strip() for ex in all_examples]
            words_text = None
        else:
            words_text = ', '.join(ex.masked_word.strip() for ex in all_examples)
            words_lines = None

        # ← УБРАНО всё про 1400
        correct_letters = [extract_correct_letter(ex.text, ex.masked_word) for ex in all_examples]

        request.session['current_exercise'] = {
            'exercise_id': f'dynamic_{",".join(map(str, orthogram_ids))}',
            'example_ids': [ex.id for ex in all_examples],
            'correct_letters': correct_letters,
            'orthogram_ids': orthogram_ids,
        }

        title_map = {
            '1': 'Безударные гласные',
            '661': 'Производные предлоги',
            '662': 'Производные предлоги',
            '13': 'Слитное, раздельное, дефисное написание',
            '14': 'Слитное, раздельное, дефисное написание'
        }
        exercise_title = title_map.get(str(orthogram_ids[0]), 'Упражнение')
        show_next_button = str(orthogram_ids[0]) not in {'1', '2'}

        html = render_to_string('exercise_snippet.html', {
            'words_text': words_text,
            'words_lines': words_lines,
            'is_orth21_lines': is_ne_split_lines,
            'exercise_id': request.session['current_exercise']['exercise_id'],
            'exercise_title': exercise_title,
            'show_next_button': show_next_button,
        })
        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка в generate_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


@login_required
def generate_alphabetical_exercise(request):
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

        examples = OrthogramExample.objects.filter(
            orthogram_id=orthogram_id_int,
            is_active=True
        ).order_by('masked_word')

        def get_first_cyrillic_char(word):
            match = re.search(r'[А-ЯЁ]', word.upper())
            return match.group(0) if match else None

        filtered_examples = [
            ex for ex in examples
            if (first_char := get_first_cyrillic_char(ex.masked_word))
            and start_letter <= first_char <= end_letter
        ]

        if not filtered_examples:
            return JsonResponse({'error': 'Нет слов в указанном диапазоне'}, status=404)

        words_text = ', '.join(ex.masked_word for ex in filtered_examples)
        correct_letters = [extract_correct_letter(ex.text, ex.masked_word) for ex in filtered_examples]

        request.session['current_exercise'] = {
            'exercise_id': f'alphabetical_{orthogram_id}_{range_code}',
            'correct_words': [ex.masked_word for ex in filtered_examples],
            'correct_letters': correct_letters,
            'orthogram_id': orthogram_id,
            'range_code': range_code,
        }

        prefix = config[orthogram_id]['title_prefix']
        range_labels = {
            'A-O': 'А-О', 'P-S': 'П-С', 'T-YA': 'Т-Я',
            'A-D': 'А-Д', 'E-K': 'Е-К', 'L-R': 'Л-Р', 'S-YA': 'С-Я'
        }
        range_label = range_labels.get(range_code, range_code)
        exercise_title = f"{prefix} {range_label}"

        html = render_to_string('exercise_snippet.html', {
            'words_text': words_text,
            'exercise_id': request.session['current_exercise']['exercise_id'],
            'exercise_title': exercise_title,
            'show_next_button': False,
        })
        return JsonResponse({'html': html})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)
    except Exception as e:
        logger.error(f"Ошибка в generate_alphabetical_exercise: {e}")
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)


# === Проверка и обратная связь (стабильная версия) ===
@csrf_exempt
@login_required
def check_exercise(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        user_letters = data.get('user_words', [])
        if not isinstance(user_letters, list):
            return JsonResponse({'error': 'Некорректный формат данных'}, status=400)

        current_exercise = request.session.get('current_exercise')
        if not current_exercise:
            return JsonResponse({'error': 'Нет активного упражнения'}, status=400)

        correct_letters = current_exercise.get('correct_letters', [])
        if len(user_letters) != len(correct_letters):
            return JsonResponse({'error': 'Несоответствие количества ответов'}, status=400)

        results = []
        for user_letter, correct_letter in zip(user_letters, correct_letters):
            # Сравниваем как есть — без .lower()
            is_correct = user_letter.strip() == correct_letter.strip()
            results.append(is_correct)

        return JsonResponse(results, safe=False)

    except Exception as e:
        logger.error(f"Ошибка в check_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка проверки'}, status=500)


@csrf_exempt
def get_advice(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    try:
        data = json.loads(request.body)
        user_words = data.get('user_words', [])
        assistant = NeuroAssistant(request.user.id)
        analysis = assistant.analyze_current_exercise(user_words)
        advice_text = assistant.generate_advice_for_exercise(analysis)
        return JsonResponse({'advice': advice_text})
    except Exception as e:
        logger.warning(f"Ошибка в get_advice: {e}")
        return JsonResponse({'advice': "Спасибо за выполнение! Продолжай в том же духе."})


@login_required
def get_assistant_data(request):
    assistant = NeuroAssistant(request.user.id)
    action = request.GET.get('action', 'daily_question')
    handlers = {
        'daily_question': assistant.get_daily_question,
        'progress': assistant.get_progress_summary,
        'weak': assistant.get_weak_orthograms,
        'planning': assistant.get_planning_words,
    }
    data = handlers.get(action, lambda: {"error": "Неизвестное действие"})()
    return JsonResponse(data)


# === Telegram и отчёты ===

@login_required
def telegram_link(request):
    token = request.GET.get('token')
    telegram_id = request.GET.get('telegram_id')
    if not token or not telegram_id:
        return HttpResponse("Неверная ссылка", status=400)
    try:
        profile = request.user.profile
        profile.telegram_id = telegram_id
        profile.telegram_username = request.GET.get('username', '')
        profile.save()
        messages.success(request, "Telegram успешно привязан!")
    except Exception as e:
        messages.error(request, "Ошибка привязки.")
    return redirect('profile')


@csrf_exempt
def weekly_report(request):
    try:
        data = json.loads(request.body)
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return JsonResponse({'error': 'Нет telegram_id'}, status=400)
        profile = UserProfile.objects.get(telegram_id=telegram_id)
        week_ago = timezone.now() - timezone.timedelta(days=7)
        answers = StudentAnswer.objects.filter(
            user=profile.user,
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
    except UserProfile.DoesNotExist:
        return JsonResponse({
            'status': 'inactive',
            'message': 'Твой Telegram не привязан к аккаунту. Зайди в ЛК на сайте и подпишись на бота.'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# === отчёты для ЛК ===

@login_required
def get_weekly_report(request):
    """Для отображения в ЛК (через GET, с авторизацией)"""
    from django.utils import timezone
    
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
    


@csrf_exempt
def get_daily_quiz(request):
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        if not user_id:
            return JsonResponse({'error': 'Нет user_id'}, status=400)
        assistant = NeuroAssistant(user_id=1)  # TODO: заменить на реальный user_id после интеграции
        quiz = assistant.get_quiz_question()
        if not quiz:
            return JsonResponse({'error': 'Нет вопросов'}, status=404)
        return JsonResponse(quiz)
    except Exception as e:
        logger.error(f"Ошибка в get_daily_quiz: {e}")
        return JsonResponse({'error': 'Ошибка генерации вопроса'}, status=500)
    
    

def parse_words_from_text(text):
    """Извлекает отдельные слова или конструкции из текста."""
    # Убираем лишние символы, разбиваем по запятым/пробелам
    words = re.split(r'[,;\n\r]+', text)
    return [w.strip() for w in words if w.strip()]


@login_required
def save_example(request):
    if request.method == 'POST':
        field_name = request.POST.get('field_name')
        content = request.POST.get('content', '').strip()
        
        # Сохраняем в UserExample (как раньше)
        UserExample.objects.update_or_create(
            user=request.user,
            field_name=field_name,
            defaults={'content': content}
        )

        # === НОВОЕ: Парсим и создаём OrthogramExample ===
        if content and field_name.startswith('user-input-orf-'):
            try:
                # Извлекаем номер орфограммы: user-input-orf-711 → 711
                orth_id = field_name.replace('user-input-orf-', '')
                
                # Находим орфограмму
                orthogram = Orthogram.objects.get(id=orth_id)
                
                # Удаляем старые пользовательские примеры для этого поля
                OrthogramExample.objects.filter(
                    added_by=request.user,
                    source_field=field_name,
                    is_user_added=True
                ).delete()

                # Парсим слова и создаём новые
                words = parse_words_from_text(content)
                for word in words:
                    # Создаём "маску" — можно просто использовать слово целиком
                    # Или реализовать логику маскирования (например, для гласных)
                    OrthogramExample.objects.create(
                        orthogram=orthogram,
                        text=word,
                        masked_word=word,  # ← можно улучшить: сделать маску *N*
                        is_active=True,
                        is_user_added=True,
                        added_by=request.user,
                        source_field=field_name
                    )
            except Orthogram.DoesNotExist:
                pass  # Игнорируем, если орфограмма не найдена

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)