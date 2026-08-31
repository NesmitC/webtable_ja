# main/forms.py
import time
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile


# ================ Форма регистрации ================
class CustomUserCreationForm(UserCreationForm):
    # 1. HONEYPOT (Горшок с медом)
    # Боты парсят HTML и заполняют ВСЕ поля. Человек этого поля не увидит.
    website = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label=''
    )
    
    # 2. TIME TRAP (Ловушка времени)
    # Сюда мы "зашьем" время загрузки страницы. 
    # Если форма улетит быстрее чем через 3 секунды — это бот.
    form_timestamp = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1']
        labels = {
            'username': 'Логин',
            'email': 'Email',
            'password1': 'Пароль',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # ВАЖНО: Внедряем timestamp только если форма еще НЕ отправлена (GET-запрос).
        # Если форма уже отправлена (POST), мы не должны перезаписывать время, 
        # иначе проверка скорости заполнения сломается.
        if not self.is_bound:
            self.fields['form_timestamp'].initial = int(time.time())

        # --- Твоя оригинальная логика (не трогаем) ---
        # Убираем подсказку для username
        self.fields['username'].help_text = None
        # Убираем подсказку для password1
        self.fields['password1'].help_text = None
        # Удаляем поле password2
        if 'password2' in self.fields:
            del self.fields['password2']

    def clean(self):
        # Вызываем стандартные проверки Django (они должны сработать первыми)
        cleaned_data = super().clean()
        
        # ПРОВЕРКА 1: Если бот заполнил скрытое поле website
        if cleaned_data.get('website'):
            raise ValidationError("Обнаружена подозрительная активность. Если вы человек, обновите страницу.")
            
        # ПРОВЕРКА 2: Если форма отправлена слишком быстро (меньше 3 секунд)
        submitted_at = cleaned_data.get('form_timestamp')
        if submitted_at:
            time_spent = int(time.time()) - submitted_at
            if time_spent < 3:
                raise ValidationError("Слишком быстрая отправка формы. Обновите страницу и попробуйте еще раз.")
                
        return cleaned_data


# ================ Форма входа ================
# ================ Форма входа ================
class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Email',
        widget=forms.TextInput(
            attrs={
                'autofocus': True,
                'class': 'form-control',
                'placeholder': 'mail@example.com',
                'type': 'email',
            }
        ),
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(
            attrs={'class': 'form-control'}
        ),
    )

    error_messages = {
        'invalid_login': 'Неверный email или пароль.',
        'inactive': 'Этот аккаунт не активирован. Проверьте почту — мы отправляли ссылку для подтверждения.',
    }

    def clean_username(self):
        """
        Этот метод вызывается Django ПЕРЕД общим clean().
        Здесь мы подменяем введённый email на настоящий username,
        чтобы стандартная проверка пароля в AuthenticationForm.clean() 
        отработала корректно.
        """
        email = self.cleaned_data.get('username', '').strip()
        if not email:
            return email

        try:
            user = User.objects.get(email__iexact=email)
            return user.username  # ← подменяем на настоящий username
        except User.DoesNotExist:
            # Вернём как есть — пусть стандартная проверка выдаст ошибку
            return email
        except User.MultipleObjectsReturned:
            # Крайний случай: несколько аккаунтов с одним email
            user = User.objects.filter(
                email__iexact=email, is_active=True
            ).first()
            return user.username if user else email


# ================ Форма профиля ================
class ProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'grade', 'telegram_username']
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'grade': 'Класс',
            'telegram_username': 'Ник в Telegram',
        }
        widgets = {
            'grade': forms.Select(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'telegram_username': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
        }