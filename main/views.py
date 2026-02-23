# main/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.sites.shortcuts import get_current_site
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.utils.html import escape
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
from .models import UserExample, UserProfile, OrthogramExample, Orthogram, StudentAnswer, Punktum, PunktumExample, TextAnalysisTask, TextQuestion, QuestionOption, OrthoepyWord, CorrectionExercise, TaskGrammaticEightExample, TaskGrammaticTwoTwo, TaskGrammaticTwoTwoExample, TaskPaponim, WordOk
from .assistant import NeuroAssistant
import random
from random import sample, choice, sample, randint, shuffle
from django.db.models import Q


logger = logging.getLogger('django')


# === Утилиты ===

# def extract_correct_letter(text, masked_word, orthogram_id=None):
#     """
#     Извлекает правильную букву/буквы из оригинального текста.
#     Для Н/НН орфограмм (38, 39, 48+) поддерживает двухсимвольные ответы.
#     """
#     try:
#         mask_start = masked_word.find('*')
#         if mask_start == -1:
#             return ''
        
#         # === СПЕЦОБРАБОТКА ДЛЯ Н/НН ===
#         if orthogram_id in {38, 39, 48, 481, 482, 483, 484, 1500}:
#             # Проверяем, есть ли "нн" в тексте на позиции маски
#             if mask_start + 1 < len(text):
#                 two_chars = text[mask_start:mask_start + 2].lower()
#                 if two_chars == 'нн':
#                     return 'нн'
        
#         # Обычная обработка (один символ)
#         if mask_start < len(text):
#             char = text[mask_start]
#             return '|' if char == '\\' else char
#         return ''
#     except Exception:
#         return ''
    

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


def planning_8kl(request):
    return render(request, 'planning_8kl.html')


def ege(request):
    return render(request, 'ege.html')

def starting_diagnostic(request):
    return render(request, 'diagnostic_starting.html')

def targetn(request):
    return render(request, 'games_html/targetn.html')


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

        # Задание 9: Орфографические нормы
        if set(orthogram_ids) == {1, 2, 12, 13, 14, 15, 24, 26, 27, 271}:
            exercise_title = "Задание № 9. Корни"

        # Задание 10: Приставки
        elif set(orthogram_ids) == {10, 11, 28, 29, 6}:
            exercise_title = "Задание № 10. Приставки."

        # Задание 11: Суффиксы
        elif set(orthogram_ids) == {31, 33, 34, 35, 37, 39, 48, 481, 482, 483, 484, 60, 61, 610, 485}:
            exercise_title = "Задание № 11. Суффиксы."

        # Задание 12: Спряжения. Причастия
        elif set(orthogram_ids) == {25, 49, 50, 51, 511, 512, 513}:
            exercise_title = "Задание № 12. Спряжения. Причастия"

        # Задание 13: Слитно - раздельно
        elif set(orthogram_ids) == {21, 32, 36, 46, 54, 56, 57, 58, 581, 582}:
            exercise_title = "Задание № 13. Слитно - раздельно"

        # Задание 14: Слитно - раздельно - дефис
        elif orthogram_ids == [1400]:
            exercise_title = "Задание № 14. Слитно - раздельно - дефис"
            
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
    Для орфограммы 1400 нормализует \ в |.
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
                mask_pattern = f"*21-{punktum_id}*"
                # Проверяем, есть ли в тексте исходная маска
                if f"*{punktum_id}*" not in ex.masked_word:
                    continue
            else:
                mask_pattern = f"*{punktum_id}*"
                if mask_pattern not in ex.masked_word:
                    continue
            
            mask_count = ex.masked_word.count(f"*{punktum_id}*")
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
        
        # Формируем слова для отображения
        words_lines = []
        for ex in valid_examples:
            masked = ex.masked_word.strip()
            if punktum_id.startswith('21'):
                # Заменяем *2100* на *21-2100* для фронтенда
                masked = masked.replace(f"*{punktum_id}*", f"*21-{punktum_id}*")
            words_lines.append(masked)
        
        structured_examples = [
            [p.strip() for p in ex.masked_word.split('\n') if p.strip()]
            for ex in valid_examples
        ]
        
        is_punktum_with_paragraphs = (punktum_id == '1800')
        
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
        })
        
        return JsonResponse({'html': html})
    
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
            'word_count': len(words)
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
            'exercise_title': 'Задание № 9. Корни',
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
        }
        
        # 5. Рендерим
        html = render_to_string('exercise_snippet.html', {
            'words_text': ', '.join(formatted_items),
            'exercise_id': 'chered_ege',
            'exercise_title': 'Чередующиеся гласные',
            'show_next_button': False,
        })
        
        return JsonResponse({'html': html})
        
    except Exception as e:
        logger.error(f"Ошибка в generate_chered_exercise: {e}", exc_info=True)
        return JsonResponse({'error': 'Внутренняя ошибка сервера'}, status=500)

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
        
        return JsonResponse({
            'results': results,
            'correct_count': correct_count,
            'total_count': total_count,
            'all_correct': all_correct
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
        tasks = TextAnalysisTask.objects.filter(is_active=True)
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
    """
    Генерирует тест по орфоэпии для тренажёра.
    
    Режимы:
    - 'main' (по умолчанию): 2-4 правильных + 1-3 неправильных варианта
    - 'diagnostic': 2-4 правильных + 1-3 неправильных варианта (тот же формат)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    test_type = data.get('test_type', 'main')
    
    # Получаем класс пользователя для фильтрации
    user_grade = None
    if hasattr(request.user, 'profile'):
        user_grade = getattr(request.user.profile, 'grade', None)

    # === ГЕНЕРИРУЕМ ТЕСТ: 2-4 правильных + 1-3 неправильных ===
    test_data = OrthoepyWord.generate_test(
        num_options=5,
        correct_min=2,
        correct_max=4,
        user_grade=user_grade,
        test_type=test_type
    )
    
    if not test_data or not test_data.get('variants'):
        return JsonResponse({'error': 'Недостаточно данных.'}, status=400)

    variants = test_data['variants']
    correct_answers = test_data['correct_answers']

    # === Проверяем уникальность (на всякий случай) ===
    if len(variants) != len(set(variants)):
        return JsonResponse({'error': 'Обнаружены повторяющиеся варианты.'}, status=400)

    # === Рендерим шаблон ===
    html = render_to_string('orthoepy_test_snippet.html', {
        'variants': variants,
        'exercise_id': f'orthoepy-{test_type}',
        'user_grade': user_grade,
    })

    # === Сохраняем в сессию ===
    request.session['orthoepy_correct'] = correct_answers  # СПИСОК правильных
    request.session['orthoepy_all_variants'] = variants    # ВСЕ варианты
    request.session['orthoepy_test_type'] = test_type

    return JsonResponse({
        'html': html,
        'test_type': test_type,
        'count': len(variants)
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
    
    # Получаем правильные ответы из сессии
    correct_answers = request.session.get('orthoepy_correct', [])
    if not isinstance(correct_answers, list):
        correct_answers = [correct_answers]
    correct = set(correct_answers)
    
    # Получаем ВСЕ варианты из сессии
    all_variants = request.session.get('orthoepy_all_variants', [])
    
    # === Формируем результат для КАЖДОГО варианта ===
    variant_results = {}
    for i, variant in enumerate(all_variants, 1):
        normalized = _normalize_text(variant)
        normalized_correct = set(_normalize_text(x) for x in correct)
        
        is_correct_variant = normalized in normalized_correct
        was_selected = variant in selected
        
        variant_results[f'4-{i}'] = {
            'variant_text': variant,
            'is_correct': is_correct_variant,
            'was_selected': was_selected,
        }
    
    # === Правило ЕГЭ: 1 балл только если ВСЕ правильные выбраны и НИЧЕГО лишнего ===
    is_perfect = selected == correct
    user_score = 1 if is_perfect else 0
    
    # === Возвращаем результат в формате, аналогичном диагностике ===
    return JsonResponse({
        'results': {
            '4': {
                'is_correct': is_perfect,
                'score': user_score,
                'variant_results': variant_results,
            }
        },
        'user_score': user_score,
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


# views.py
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
    if request.method != 'POST':
        return JsonResponse({'error': 'Только POST'}, status=405)

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
        user_grade = None
        if request.user.is_authenticated:
            # Залогиненный пользователь - берём из профиля
            user_grade = getattr(request.user.profile, 'grade', None)
        else:
            # Анонимный пользователь - ставим None (будут задания для всех классов)
            user_grade = None
        
        # === ЗАДАНИЕ 4: ОРФОЭПИЯ (НОВАЯ ЛОГИКА) ===
        test_data = OrthoepyWord.generate_test(
            num_options=5,
            correct_min=2,
            correct_max=4,
            user_grade=user_grade
        )
        
        if test_data:
            context['orthoepy_variants'] = test_data['variants']
            # Сохраняем ПРАВИЛЬНЫЕ ответы и ВСЕ варианты
            session_data['answer_4'] = test_data['correct_answers']
            session_data['variants_4'] = test_data['variants']

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

        # === Задание 7: Грамматика ===
        try:
            user_grade = getattr(request.user.profile, 'grade', None)
            test_data = CorrectionExercise.generate_correction_test(user_grade=user_grade)
            if test_data:
                wrong_item = CorrectionExercise.objects.filter(
                    incorrect_text=test_data['incorrect_word'],
                    correct_text=test_data['correct_answer']
                ).first()
                context['correction_sentences'] = test_data['words']
                explanation = wrong_item.explanation.lower().strip() if wrong_item else ''
                session_data['answer_7'] = explanation or test_data['correct_answer'].lower().strip()
        except Exception as e:
            logger.error(f"Ошибка генерации задания 7: {e}")

        # === ЗАДАНИЕ 8: Грамматические ошибки ===
        task8_data = generate_task8_for_diagnostic()
        if task8_data:
            context['task8_html'] = task8_data['html']
            session_data['task8_correct'] = task8_data['correct_answers']  # ← Это важно!

        # === ЗАДАНИЕ 9 ===
        task9_lines = generate_task9_lines()
        if task9_lines:
            context['task9_lines'] = task9_lines
            flat_letters = [letter for line in task9_lines for letter in line.get('expected_letters', [])]
            if flat_letters:
                session_data['task9_correct'] = flat_letters

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
        task21_data = generate_task21_for_diagnostic()
        if task21_data:
            context['task21_data'] = task21_data
            session_data['task21_correct'] = task21_data['correct_symbols']
            context['task21_letter_groups'] = json.dumps(task21_data['letter_groups'])
            context['task21_subgroup_letters'] = json.dumps(task21_data['subgroup_letters'])

        # === ЗАДАНИЕ 22: Средства выразительности ===
        task22_data = generate_task_twotwo_for_diagnostic()
        if task22_data:
            context['task22_html'] = task22_data['html']
            session_data['task22_correct'] = task22_data['correct_answers']
        else:
            context['task22_html'] = '<p>Задание 22 временно недоступно</p>'

        # === Задания 23-26 ===
        text_task_23_26, text_questions_23_26 = get_text_analysis_questions('23_26')
        if text_task_23_26:
            context['text_task_23_26'] = text_task_23_26
            context['text_questions_23_26'] = text_questions_23_26
            session_data['answers_23_26'] = {
                str(q.question_number): q.correct_answer for q in text_questions_23_26
            }

        # === Сохраняем в сессию ===
        request.session['starting_diagnostic'] = session_data

        # === Рендерим шаблон ===
        html = render_to_string('diagnostic_snippet.html', context)
        return JsonResponse({'html': html})

    except Exception as e:
        logger.error(f"Ошибка генерации диагностики: {e}", exc_info=True)
        return JsonResponse({'error': f'Ошибка: {str(e)}'}, status=500)
    


def _normalize_text(s):
    """Приводит строку к нижнему регистру и убирает пробелы по краям."""
    if not isinstance(s, str):
        s = str(s)
    return s.strip().lower()

def _normalize_digits(s):
    """Извлекает только цифры из строки."""
    if not isinstance(s, str):
        s = str(s)
    return ''.join(filter(str.isdigit, s))


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

        # === Задания 1–3 (ТОЧНО как в тренажере) ===
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
                # Задание 1: варианты через / (как в тренажере!)
                correct_variants = [v.strip() for v in correct.split('/')]
                is_correct = user_ans.lower() in [v.lower() for v in correct_variants]
            else:
                # Задания 2 и 3
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
    tasks = TextAnalysisTask.objects.filter(is_active=True)
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
    # Используем статический метод модели
    test_data = TaskGrammaticEightExample.generate_task_eight_test()
    
    if not test_data:
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
    answer_key = test_data['answer_key']  # {id_предложения: 'А' или None}
    
    # Находим для каждой буквы (А-Д) номер предложения
    for sentence_id, letter in answer_key.items():
        if letter:  # Если не None (предложение с ошибкой)
            # Находим номер этого предложения
            for i, sent_item in enumerate(test_data['sentences'], 1):
                if str(sent_item['id']) == str(sentence_id):
                    correct_answers[letter] = str(i)
                    break

    # ГЕНЕРИРУЕМ HTML (добавьте этот блок!)
    html = render_to_string('task_grammatic_eight.html', {
        'error_type_names': test_data['error_type_names'],
        'sentences': sentences,
        'show_check_button': False  # Для диагностики не нужна кнопка
    })
    
    return {
        # 'error_type_names': test_data['error_type_names'],
        # 'sentences': sentences,  # 9 предложений
        'html': html,  # ← ДОБАВЬТЕ HTML!
        'correct_answers': correct_answers,  # {'А': '1', 'Б': '2', ...}
        'test_data': test_data  # Сохраняем полные данные на всякий случай
    }

# ======= Задание 9  =================================================
def generate_task9_lines():
    # === НОВАЯ СТРУКТУРА: 5 чётких групп ===
    letter_groups = [
        {
            'letters': ('о', 'а', 'е', 'и', 'я', 'у', 'ю'),
            'orth_ids': ['1_11', '2_11'],
            'name': 'о/а/е/и/я/у/ю'
        },
        {
            'letters': ('о', 'а'),
            'orth_ids': ['12', '13', '26', '27', '271'],
            'name': 'о/а'
        },
        {
            'letters': ('е', 'и', 'я'),
            'orth_ids': ['24'],
            'name': 'е/и/я'
        },
        {
            'letters': ('ё', 'о'),
            'orth_ids': ['14'],
            'name': 'ё/о'
        },
        {
            'letters': ('и', 'ы'),
            'orth_ids': ['15'],
            'name': 'и/ы'
        }
    ]

    # === Шаг 1: Выбираем, сколько строк будет uniform (2–4) ===
    from random import randint, sample, shuffle, choice
    
    uniform_count = randint(2, 4)

    # === Шаг 2: Случайно выбираем индексы uniform-строк ===
    line_indices = list(range(len(letter_groups)))
    uniform_indices = set(sample(line_indices, uniform_count))

    lines = []
    flat_index = 1

    # === Шаг 3: Генерируем ровно 5 строк — по одной на каждую группу ===
    for i, group in enumerate(letter_groups):
        orth_ids = []
        for oid in group['orth_ids']:
            if '_' in oid:
                base_id = oid.split('_')[0]
            else:
                base_id = oid
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
        ).order_by('?')[:30]  # Берем больше для выборки

        # Собираем валидные примеры
        valid_examples = []
        for ex in examples_qs:
            correct_letter = extract_correct_letter(ex.text, ex.masked_word)
            if correct_letter and len(correct_letter) == 1:
                valid_examples.append((ex, correct_letter.lower()))

        if len(valid_examples) < 3:
            continue

        # Решаем: делать ли строку с одинаковыми буквами?
        make_uniform = i in uniform_indices  # ← Проверяем, current строка uniform
        
        if make_uniform:
            # Строка с одинаковыми буквами во всех словах
            # Группируем примеры по буквам
            examples_by_letter = {}
            for ex, letter in valid_examples:
                if letter not in examples_by_letter:
                    examples_by_letter[letter] = []
                examples_by_letter[letter].append(ex)
            
            # Ищем букву с минимум 3 примерами
            selected_letter = None
            selected_examples = []
            
            for letter, ex_list in examples_by_letter.items():
                if len(ex_list) >= 3:
                    selected_letter = letter
                    selected_examples = sample(ex_list, 3)
                    break
            
            if selected_letter:
                # Берем 3 примера с одной буквой
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
            # Собираем примеры, где хотя бы 2 разные буквы
            attempts = 0
            selected = []
            while attempts < 10:
                selected = sample(valid_examples, 3)
                letters_in_line = [letter for _, letter in selected]
                if len(set(letters_in_line)) >= 2:  # Минимум 2 разные буквы
                    break
                attempts += 1
            
            if attempts >= 10:
                selected = sample(valid_examples, 3)
            
            examples, letters = zip(*selected)
            is_uniform = False

        # Формируем строку
        parts = []
        for ex in examples:
            masked = re.sub(r'\*\d+(?:_\d+)?\*', f'*9-{flat_index}*', ex.masked_word, count=1)
            parts.append(masked)
            flat_index += 1

        display_line = ', '.join(parts)
        lines.append({
            'examples': list(examples),
            'expected_letters': list(letters),
            'display_line': display_line,
            'available_letters': list(group['letters']),
            'group_name': group['name'],
            'is_uniform': is_uniform  # Для отладки
        })

    return lines[:5]

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
        # 1. Получаем активные средства выразительности
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
            for idx, device in enumerate(all_devices, 1):
                if device.id == ex.device_type_id:
                    correct_answers[letters[i]] = str(idx)
                    break

        # Формируем названия как список
        device_names_list = []
        for i, device in enumerate(all_devices, 1):
            device_names_list.append((str(i), device.get_id_display()))

        # 6. Генерируем HTML
        html_parts = []
        
        # Начало HTML
        html_parts.append('''
<!-- main/templates/task_grammatic_twotwo_snippet.html -->
<div class="task-twotwo-exercise">
    <h3>Задание 22: Установите соответствие между примерами и средствами выразительности</h3>
    <p>К каждой позиции первого столбца подберите соответствующую позицию из второго столбца.</p>

    <div class="task-match-container">
        
        <!-- ЛЕВАЯ КОЛОНКА: Примеры -->
        <div class="task-match-left-column">
            <h4>ПРЕДЛОЖЕНИЯ</h4>
''')
        
        # Левая колонка: Примеры
        for i, ex in enumerate(selected_examples):
            letter = letters[i]
            html_parts.append(f'''
            
            <div class="task-match-row">
                <select class="task-twotwo-select" data-error-letter="{letter}">
                    <option value="-">—</option>
            ''')
            
            # Опции 1-9
            for idx, device in enumerate(all_devices, 1):
                html_parts.append(f'''
                    <option value="{idx}">{idx}</option>
                ''')
            
            html_parts.append(f'''
                </select>
                <span class="task-match-letter">
                    {letter}.
                </span>
                <div class="task-match-content">
            ''')
            
            # Текст примера
            if ex.text and ex.text.strip():
                html_parts.append(f'                    {ex.text}')
            else:
                html_parts.append('                    [Текст примера отсутствует]')
            
            # Автор
            if ex.author and ex.author.strip():
                html_parts.append(f'''
                    <div class="task-match-author">({ex.author})</div>
                ''')
            
            html_parts.append('''
                </div>
            </div>
            ''')
        
        # Правая колонка: Средства выразительности
        html_parts.append('''
        </div>

        <!-- ПРАВАЯ КОЛОНКА: Средства выразительности -->
        <div class="task-match-right-column">
            <h4>ИЗОБРАЗИТЕЛЬНО-ВЫРАЗИТЕЛЬНЫЕ СРЕДСТВА ЯЗЫКА</h4>
            
            <div>
        ''')
        
        for idx, device in enumerate(all_devices, 1):
            html_parts.append(f'''
                <div class="task-match-row">
                    <span class="task-match-item-number">{idx}.</span>
                    <span class="task-match-content">{device.get_id_display()}</span>
                </div>
            ''')
        
        # Конец HTML
        html_parts.append('''
            </div>
        </div>
        
    </div>
</div>
''')
        
        html = ''.join(html_parts)
        
        return {
            'html': html,
            'correct_answers': correct_answers,
            'all_devices': [d.id for d in all_devices]
        }
        
    except Exception as e:
        logger.error(f"Ошибка генерации задания 22 для диагностики: {e}")
        return None
