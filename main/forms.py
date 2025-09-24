# main/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile


# ================ Форма регистрации ================
class CustomUserCreationForm(UserCreationForm):
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
        # Убираем подсказку для username
        self.fields['username'].help_text = None
        # Убираем подсказку для password1
        self.fields['password1'].help_text = None
        # Удаляем поле password2
        if 'password2' in self.fields:
            del self.fields['password2']


# ================ Форма входа ================
class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Логин',
        widget=forms.TextInput(
            attrs={'autofocus': True, 'class': 'form-control'}
        ),
    )
    password = forms.CharField(
        label='Пароль',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )


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
