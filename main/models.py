from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    email_confirmed = models.BooleanField(default=False)

    # Персональные данные
    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Имя",
    )
    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Фамилия",
    )
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
    telegram_username = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ник в Telegram",
    )
    telegram_id = models.BigIntegerField(
        null=True, 
        blank=True, 
        unique=True, 
        verbose_name="Telegram ID")

    def __str__(self):
        return f"{self.user.username} Profile"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


class UserExample(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
    )
    # например: "user-input-orf-1"
    field_name = models.CharField(
        max_length=50,
        verbose_name="Имя поля",
    )
    content = models.TextField(blank=True, verbose_name="Содержимое")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")

    class Meta:
        # Уникальная пара: пользователь + поле
        unique_together = ('user', 'field_name')
        verbose_name = "Пример пользователя"
        verbose_name_plural = "Примеры пользователей"

    def __str__(self):
        return f"{self.user.username} - {self.field_name}"


class CorrectAnswer(models.Model):
    orthogram_number = models.IntegerField(verbose_name="Номер орфограммы")
    correct_word = models.CharField(
        max_length=255,
        verbose_name="Правильное слово",
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Описание",
    )

    class Meta:
        indexes = [
            models.Index(fields=['orthogram_number'], name='orfo_num_idx'),
            models.Index(fields=['correct_word'], name='word_idx'),
            models.Index(
                fields=['orthogram_number', 'correct_word'],
                name='orfo_word_idx',
            ),
        ]
        verbose_name = "Правильный ответ"
        verbose_name_plural = "Правильные ответы"





class Orthogram(models.Model):
    id = models.CharField(max_length=10, primary_key=True)  # '1', '2', '6', '271'
    name = models.CharField(max_length=200)
    rule = models.TextField()
    
    # 🔑 Новый: список букв/символов для этой орфограммы
    letters = models.CharField(
        max_length=200,
        default='а,о,е,и,я',
        help_text="Буквы или символы через запятую: а,б,в,г,д,е,ё,ж,з,и,й,к,л,м,н,о,п,р,с,т,у,ф,х,ц,ч,ш,щ,ъ,ы,ь,э,ю,я,-,/,|,_"  # можно добавлять любые символы
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        help_text="Через запятую: 5,6,7"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def get_letters_list(self):
        """Возвращает список букв без пробелов"""
        return [letter.strip() for letter in self.letters.split(',') if letter.strip()]

    def __str__(self):
        return f"{self.id}: {self.name}"
    


class OrthogramExample(models.Model):
    orthogram = models.ForeignKey(Orthogram, on_delete=models.CASCADE)
    text = models.CharField(max_length=300)                    # например: "вода"
    masked_word = models.CharField(max_length=300)             # например: "в*1*да"
    incorrect_variant = models.CharField(max_length=300, blank=True, null=True)
    explanation = models.TextField(blank=True)

    difficulty = models.PositiveSmallIntegerField(default=1)
    is_for_quiz = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_user_added = models.BooleanField(default=False, verbose_name="Добавлен пользователем")
    added_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Кем добавлен"
    )
    source_field = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Поле-источник (например, user-input-orf-711)"
    )

    # Для каких классов актуален пример
    grades = models.CharField(
        max_length=50,
        blank=True,
        help_text="Через запятую: 5,6,7"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def get_grades_list(self):
        """Возвращает список целых чисел: [5, 6, 7]"""
        if self.grades:
            return [
                int(g.strip())
                for g in self.grades.split(',')
                if g.strip().isdigit()
            ]
        return []

    def __str__(self):
        grades_display = self.grades or 'все'
        return f"{self.text} (орф. {self.orthogram.id}, классы: {grades_display})"


class StudentAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    orthogram = models.ForeignKey(Orthogram, on_delete=models.CASCADE, verbose_name="Орфограмма")
    phrase = models.ForeignKey(OrthogramExample, on_delete=models.CASCADE, verbose_name="Пример")
    selected_answer = models.CharField(max_length=300, verbose_name="Выбранный ответ")
    is_correct = models.BooleanField(verbose_name="Правильно?")
    answered_at = models.DateTimeField(auto_now_add=True, verbose_name="Когда ответил")

    class Meta:
        verbose_name = "Ответ ученика"
        verbose_name_plural = "Ответы учеников"

    def __str__(self):
        return f"{self.user.username} → {self.selected_answer} ({'✓' if self.is_correct else '✗'})"