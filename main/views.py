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
from .models import UserExample, UserProfile, OrthogramExample, Orthogram, StudentAnswer, Punktum, PunktumExample, TextAnalysisTask, TextQuestion, QuestionOption, OrthoepyWord, CorrectionExercise
from .assistant import NeuroAssistant
import random
from random import sample



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


# === Генерация упражнений ОРФОГРАММ 1 маска ===
logger = logging.getLogger(__name__)

@login_required
def generate_exercise(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        orthogram_ids = validate_orthogram_ids(data.get('orthogram_ids', []))
        if not orthogram_ids:
            return JsonResponse({'error': 'Нет корректных ID орфограмм'}, status=400)

        # === Тип задания ===
        TASK_13_ORTHOGRAMS = {21, 32, 36, 46, 54, 56, 57, 58, 581, 582}
        is_task_13 = set(orthogram_ids).issubset(TASK_13_ORTHOGRAMS)
        is_task_14 = orthogram_ids == [1400]
        is_multi_sentence_task = is_task_13 or is_task_14
        total_needed = 5 if is_multi_sentence_task else 16

        # === Сбор примеров ===
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

        # === Формат отображения ===
        is_ne_split_lines = is_multi_sentence_task
        if is_ne_split_lines:
            words_lines = [ex.masked_word.strip() for ex in all_examples]
            words_text = None
        else:
            words_text = ', '.join(ex.masked_word.strip() for ex in all_examples)
            words_lines = None

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

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)
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

        examples = OrthogramExample.objects.filter(
            orthogram_id=orthogram_id,
            is_active=True
        ).order_by('?')[:total_needed]

        if not examples:
            return JsonResponse({'error': f'Нет примеров для орфограммы {orthogram_id}'}, status=404)

        correct_letters = []
        valid_examples = []

        for ex in examples:
            mask_count = len(re.findall(rf'\*{orthogram_id}\*', ex.masked_word))
            explanation_text = (ex.explanation or '').strip()
            
            # Обработка explanation в зависимости от типа задания
            if orthogram_id == 1400:
                # Для задания 14: "/-" -> ["/", "-"]
                if explanation_text == '/-':
                    parts = ['/', '-']
                else:
                    parts = [p.strip() for p in explanation_text.split(',') if p.strip()]
            elif orthogram_id == 1500:
                # Для задания 15: "н,нн,н" -> ["н", "нн", "н"]
                parts = [p.strip() for p in explanation_text.split(',') if p.strip()]

            if mask_count == len(parts) and mask_count > 0:
                correct_letters.append(parts)
                valid_examples.append(ex)

        if not valid_examples:
            return JsonResponse({'error': 'Нет корректных примеров с explanation'}, status=400)

        exercise_id = f'multi_{orthogram_id}'
        title = 'Задание 14' if orthogram_id == 1400 else 'Задание 15'
        
        request.session['current_exercise'] = {
            'exercise_id': exercise_id,
            'example_ids': [ex.id for ex in valid_examples],
            'correct_letters': correct_letters,
            'orthogram_ids': [orthogram_id],
        }

        words_lines = [ex.masked_word for ex in valid_examples]
        
        html = render_to_string('exercise_snippet.html', {
            'words_lines': words_lines,
            'words_text': None,
            'is_orth21_lines': True,
            'exercise_id': exercise_id,
            'exercise_title': title,
            'show_next_button': False,
        })

        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка в generate_exercise_multi: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка сервера'}, status=500)
    

# === Генерация упражнений на 1 ПУНКТОГРАММУ (задания 16–21) ===
# @login_required
# def generate_punktum_exercise(request):
#     if request.method != 'POST':
#         return JsonResponse({'error': 'Только POST'}, status=405)

#     try:
#         data = json.loads(request.body)
#         orthogram_ids = data.get('orthogram_ids', [])

#         # Поддерживаем только 1600, 1700, ..., 2100
#         PUNKTUM_TASKS = {'1600', '1700', '1800', '1900', '2000', '2100'}

#         if not set(orthogram_ids).issubset(PUNKTUM_TASKS):
#             return JsonResponse({'error': 'Поддерживаются только задания 16–21'}, status=400)

#         # Определяем количество примеров по ID задания
#         task_id = orthogram_ids[0]  # '1600', '1700', и т.д.
        
#         if task_id == '1600':
#             # Задание 16 - 5 примеров-предложений
#             total_needed = 5
#         else:
#             # Задания 17, 18, 19, 20 - 1 пример-предложение
#             total_needed = 1

#         examples = PunktumExample.objects.filter(
#             punktum__id__in=orthogram_ids,
#             is_active=True
#         ).order_by('?')[:total_needed]

#         if not examples:
#             return JsonResponse({'error': 'Нет доступных пунктуационных примеров'}, status=404)

#         correct_letters = []
#         valid_examples = []

#         for ex in examples:
#             key = ex.explanation.strip() if ex.explanation else ''
#             if not key:
#                 continue

#             parts = [part.strip() for part in key.split(',') if part.strip()]
#             mask_count = len(re.findall(r'\*\d+\*', ex.masked_word))

#             if mask_count != len(parts):
#                 continue

#             correct_letters.extend(parts)
#             valid_examples.append(ex)

#         if not valid_examples:
#             return JsonResponse({'error': 'Нет корректных пунктуационных примеров'}, status=400)

#         # Сохраняем в сессию
#         request.session['current_exercise'] = {
#             'exercise_id': f'punktum_{",".join(orthogram_ids)}',
#             'example_ids': [ex.id for ex in valid_examples],
#             'correct_letters': correct_letters,
#             'orthogram_ids': orthogram_ids,
#         }

#         # ДЛЯ ЗАДАНИЯ 18 (1800) - разбиваем на абзацы
#         # Для остальных - оставляем как было
#         task_num = task_id[:2]  # '16', '18'
        
#         if task_id == '1800':  # Только для задания 18
#             # Структурированный формат с абзацами
#             structured_examples = []
#             for ex in valid_examples:
#                 # Разбиваем на абзацы по символу новой строки
#                 paragraphs = [p.strip() for p in ex.masked_word.split('\n') if p.strip()]
#                 structured_examples.append(paragraphs)
            
#             html = render_to_string('exercise_snippet.html', {
#                 'structured_examples': structured_examples,
#                 'is_punktum_exercise': True,
#                 'is_punktum_with_paragraphs': True,  # Флаг для абзацев
#                 'exercise_id': f'punktum_{",".join(orthogram_ids)}',
#                 'exercise_title': f'Задание № {task_num}',
#                 'show_next_button': False,
#                 'words_lines': None,
#                 'words_text': None,
#                 'is_orth21_lines': False,
#             })
#         else:
#             # Старый формат для остальных заданий (16, 17, 19, 20)
#             words_lines = [ex.masked_word.strip() for ex in valid_examples]
            
#             html = render_to_string('exercise_snippet.html', {
#                 'words_lines': words_lines,
#                 'words_text': None,
#                 'is_orth21_lines': True,
#                 'is_punktum_exercise': True,
#                 'is_punktum_with_paragraphs': False,  # Без абзацев
#                 'exercise_id': f'punktum_{",".join(orthogram_ids)}',
#                 'exercise_title': f'Задание № {task_num}',
#                 'show_next_button': False,
#             })

#         return JsonResponse({'html': html})

#     except Exception as e:
#         logger.error(f"Ошибка в generate_punktum_exercise: {e}", exc_info=True)
#         return JsonResponse({'error': 'Ошибка генерации упражнения'}, status=500)


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
    Генерирует упражнение с НЕСКОЛЬКИМИ масками в одном предложении (Задания 16–21).
    Каждый пример разбивается на абзацы для лучшего отображения.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body)
        orthogram_ids = data.get('orthogram_ids', [])

        # Поддерживаем 1600, 1700, ..., 2100
        PUNKTUM_MULTI_TASKS = {'1600', '1700', '1800', '1900', '2000', '2100'}
        if not set(orthogram_ids).issubset(PUNKTUM_MULTI_TASKS):
            return JsonResponse({'error': 'Поддерживаются только задания 16–21'}, status=400)

        # Берём первую (и единственную) ID — например, ['1600'] → '1600'
        punktum_id = orthogram_ids[0]

        # Определяем количество примеров по ID задания
        if punktum_id == '1600':
            # Задание 16 - 5 примеров-предложений
            total_needed = 5
        else:
            # Задания 17, 18, 19, 20 - 1 пример-предложение
            total_needed = 1

        # Ищем примеры
        examples = PunktumExample.objects.filter(
            punktum__id=punktum_id,
            is_active=True
        ).order_by('?')[:total_needed]

        if not examples:
            return JsonResponse({'error': f'Нет примеров для пунктограммы {punktum_id}'}, status=404)

        correct_letters = []  # Будет: [['!', '!'], ['?']]
        valid_examples = []

        for ex in examples:
            explanation_text = (ex.explanation or '').strip()
            if not explanation_text:
                continue

            # Разбиваем explanation на части: "!,!" → ["!", "!"]
            parts = [p.strip() for p in explanation_text.split(',') if p.strip()]
            mask_count = len(re.findall(rf'\*{punktum_id}\*', ex.masked_word))

            if mask_count == len(parts) and mask_count > 0:
                correct_letters.append(parts)  # ← список списков!
                valid_examples.append(ex)

        if not valid_examples:
            return JsonResponse({'error': 'Нет корректных примеров с explanation'}, status=400)

        # Сохраняем в сессию (для check_exercise)
        request.session['current_exercise'] = {
            'exercise_id': f'punktum_multi_{punktum_id}',
            'example_ids': [ex.id for ex in valid_examples],
            'correct_letters': correct_letters,  # ← список списков
            'orthogram_ids': [punktum_id],
        }

        # Структурируем примеры: список примеров, каждый пример - список абзацев
        structured_examples = []
        for ex in valid_examples:
            # Разбиваем masked_word на абзацы по символу новой строки
            # Фильтруем пустые строки
            paragraphs = [p.strip() for p in ex.masked_word.split('\n') if p.strip()]
            structured_examples.append(paragraphs)

        task_num = punktum_id[:2]  # '1600' → '16'
        
        # Генерация HTML с новой структурой
        html = render_to_string('exercise_snippet.html', {
            'structured_examples': structured_examples,  # Новая структура
            'is_punktum_exercise': True,                 # Флаг для шаблона
            'exercise_id': f'punktum_multi_{punktum_id}',
            'exercise_title': f'Задание № {task_num}',
            'show_next_button': False,
            'words_lines': None,      # Не используем
            'words_text': None,       # Не используем
            'is_orth21_lines': False, # Не используем старую логику
        })

        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка в generate_punktum_exercise_multi: {e}", exc_info=True)
        return JsonResponse({'error': 'Ошибка сервера'}, status=500)



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
        
        print(f"🔍 CHECK: is_multi_mask = {is_multi_mask}")  # ОТЛАДКА
        print(f"🔍 CHECK: user_letters = {user_letters}")  # ОТЛАДКА
        print(f"🔍 CHECK: correct_letters = {correct_letters}")  # ОТЛАДКА
        
        if is_multi_mask:
            # correct_letters = [['нн', 'н', 'нн', 'нн', 'н', 'н']] - список списков
            # user_letters = ['н', 'н', 'нн', 'нн', 'н', 'н'] - плоский список
            results = []
            user_index = 0
            
            print(f"🔍 MULTI: Обрабатываем {len(correct_letters)} примеров")  # ОТЛАДКА
            
            for example_index, example_letters in enumerate(correct_letters):
                print(f"🔍 MULTI: Пример {example_index}: {example_letters}")  # ОТЛАДКА
                example_results = []
                for correct_letter in example_letters:
                    if user_index >= len(user_letters):
                        example_results.append(False)
                        print(f"❌ MULTI: Не хватает ответов пользователя")  # ОТЛАДКА
                    else:
                        user_clean = user_letters[user_index].strip()
                        correct_clean = correct_letter.strip()  # ← ЭТО РАБОТАЕТ, потому что correct_letter теперь строка
                        is_correct = user_clean == correct_clean
                        example_results.append(is_correct)
                        print(f"🔍 MULTI: Сравниваем '{user_clean}' == '{correct_clean}' → {is_correct}")  # ОТЛАДКА
                        user_index += 1
                results.extend(example_results)
            
            print(f"🔍 MULTI: Итоговые результаты: {results}")  # ОТЛАДКА
            
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
                logger.debug(f"Позиция {i}: '{user_clean}' == '{correct_clean}' → {is_correct}")

        logger.info(f"Итоговые результаты: {results}")
        return JsonResponse(results, safe=False)

    except json.JSONDecodeError:
        logger.error("Ошибка декодирования JSON из тела запроса")
        return JsonResponse({'error': 'Некорректный JSON'}, status=400)
    except Exception as e:
        logger.error(f"Критическая ошибка в check_exercise: {e}", exc_info=True)
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
        UserExample.objects.update_or_create(
            user=request.user,
            field_name=field_name,
            defaults={'content': content}
        )
        
        # === Сохранение ОРФОГРАММ ===
        if content and field_name.startswith('user-input-orf-'):
            try:
                orth_id = field_name.replace('user-input-orf-', '')
                orthogram = Orthogram.objects.get(id=orth_id)
                OrthogramExample.objects.filter(
                    added_by=request.user,
                    source_field=field_name,
                    is_user_added=True
                ).delete()
                words = parse_words_from_text(content)
                for word in words:
                    OrthogramExample.objects.create(
                        orthogram=orthogram,
                        text=word,
                        masked_word=word,
                        is_active=True,
                        is_user_added=True,
                        added_by=request.user,
                        source_field=field_name
                    )
            except Orthogram.DoesNotExist:
                pass

        # === СОХРАНЕНИЕ ПУНКТОГРАММ ===
        elif content and field_name.startswith('user-input-punktum-'):
            try:
                # user-input-punktum-2 → '16' (согласно вашей логике: 2 = задание 16)
                # ИЛИ: user-input-punktum-16 → '16' (лучше!)
                # Предположим, что вы используете ID напрямую: user-input-punktum-16
                punktum_id = field_name.replace('user-input-punktum-', '')
                punktum = Punktum.objects.get(id=punktum_id)
                
                PunktumExample.objects.filter(
                    added_by=request.user,
                    source_field=field_name,
                    is_user_added=True
                ).delete()
                
                sentences = [s.strip() for s in content.split('\n') if s.strip()]
                for sent in sentences:
                    PunktumExample.objects.create(
                        punktum=punktum,
                        text=sent,
                        masked_word=sent,  # ← можно улучшить маскирование позже
                        is_active=True,
                        is_user_added=True,
                        added_by=request.user,
                        source_field=field_name,
                        explanation="!"  # ← или парсить из содержимого
                    )
            except Punktum.DoesNotExist:
                pass

        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)


# =========== ЗАДАНИЯ 1-3 ================================================
@login_required
def generate_text_analysis(request):
    """Генерация задания 1-3 (анализ текста)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        # Получаем случайный активный текст
        tasks = TextAnalysisTask.objects.filter(is_active=True)
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
        
        # Проверяем каждый ответ
        results = {}
        total_correct = 0
        
        for q_num in ['1', '2', '3']:
            user_answer = user_answers.get(q_num, '').strip()
            correct_answer = correct_answers.get(q_num, '').strip()
            
            if q_num == '1':
                # Для вопроса 1: сравниваем текст (можно несколько вариантов через /)
                correct_variants = [v.strip() for v in correct_answer.split('/')]
                is_correct = user_answer.lower() in [v.lower() for v in correct_variants]
            else:
                # Для вопросов 2 и 3: сравниваем строку с номерами (например "345")
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
            'total_questions': 3,
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Ошибка проверки: {str(e)}'}, status=500)
    
    
    
# =========== ЗАДАНИЯ 23-24 ===============================================
# в views.py
@login_required
def generate_text_analysis_23_24(request):
    """Генерация заданий 23-24"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    
    try:
        # Просто берем все активные тексты
        tasks = TextAnalysisTask.objects.filter(is_active=True)
        
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
    


# =====================================================================================
# def generate_orthoepy_test(request):
#     """Автоматически генерирует тест по орфоэпии (задание 4)"""
#     if request.method != 'POST':
#         return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
#     try:
#         import random
        
#         # Получаем активные слова
#         active_words = OrthoepyWord.objects.filter(is_active=True)
        
#         if not active_words.exists():
#             return JsonResponse({
#                 'error': 'Нет доступных слов для теста',
#                 'html': '<p>Пока нет слов для теста по орфоэпии.</p>'
#             })
        
#         # Берем 5 случайных слов из базы
#         words_count = 5
#         all_words_list = list(active_words)
        
#         if len(all_words_list) < words_count:
#             selected_words = all_words_list
#         else:
#             selected_words = random.sample(all_words_list, words_count)
        
#         # Формируем HTML в формате задания
#         html = '''
#         <div class="orthoepy-exercise">
#             <h3>Задание 4: Орфоэпические нормы</h3>
#             <p><strong>Укажите варианты ответов, в которых верно выделена буква, обозначающая ударный гласный звук. Запишите номера ответов.</strong></p>
#             <div class="questions-container">
#         '''
        
#         correct_numbers = []  # Здесь будем хранить номера правильных ответов
        
#         for i, word in enumerate(selected_words, 1):
#             all_variants = word.get_all_variants_shuffled()
            
#             html += f'''
#             <div class="orthoepy-question" data-word-id="{word.id}">
#                 <p><strong>{i})</strong> <span style="margin-left: 10px;"></span>
#             '''
            
#             for j, variant in enumerate(all_variants, 1):
#                 # Ищем правильный вариант для этого слова
#                 if variant == word.correct_variant:
#                     correct_numbers.append(str(i))
                
#                 html += f'''
#                 <label class="option">
#                     <input type="checkbox" 
#                            data-question="{i}" 
#                            data-correct="{1 if variant == word.correct_variant else 0}"
#                            value="{i}">  <!-- номер вопроса -->
#                     {variant}
#                 </label>
#                 '''
#                 if j < len(all_variants):
#                     html += '<br>'
            
#             html += f'''
#                 </p>
#                 <div class="hint" style="display: none; color: #666; font-size: 0.9em; margin-top: 5px;">
#                     <strong>Объяснение:</strong> {word.explanation}
#                 </div>
#             </div>
#             '''
        
#         html += '''
#             </div>
#             <div style="margin-top: 20px;">
#                 <button class="check-orthoepy green">Проверить ответы</button>
#                 <button class="show-hints">Показать объяснения</button>
#             </div>
#             <div class="result" style="display: none; margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 5px;"></div>
#             <!-- Скрытое поле с правильными ответами для проверки -->
#             <input type="hidden" id="correct-answer" value="''' + ''.join(correct_numbers) + '''">
#         </div>
#         '''
        
#         # Сохраняем правильные ответы в сессии для проверки
#         request.session['orthoepy_correct_answer'] = ''.join(correct_numbers)
        
#         return JsonResponse({'html': html})
        
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)


# def check_orthoepy_test(request):
#     """Проверяет ответы теста по орфоэпии в формате "125" """
#     if request.method != 'POST':
#         return JsonResponse({'error': 'Метод не поддерживается'}, status=405)
    
#     try:
#         import json
#         data = json.loads(request.body)
#         user_answer = data.get('answer', '')  # Строка типа "125"
        
#         # Получаем правильный ответ из сессии
#         correct_answer = request.session.get('orthoepy_correct_answer', '')
        
#         if not correct_answer:
#             return JsonResponse({'error': 'Сессия истекла. Обновите страницу.'})
        
#         # Сортируем обе строки для сравнения (пользователь мог ввести в любом порядке)
#         user_sorted = ''.join(sorted(user_answer))
#         correct_sorted = ''.join(sorted(correct_answer))
        
#         is_correct = (user_sorted == correct_sorted)
        
#         return JsonResponse({
#             'is_correct': is_correct,
#             'user_answer': user_answer,
#             'correct_answer': correct_answer,
#             'message': 'Правильно!' if is_correct else 'Неверно'
#         })
        
#     except Exception as e:
#         return JsonResponse({'error': str(e)}, status=500)


# views.py - упрощенная функция generate_orthoepy_test

# views.py
# @login_required
# def generate_orthoepy_test(request):
#     if request.method != 'POST':
#         return JsonResponse({'error': 'Только POST'}, status=405)

#     user_grade = getattr(request.user.profile, 'grade', None)
#     test_data = OrthoepyWord.generate_test(user_grade=user_grade)

#     if not test_data or not test_data.get('variants'):
#         return JsonResponse({'error': 'Недостаточно данных для генерации теста.'}, status=400)

#     # Проверка на уникальность слов
#     variants = test_data['variants']
#     unique_variants = []
#     seen = set()
    
#     for variant in variants:
#         if variant not in seen:
#             unique_variants.append(variant)
#             seen.add(variant)
#         else:
#             # Если есть дубликат, логика генерации некорректна
#             return JsonResponse({'error': 'Обнаружены повторяющиеся слова в тесте.'}, status=400)

#     # Используем только уникальные варианты
#     html = render(request, 'orthoepy_test_snippet.html', {
#         'variants': unique_variants,
#         'exercise_id': 'orthoepy-1',
#         'user_grade': user_grade,
#     }).content.decode('utf-8')

#     request.session['orthoepy_correct'] = test_data['correct_answers']
#     return JsonResponse({'html': html})


@login_required
def generate_orthoepy_test(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    user_grade = getattr(request.user.profile, 'grade', None)
    test_data = OrthoepyWord.generate_test(user_grade=user_grade)

    if not test_data or not test_data.get('variants'):
        return JsonResponse({'error': 'Недостаточно данных для генерации теста.'}, status=400)

    # Проверка на уникальность слов
    variants = test_data['variants']
    unique_variants = []
    seen = set()
    
    for variant in variants:
        if variant not in seen:
            unique_variants.append(variant)
            seen.add(variant)
        else:
            return JsonResponse({'error': 'Обнаружены повторяющиеся слова в тесте.'}, status=400)

    html = render(request, 'orthoepy_test_snippet.html', {
        'variants': unique_variants,
        'exercise_id': 'orthoepy-1',
        'user_grade': user_grade,
    }).content.decode('utf-8')

    # 🔴 СОХРАНЯЕМ ВСЕ варианты теста для последующей проверки
    request.session['orthoepy_correct'] = test_data['correct_answers']
    request.session['orthoepy_all_variants'] = unique_variants  # <-- ДОБАВЛЕНО
    
    return JsonResponse({'html': html})

# @login_required
# def check_orthoepy_test(request):
#     if request.method != 'POST':
#         return JsonResponse({'error': 'Только POST'}, status=405)

#     data = json.loads(request.body)
#     selected = set(data.get('selected', []))
#     correct = set(request.session.get('orthoepy_correct', []))

#     # ✅ Правило ЕГЭ: 1 балл — если выбраны ВСЕ правильные и НИЧЕГО лишнего
#     # То есть: selected == correct
#     is_perfect = selected == correct

#     # Формируем результат для каждого варианта
#     results = {}
#     for variant in (selected | correct):
#         results[variant] = {
#             'variant': variant,
#             'is_correct_variant': variant in correct,
#             'was_selected': variant in selected,
#         }

#     # Статистика
#     correctly_selected = len(selected & correct)  # сколько верных выбрали
#     incorrectly_selected = len(selected - correct)  # сколько неверных выбрали
#     correct_count = len(correct)  # всего правильных

#     # ⚠️ Балл: 1 — только если selected == correct, иначе 0
#     user_score = 1 if is_perfect else 0

#     return JsonResponse({
#         'results': results,
#         'summary': {
#             'correctly_selected': correctly_selected,
#             'incorrectly_selected': incorrectly_selected,
#             'correct_answers_count': correct_count,
#             'user_score': user_score,
#         }
#     })

@login_required
def check_orthoepy_test(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    data = json.loads(request.body)
    selected = set(data.get('selected', []))
    correct = set(request.session.get('orthoepy_correct', []))
    
    # 🔴 ВАЖНО: Получаем ВСЕ варианты из текущего теста
    # Они должны где-то сохраняться в сессии
    all_variants = set(request.session.get('orthoepy_all_variants', []))

    # Если в сессии нет всех вариантов, используем union selected и correct
    if not all_variants:
        all_variants = selected | correct

    # ✅ Правило ЕГЭ: 1 балл — если выбраны ВСЕ правильные и НИЧЕГО лишнего
    is_perfect = selected == correct

    # Формируем результат для КАЖДОГО варианта из теста (а не только selected|correct)
    results = {}
    for variant in all_variants:
        results[variant] = {
            'variant': variant,
            'is_correct_variant': variant in correct,
            'was_selected': variant in selected,
        }

    # Статистика
    correctly_selected = len(selected & correct)
    incorrectly_selected = len(selected - correct)
    correct_count = len(correct)

    # ⚠️ Балл: 1 — только если selected == correct, иначе 0
    user_score = 1 if is_perfect else 0

    return JsonResponse({
        'results': results,
        'summary': {
            'correctly_selected': correctly_selected,
            'incorrectly_selected': incorrectly_selected,
            'correct_answers_count': correct_count,
            'user_score': user_score,
        }
    })


# ======= ЗАДАНИЕ 7 ===================================================
# В views.py
@login_required
def generate_correction_test_view(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)
    user_grade = getattr(request.user.profile, 'grade', None)
    test_data = CorrectionExercise.generate_correction_test(user_grade=user_grade)
    if not test_data:
        return JsonResponse({'error': 'Недостаточно данных'}, status=400)
    # Сохраняем в сессии для проверки
    request.session['correction_test'] = {
        'correct_answer': test_data['correct_answer'].lower().strip(),
        'exercise_id': test_data['exercise_id'],
        'incorrect_word': test_data['incorrect_word'].lower().strip(),  # Для проверки
    }
    html = render_to_string('correction_test_snippet.html', {
        'words': test_data['words'],  # ← Передаём весь список слов
    })
    return JsonResponse({'html': html})


# В views.py
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
