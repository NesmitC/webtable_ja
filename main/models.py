from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    email_confirmed = models.BooleanField(default=False)

    # Персональные данные
    first_name = models.CharField(max_length=100, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=100, blank=True, verbose_name="Фамилия")
    grade = models.CharField(
        max_length=2,
        choices=[
            ('3', '3'),
            ('4', '4'),
            ('5', '5'),
            ('6', '6'),
            ('7', '7'),
            ('8', '8'),
            ('9', '9'),
            ('10', '10'),
            ('11', '11'),
        ],
        blank=True,
        verbose_name="Класс"
    )
    telegram_username = models.CharField(max_length=100, blank=True, verbose_name="Ник в Telegram")

    def __str__(self):
        return f"{self.user.username} Profile"
    

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        

class UserExample(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    field_name = models.CharField(max_length=50, verbose_name="Имя поля")  # например: "user-input-orf-1"
    content = models.TextField(blank=True, verbose_name="Содержимое")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        unique_together = ('user', 'field_name')  # Уникальная пара: пользователь + поле
        verbose_name = "Пример пользователя"
        verbose_name_plural = "Примеры пользователей"

    def __str__(self):
        return f"{self.user.username} - {self.field_name}"