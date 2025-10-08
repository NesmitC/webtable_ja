# main/views.py
from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm
from django.contrib.auth import login
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import User
from .models import UserProfile
from .forms import ProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import UserExample
from django.views.decorators.csrf import csrf_exempt
from .models import CorrectAnswer
import json


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()  # ← is_active=True по умолчанию
                login(request, user)

                # Создаем профиль при регистрации
                profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={'email_confirmed': True}
                )

                return redirect('index')

            except Exception as e:
                # Логируем ошибку (если настроен логгер)
                import logging
                logger = logging.getLogger('django')
                logger.error(f"Ошибка при регистрации пользователя {user.username}: {e}")

                # Показываем пользователю понятное сообщение
                messages.error(request, "Произошла ошибка при регистрации. Попробуйте позже.")
                return render(request, 'registration/register.html', {'form': form})
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def confirm_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()

        # Создаем профиль, если его нет
        profile, created = UserProfile.objects.get_or_create(user=user)
        profile.email_confirmed = True
        profile.save()

        login(request, user)
        return redirect('index')  # или 'profile'
    else:
        return render(request, 'registration/invalid_link.html')


@login_required
def profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные успешно сохранены!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'profile.html', {'form': form})


@login_required
def save_example(request):
    if request.method == 'POST':
        field_name = request.POST.get('field_name')
        content = request.POST.get('content', '')

        # Сохраняем или обновляем запись
        obj, created = UserExample.objects.update_or_create(
            user=request.user,
            field_name=field_name,
            defaults={'content': content}
        )

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)


@login_required
def load_examples(request):
    examples = (
        UserExample.objects.filter(user=request.user)
        .values('field_name', 'content')
    )
    data = {item['field_name']: item['content'] for item in examples}
    return JsonResponse(data)


def index(request):
    return render(request, 'index.html')


def planning_5kl(request):
    return render(request, 'planning_5kl.html')


def planning_6kl(request):
    return render(request, 'planning_6kl.html')


def planning_7kl(request):
    return render(request, 'planning_7kl.html')


@csrf_exempt
def check_answers(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Список слов от пользователя
            user_words = data.get('words', [])
            results = []

            for word in user_words:
                # Ищем точное совпадение в БД
                is_correct = (
                    CorrectAnswer.objects.filter(correct_word=word).exists()
                )
                results.append({
                    'word': word,
                    'is_correct': is_correct
                })

            return JsonResponse({'results': results})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Only POST allowed'}, status=405)
