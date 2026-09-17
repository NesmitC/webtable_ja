from django.db import models
import random
from django.db.models import Q
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
from django.utils import timezone



# === ТАРИФЫ И ДОСТУП (бизнес-данные в одном месте) ===
PLAN_LEVEL = {'free': 0, 'self': 1, 'group': 2, 'premium': 3}
PLAN_NAMES = {'free': '0', 'self': 'Я сам', 'group': 'Вместе', 'premium': 'Премиум'}
PLAN_PRICES = {'free': 0, 'self': 2490, 'group': 4990, 'premium': 11990}
AI_LIMITS = {0: 15, 1: 150, 2: 200, 3: None}   # сообщений ИИ в месяц; None = безлимит
FREE_PLANNING_WORDS = 15   # лимит активных слов планинга на тарифе «0»
FEATURE_MIN_LEVEL = {
    'planning': 0, 'trainers': 1, 'quizzes': 1, 'lessons': 1,
    'group': 2,
    'premium': 3,
}
TRIAL_DAYS = 5


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    email_confirmed = models.BooleanField(default=False)

    # === Подписка ===
    plan = models.CharField(
        max_length=20,
        choices=[(k, PLAN_NAMES[k]) for k in ('free', 'self', 'group', 'premium')],
        default='free',
    )
    plan_until = models.DateTimeField(null=True, blank=True)
    trial_until = models.DateTimeField(null=True, blank=True)
    ai_used = models.IntegerField(default=0)
    ai_month = models.CharField(max_length=7, blank=True, default='')

    @property
    def level(self):
        if self.role == 'tutor' and self.tutor_active:
            return 3

        """Эффективный уровень: триал даёт полный доступ, иначе — активный тариф."""
        if self.trial_until and timezone.now() < self.trial_until:
            return 3
        if self.plan != 'free' and self.plan_until and timezone.now() < self.plan_until:
            return PLAN_LEVEL[self.plan]
        return 0

    def has_access(self, feature):
        return self.level >= FEATURE_MIN_LEVEL.get(feature, 0)

    def can_use_ai(self):
        """Есть ли свободное сообщение ИИ в месячной квоте (БЕЗ списания)."""
        limit = AI_LIMITS[self.level]
        if limit is None:
            return True
        month = timezone.now().strftime('%Y-%m')
        used = self.ai_used if self.ai_month == month else 0
        return used < limit

    def try_consume_ai(self):
        """Списывает 1 сообщение ИИ с месячной квоты. False = лимит исчерпан."""
        limit = AI_LIMITS[self.level]
        if limit is None:
            return True
        month = timezone.now().strftime('%Y-%m')
        if self.ai_month != month:
            self.ai_month, self.ai_used = month, 0
        if self.ai_used >= limit:
            return False
        self.ai_used += 1
        self.save(update_fields=['ai_month', 'ai_used'])
        return True

    def subscription_info(self):
        """Статус подписки для карточки в ЛК: платный тариф главный, триал — бонус."""
        now = timezone.now()
        info = {'ai_limit': AI_LIMITS[self.level], 'ai_used': self.ai_used}

        if self.role == 'tutor' and self.tutor_active:
            info.update(kind='tutor', plan_name='Репетитор — полный доступ',
                        expiry_date=None, days_text=None,
                        progress_percent=100, trial_note=None)
            return info

        trial_active = bool(self.trial_until and now < self.trial_until)
        trial_note = None
        if trial_active:
            tdays = (self.trial_until - now).days + 1
            trial_note = f'Триал: ещё {self._ru_days(tdays)} полного доступа'

        if self.plan != 'free' and self.plan_until and now < self.plan_until:
            days = (self.plan_until - now).days + 1
            info.update(
                kind='paid',
                plan_name=f'«{PLAN_NAMES[self.plan]}»',
                expiry_date=self.plan_until.strftime('%d.%m.%Y'),
                days_text=self._ru_days(days),
                progress_percent=min(100, int(days / 30 * 100)),
                trial_note=trial_note,
            )
        elif trial_active:
            days = (self.trial_until - now).days + 1
            info.update(
                kind='trial',
                plan_name='Триал — полный доступ',
                expiry_date=self.trial_until.strftime('%d.%m.%Y'),
                days_text=self._ru_days(days),
                progress_percent=min(100, int(days / TRIAL_DAYS * 100)),
                trial_note=None,
            )
        else:
            info.update(
                kind='free',
                plan_name='«0» — базовый доступ',
                expiry_date=None,
                days_text=None,
                progress_percent=100,
                trial_note=None,
            )
        return info


    @staticmethod
    def _ru_days(n):
        """Правильные русские склонения: 1 день / 2 дня / 5 дней."""
        m10, m100 = n % 10, n % 100
        if 11 <= m100 <= 14:
            return f'{n} дней'
        if m10 == 1:
            return f'{n} день'
        if 2 <= m10 <= 4:
            return f'{n} дня'
        return f'{n} дней'

    # === Репетитор платформы ===
    role = models.CharField(
        max_length=10,
        choices=[('student', 'Ученик'), ('tutor', 'Репетитор')],
        default='student',
    )
    tutor_active = models.BooleanField(default=False, verbose_name='Доступ репетитора активен')

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
    
    # 🔹 🔹 🔹 НОВЫЕ ПОЛЯ ДЛЯ VK 🔹 🔹 
    vk_id = models.BigIntegerField(
        null=True, 
        blank=True, 
        unique=True, 
        verbose_name="VK ID"
    )
    link_code = models.CharField(
        max_length=10, 
        blank=True, 
        null=True, 
        verbose_name="Код привязки VK"
    )
    link_code_expires = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="Срок действия кода"
    )

    max_id = models.BigIntegerField(
        null=True, 
        blank=True, 
        unique=True, 
        verbose_name='MAX ID'
    )

    max_chat_id = models.BigIntegerField(
        null=True, 
        blank=True, 
        verbose_name='MAX chat ID'
        )

    def __str__(self):
        return f"{self.user.username} Profile"


class Payment(models.Model):
    """Журнал платежей ЮKassa. unique по yk_payment_id = защита от двойной активации."""
    yk_payment_id = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=30, default='pending')  # pending/succeeded/canceled/refunded
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} {self.plan} {self.status}'


class TutorInvite(models.Model):
    """Пригласительный код репетитора. Коды создаёт владелец в админке."""
    code = models.CharField(max_length=12, unique=True)
    is_active = models.BooleanField(default=True)
    used_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.code} ({self.used_by or "свободен"})'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate()
        super().save(*args, **kwargs)

    def _generate(self):
        import random, string
        while True:
            code = 'TUTOR-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not TutorInvite.objects.filter(code=code).exists():
                return code



@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

class DailyWord(models.Model):
    """Слово дня: одно слово на пользователя на период (12:00 МСК -> следующие 12:00)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_words')
    period_date = models.DateField()                        # дата, в 12:00 МСК которой открыто слово
    source = models.CharField(max_length=20, default='')    # planning/hot/orthography/orthoepy
    example_id = models.IntegerField(null=True, blank=True)
    user_word_id = models.IntegerField(null=True, blank=True)
    question = models.TextField(default='')
    options_json = models.TextField(default='')
    correct_text = models.CharField(max_length=200, default='')
    explanation = models.TextField(default='')
    answered = models.BooleanField(default=False)
    answered_correctly = models.BooleanField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'period_date')

    def __str__(self):
        return f'{self.user.username} {self.period_date} {"answered" if self.answered else "open"}'

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
        help_text="Буквы или символы через запятую: а,б,в,г,д,е,ё,ж,з,и,й,к,л,м,н,о,п,р,с,т,у,ф,х,ц,ч,ш,щ,ъ,ы,ь,э,ю,я,-,/,\\,|,_"  # можно добавлять любые символы
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
    correct_letters = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Правильные буквы (через запятую)"
    )

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



class Punktum(models.Model):
    """
    Пунктограмма — тип пунктуации (запятая, тире, скобки и т.д.).
    Аналог Orthogram, но для знаков препинания.
    """
    id = models.CharField(max_length=10, primary_key=True)  # '16', '17', '21'
    name = models.CharField(max_length=200)
    rule = models.TextField()
    
    # Символы для выпадающего списка: ! = запятая, ? = нет запятой
    letters = models.CharField(
        max_length=200,
        default='!, ?',
        help_text="Символы через запятую: !, ?, -, (, ), [, ]"
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        help_text="Через запятую: 5,6,7"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def get_letters_list(self):
        return [letter.strip() for letter in self.letters.split(',') if letter.strip()]

    def __str__(self):
        return f"{self.id}: {self.name}"


class PunktumExample(models.Model):
    """Пример для пунктуационного задания."""
    punktum = models.ForeignKey(
        Punktum, 
        on_delete=models.CASCADE,
    )
    text = models.TextField()
    masked_word = models.TextField()
    explanation = models.TextField(blank=True, help_text="Правильные ответы через запятую: !, ?")
    correct_letters = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Правильные символы пунктуации (через запятую)"
    )
    difficulty = models.PositiveSmallIntegerField(default=1)
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
        if self.grades:
            return [
                int(g.strip())
                for g in self.grades.split(',')
                if g.strip().isdigit()
            ]
        return []

    def __str__(self):
        grades_display = self.grades or 'все'
        return f"{self.text} (пунктограмма {self.punktum.id}, классы: {grades_display})"


class UserWord(models.Model):
    """Слова из планинга пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_words')
    field_name = models.CharField(max_length=100, db_index=True)
    text = models.CharField(max_length=255)
    
    # Связь с эталонной базой
    reference_word = models.ForeignKey(
        'OrthogramExample',
        null=True, blank=True,
        on_delete=models.SET_NULL
    )
    
    # Флаги
    in_master = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # 👇 НОВЫЕ ПОЛЯ ДЛЯ АДАПТИВНОСТИ
    weight = models.FloatField(default=1.0, help_text="Вес слова (чем выше, тем чаще показывается)")
    error_count = models.IntegerField(default=0, help_text="Сколько раз ошиблись")
    success_count = models.IntegerField(default=0, help_text="Сколько раз ответили правильно")
    last_shown = models.DateTimeField(null=True, blank=True)
    last_error = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # для отслеживания изменений

    class Meta:
        verbose_name = "Слово пользователя"
        verbose_name_plural = "Слова пользователей"
        unique_together = ['user', 'field_name', 'text']
        indexes = [
            models.Index(fields=['user', 'in_master', 'is_active']),
            models.Index(fields=['user', 'weight']),  # для сортировки по весу
        ]

    def update_weight(self):
        """Обновляет вес слова на основе ошибок"""
        # Базовая формула: вес = 1 + (ошибки * 2) - (успехи * 0.5)
        # Но вес не может быть меньше 0.5
        new_weight = 1.0 + (self.error_count * 2.0) - (self.success_count * 0.5)
        self.weight = max(0.5, min(10.0, new_weight))  # ограничиваем от 0.5 до 10
        self.save(update_fields=['weight', 'updated_at'])

    def __str__(self):
        return f"{self.user.username}: {self.text} (вес={self.weight:.1f})"
    
    
class QuizHistory(models.Model):
    """История ответов пользователя в квизах"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_history')
    word = models.ForeignKey('OrthogramExample', on_delete=models.CASCADE)
    user_word = models.ForeignKey('UserWord', null=True, blank=True, on_delete=models.SET_NULL)
    was_correct = models.BooleanField()
    answer_time = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "История квизов"
        verbose_name_plural = "История квизов"
        ordering = ['-answer_time']
        indexes = [
            models.Index(fields=['user', '-answer_time']),
            models.Index(fields=['user', 'was_correct']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.word.text} - {'✅' if self.was_correct else '❌'}"


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


class DiagnosticAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Владелец (NULL для анонимов)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name='diagnostic_attempts',
    )
    
    # Привязка для анонимов
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    access_code = models.CharField(max_length=12, unique=True, blank=True)
    
    # Что проходили
    test_code = models.CharField(max_length=50, default='DIAG_EGE_2027_V1')
    diagnostic_type = models.CharField(max_length=20, blank=True, verbose_name="Тип диагностики")

    # Результат
    primary_score = models.IntegerField(null=True, blank=True, verbose_name="Первичный балл")
    max_primary_score = models.IntegerField(default=50, verbose_name="Максимальный первичный балл")
    score = models.IntegerField(null=True, blank=True)
    max_score = models.IntegerField(default=50)
    answers_data = models.JSONField(default=dict)
    weak_topics = models.JSONField(default=list)
    
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # === Разбор преподавателем (зеркальная проверка на встрече) ===
    teacher_notes = models.TextField(blank=True, verbose_name="Заметки преподавателя")
    is_reviewed_by_teacher = models.BooleanField(default=False, verbose_name="Разобрано на встрече")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата разбора")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        owner = self.user.username if self.user else 'аноним'
        return f"{owner}: {self.score}/{self.max_score}"

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self):
        import random, string
        while True:
            code = 'DIAG-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not DiagnosticAttempt.objects.filter(access_code=code).exists():
                return code


# ========== ЗАДАНИЯ 1-3 ====================================================
class TextAnalysisTask(models.Model):
    """Текст с заданиями 1-3 или 23-26 (тип — в task_type)"""
    TASK_TYPES = (
        ('1_3', 'Задания 1–3 (микротекст)'),
        ('23_26', 'Задания 23–26 (макротекст)'),
    )
    title = models.CharField(max_length=200, verbose_name="Название")
    text_content = models.TextField(verbose_name="Текст")
    author = models.CharField(max_length=100, blank=True, verbose_name="Автор")
    source = models.CharField(max_length=200, blank=True, verbose_name="Источник")
    order = models.IntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    task_type = models.CharField(
        max_length=10, choices=TASK_TYPES, default='1_3', db_index=True,
        verbose_name="Тип текста",
        help_text="Микротекст — задания 1–3, макротекст — задания 23–26",
    )
    
    class Meta:
        verbose_name = "Текст для анализа 1–3"
        verbose_name_plural = "Тексты для анализа 1–3"
        ordering = ['order']
    
    def __str__(self):
        return self.title


class TextAnalysisTask2326(TextAnalysisTask):
    """Прокси-модель: отдельный блок админки для макротекстов (23–26)"""

    class Meta:
        proxy = True
        verbose_name = "Текст для анализа 23–26"
        verbose_name_plural = "Тексты для анализа 23–26"

    def __str__(self):
        return self.title


class TextQuestion(models.Model):
    """Вопрос к тексту (1, 2 или 3)"""
    QUESTION_TYPES = (
        ('missing_word', 'Подобрать слово'),
        ('multiple_choice', 'Множественный выбор'),
        ('text_characteristics', 'Характеристики текста'),
        ('free_text', 'Свободный текст (выписать из текста)'),
    )
    
    task = models.ForeignKey(TextAnalysisTask, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(max_length=50, choices=QUESTION_TYPES)
    question_text = models.TextField(verbose_name="Текст вопроса")
    question_number = models.IntegerField(verbose_name="Номер вопроса (2, 3, 4)")
    correct_answer = models.TextField(verbose_name="Правильный ответ")
    
    class Meta:
        verbose_name = "Вопрос к тексту"
        verbose_name_plural = "Вопросы к тексту"
        ordering = ['question_number']
    
    def __str__(self):
        return f"Вопрос {self.question_number} к {self.task.title}"


class QuestionOption(models.Model):
    """Варианты ответов для вопросов 2 и 3"""
    question = models.ForeignKey(TextQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.TextField(verbose_name="Текст варианта")
    option_number = models.IntegerField(verbose_name="Номер варианта")
    is_correct = models.BooleanField(default=False, verbose_name="Правильный")
    
    class Meta:
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"
        ordering = ['option_number']
    
    def __str__(self):
        return f"Вариант {self.option_number}"

# ====== ЗАДАНИЕ 4 =============================================================
class OrthoepyWord(models.Model):
    word = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Слово с ударением"
    )
    lemma = models.CharField(
        max_length=100,
        verbose_name="Лемма (слово без ударения)",
        help_text="Например: аэропорты, баловать"
    )
    is_correct = models.BooleanField(
        default=True,
        verbose_name="Правильное ударение",
        help_text="✓ — правильное, ✗ — неправильное"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активно"
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Классы",
        help_text="Например: 5,6,7"
    )

    class Meta:
        verbose_name = "Слово для орфоэпии"
        verbose_name_plural = "Слова для орфоэпии"
        ordering = ['word']

    def __str__(self):
        status = "✓" if self.is_correct else "✗"
        return f"{status} {self.word}"

    def get_grades_list(self):
        return [int(g.strip()) for g in self.grades.split(',') if g.strip().isdigit()]

    @staticmethod
    def generate_test(num_options=5, correct_min=2, correct_max=4, 
                     user_grade=None, test_type='main'):
        """
        Генерирует тест по орфоэпии с накопительной системой.
        
        Логика grades:
        - grades = '6' -> доступно для 6, 7, 8, 9, 10, 11
        - grades = '7' -> доступно для 7, 8, 9, 10, 11 (скрыто для 6)
        - grades = '10' -> доступно только для 10, 11
        """
        from django.db.models import Q
        import random
        import logging
        
        logger = logging.getLogger('django')

        # Базовый запрос: только активные слова
        queryset = OrthoepyWord.objects.filter(is_active=True)
        
        # === ФИЛЬТРАЦИЯ ПО КЛАССАМ (НАКОПИТЕЛЬНАЯ) ===
        if user_grade:
            suitable_words_ids = []
            # Получаем все активные слова (id и grades)
            all_words = list(queryset.values('id', 'grades'))
            
            for item in all_words:
                g_str = item['grades']
                
                # Если поле пустое, пропускаем (или можно считать доступным всем, если нужно)
                if not g_str: 
                    continue 
                
                try:
                    # Берем ПЕРВОЕ число из строки. 
                    # Если там "6", получим 6. Если "10", получим 10.
                    start_grade = int(g_str.split(',')[0].strip())
                    
                    # ГЛАВНОЕ ПРАВИЛО: 
                    # Если стартовый класс слова <= текущему классу ученика, слово подходит.
                    if start_grade <= user_grade:
                        suitable_words_ids.append(item['id'])
                        
                except (ValueError, IndexError):
                    continue
            
            # Фильтруем основной queryset по найденным ID
            if suitable_words_ids:
                queryset = queryset.filter(id__in=suitable_words_ids)
                logger.info(f"Орфоэпия: для {user_grade} класса найдено {queryset.count()} слов (накопительно)")
            else:
                logger.warning(f"Орфоэпия: для {user_grade} класса не найдено подходящих слов!")
                return None # Возвращаем None, если слов нет
        
        # Если user_grade нет (режим ЕГЭ без привязки), берем всё активное
        # Но для кнопки "ЕГЭ" лучше передавать grade=11, чтобы работала та же логика
        
        # Разделение на правильные и неправильные
        correct_words = list(queryset.filter(is_correct=True))
        incorrect_words = list(queryset.filter(is_correct=False))
        
        # Проверка достаточности данных
        if len(correct_words) < correct_min or len(incorrect_words) < 1:
            logger.warning(f"Недостаточно слов для генерации теста (правильных: {len(correct_words)}, неправильных: {len(incorrect_words)})")
            return None
        
        # Корректировка количества вариантов, если слов мало
        num_correct = random.randint(correct_min, min(correct_max, len(correct_words)))
        max_incorrect = num_options - num_correct
        num_incorrect = min(max_incorrect, len(incorrect_words))
        
        # Выбор уникальных лемм (чтобы не было пар типа "баловать/балУют" в одном тесте)
        selected_correct = []
        used_lemmas = set()
        random.shuffle(correct_words)
        for word in correct_words:
            if len(selected_correct) >= num_correct:
                break
            if word.lemma not in used_lemmas:
                selected_correct.append(word)
                used_lemmas.add(word.lemma)
        
        selected_incorrect = []
        random.shuffle(incorrect_words)
        for word in incorrect_words:
            if len(selected_incorrect) >= num_incorrect:
                break
            if word.lemma not in used_lemmas:
                selected_incorrect.append(word)
                used_lemmas.add(word.lemma)
        
        # Финальная проверка
        if len(selected_correct) < correct_min or len(selected_incorrect) < 1:
            return None
        
        # Сборка результата
        all_variants = selected_correct + selected_incorrect
        random.shuffle(all_variants)
        
        variants = [word.word for word in all_variants]
        correct_answers = [word.word for word in selected_correct]
        
        return {
            'variants': variants,
            'correct_answers': correct_answers,
        }

# === СЛОВАРЬ орфоэпии: прохождения и коррекция ===
class OrthoepyAttempt(models.Model):
    """Одно прохождение тренажёра."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orthoepy_attempts')
    created_at = models.DateTimeField(auto_now_add=True)
    total_words = models.IntegerField(default=0)
    chosen_count = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)

    def __str__(self):
        return f'{self.user.username} {self.created_at:%d.%m.%Y %H:%M}'


class OrthoepyAttemptWord(models.Model):
    """Результат по одному слову в прохождении."""
    attempt = models.ForeignKey(OrthoepyAttempt, on_delete=models.CASCADE, related_name='words')
    word_id = models.IntegerField()
    word = models.CharField(max_length=100)
    chosen_index = models.IntegerField()
    correct_index = models.IntegerField()
    is_correct = models.BooleanField()


class OrthoepyWordStat(models.Model):
    """Накопительная статистика по слову: прогресс и коррекция."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orthoepy_stats')
    word_id = models.IntegerField()
    word = models.CharField(max_length=100)
    correct_index = models.IntegerField(default=0)
    attempts = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    last_result = models.BooleanField(null=True)
    last_chosen_index = models.IntegerField(null=True)
    last_seen = models.DateTimeField(null=True)
    in_correction = models.BooleanField(default=False)
    correction_since = models.DateField(null=True)

    class Meta:
        unique_together = ('user', 'word_id')

    def __str__(self):
        return f'{self.user.username}: {self.word}'


# ===== ЛЕТОПИСЬ ЗАДАНИЯ 9 (алфавитные блоки тренажёров) ======================
class Task9Attempt(models.Model):
    """Одно прохождение алфавитного блока задания 9 (диапазон А-О, П-С и т.д.)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task9_attempts')
    orthogram_id = models.CharField(max_length=10, db_index=True)
    range_code = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)
    total_words = models.IntegerField(default=0)
    chosen_count = models.IntegerField(default=0)
    correct_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (f'{self.user.username} orth{self.orthogram_id}/{self.range_code} '
                f'{self.created_at:%d.%m.%Y %H:%M}')


class Task9AttemptWord(models.Model):
    """Результат по одному слову в прохождении: для летописи и разбора ошибок."""
    attempt = models.ForeignKey(Task9Attempt, on_delete=models.CASCADE, related_name='words')
    word = models.CharField(max_length=100)  # маскированное: з*1*мля
    chosen_letter = models.CharField(max_length=10, null=True, blank=True)
    correct_letter = models.CharField(max_length=10)
    is_correct = models.BooleanField()


class Task9WordStat(models.Model):
    """Накопительная статистика по слову: какие ошибки ставить на коррекцию."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task9_stats')
    orthogram_id = models.CharField(max_length=10)
    range_code = models.CharField(max_length=10)
    word = models.CharField(max_length=100)
    correct_letter = models.CharField(max_length=10)
    attempts = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    last_result = models.BooleanField(null=True, blank=True)
    last_chosen_letter = models.CharField(max_length=10, null=True, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    in_correction = models.BooleanField(default=False)
    correction_since = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'orthogram_id', 'word')
        ordering = ['-correction_since']

    def __str__(self):
        return f'{self.user.username}: {self.word} [orth{self.orthogram_id}]'


# ===== РУБЕЖНЫЕ ТЕСТЫ (чекпоинты между уроками) =============================
class CheckpointAttempt(models.Model):
    """Одна попытка рубежного теста (чекпоинта).

    checkpoint_code: 'cp9' — чекпоинт после урока 9, открывает урок 10.
    words_data: список слов попытки [{task, word, orthogram_id, correct}] —
    источник персонализации следующих попыток (ротация) и рекомендаций.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='checkpoint_attempts')
    checkpoint_code = models.CharField(max_length=20, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    correct_count = models.PositiveSmallIntegerField(default=0)
    error_count = models.PositiveSmallIntegerField(default=0)
    total_tasks = models.PositiveSmallIntegerField(default=9)
    passed = models.BooleanField(default=False, db_index=True)
    answers_data = models.JSONField(default=dict, blank=True)
    results_data = models.JSONField(default=dict, blank=True)
    words_data = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'checkpoint_code', '-created_at'])]

    def __str__(self):
        return (f'{self.user.username} {self.checkpoint_code}: '
                f'{self.correct_count}/{self.total_tasks}, {"сдан" if self.passed else "не сдан"}')


class CallbackRequest(models.Model):
    """Заявка на обратный звонок: преподаватель сам связывается с учеником.
    Оставляют анонимы после входящей диагностики."""
    name = models.CharField(max_length=100, blank=True, verbose_name='Имя')
    contact = models.CharField(max_length=100, verbose_name='Телефон или MAX')
    attempt = models.ForeignKey(
        'DiagnosticAttempt', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='callback_requests',
        verbose_name='Диагностика')
    source = models.CharField(max_length=50, blank=True, verbose_name='Откуда заявка')
    is_processed = models.BooleanField(default=False, verbose_name='Обработана')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка на звонок'
        verbose_name_plural = 'Заявки на звонок'
        ordering = ['-created_at']

    def __str__(self):
        when = self.created_at.strftime('%d.%m %H:%M')
        who = self.name or 'без имени'
        return f'{self.contact} ({who}), {when}'

# ===== ЗАДАНИЕ 5 ==============================================================
class TaskPaponim(models.Model):
    text = models.TextField(
        verbose_name="Предложение с выделенным словом",
        help_text="Выделите слово жирным, используя **двойные звёздочки**: ...**гарантийного**..."
    )
    correct_word = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Правильное слово (пароним)"
    )
    root = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Корень (для исключения в одном тесте)",
        help_text="Примеры: 'деть', 'гарант', 'абон'"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_for_quiz = models.BooleanField(default=False, verbose_name="Использовать в квизах")
    grades = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name="Классы"
    )

    @property
    def has_error(self):
        return bool(self.correct_word.strip())

    def __str__(self):
        return (self.text[:60] + '...') if len(self.text) > 60 else self.text

    class Meta:
        verbose_name = "ПАРОНИМЫ задание 5"
        verbose_name_plural = "ПАРОНИМЫ задание 5"


# ===== ЗАДАНИЕ 6 ==============================================================
class WordOk(models.Model):
    TYPE_CHOICES = [
        ('6100', 'Исключить лишнее слово'),
        ('6200', 'Заменить неверное слово'),
    ]

    text = models.TextField(
        verbose_name="Предложение с лексической ошибкой"
    )
    task_type = models.CharField(
        max_length=4,
        choices=TYPE_CHOICES,
        verbose_name="Тип задания"
    )
    # Для 6100: одно слово (лишнее)
    # Для 6200: список слов через запятую (все допустимые замены)
    correct_variants = models.TextField(
        verbose_name="Правильные слова (через запятую, без пробелов)",
        help_text="Для 6100 — одно слово. Для 6200 — варианты: одержать,совершить,добиться"
    )
    explanation = models.TextField(
        blank=True, default='',
        verbose_name="Объяснение ошибки (для RAG)",
        help_text="Короткое объяснение, почему слово лишнее/неверное. Используется ИИ-ассистентом"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_for_quiz = models.BooleanField(default=False, verbose_name="Использовать в квизах")
    grades = models.CharField(max_length=50, blank=True, verbose_name="Классы")

    def get_correct_words(self):
        return [w.strip().lower() for w in self.correct_variants.split(',') if w.strip()]

    def __str__(self):
        return (self.text[:60] + '...') if len(self.text) > 60 else self.text

    class Meta:
        verbose_name = "Задание 6: Лексические нормы"
        verbose_name_plural = "Задание 6: Лексические нормы"


# ===== ЗАДАНИЕ 7 ==============================================================

class CorrectionExercise(models.Model):
    """Упражнение: исправь ошибку 7 (свободный ввод)"""

    # Неправильный вариант (то, что видит ученик)
    incorrect_text = models.CharField(
        max_length=200,
        verbose_name="Неправильный текст (с ошибкой)",
        help_text="Пример: сожгет, чулков, замрзнул"
    )
    # Правильный вариант (эталон)
    correct_text = models.CharField(
        max_length=200,
        verbose_name="Правильный текст",
        help_text="Пример: сожжет, чулок, замерз"
    )
    # Описание ошибки (опционально)
    explanation = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Пояснение"
    )
    # Орфограмма или ID задания (например, '711')
    exercise_id = models.CharField(
        max_length=20,
        default='711',
        verbose_name="ID задания"
    )
    # Для каких классов
    grades = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Классы (через запятую)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    is_for_quiz = models.BooleanField(
        default=False,
        verbose_name="Для квизов",
        help_text="Использовать в квизах"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ЗАДАНИЕ 7: исправь ошибку"
        verbose_name_plural = "ЗАДАНИЕ 7: исправь ошибку"

    def __str__(self):
        return f"{self.incorrect_text} → {self.correct_text}"


    @staticmethod
    def generate_correction_test(num_options=5, wrong_count=1, user_grade=None):
        """
        Генерирует тест: 4 правильных + 1 неправильный, в случайном порядке.
        Ученик должен найти и исправить НЕПРАВИЛЬНЫЙ.
        """
        from django.db.models import Q
        import random
        exercises = CorrectionExercise.objects.filter(is_active=True)
        if user_grade:
            exercises = exercises.filter(
                Q(grades__contains=user_grade) | Q(grades='') | Q(grades__isnull=True)
            )
        exercises = list(exercises)
        if len(exercises) < num_options:
            return None

        # Выбираем 1 неправильный вариант (который нужно исправить)
        wrong_item = random.choice(exercises)

        # Выбираем 4 правильных из других упражнений
        correct_pool = [ex for ex in exercises if ex.id != wrong_item.id]
        if len(correct_pool) < num_options - wrong_count:
            return None
        correct_items = random.sample(correct_pool, num_options - wrong_count)

        # Создаём список всех слов (4 правильных + 1 неправильное)
        all_words = [ex.correct_text for ex in correct_items]  # 4 правильных
        all_words.append(wrong_item.incorrect_text)           # 1 неправильное

        # Перемешиваем случайным образом
        random.shuffle(all_words)

        return {
            'words': all_words,              # ← ВСЕ слова в случайном порядке
            'correct_answer': wrong_item.correct_text,  # эталон
            'exercise_id': wrong_item.exercise_id,
            'incorrect_word': wrong_item.incorrect_text,  # для проверки (не показываем!)
        }


# ===== ЗАДАНИЕ 8 ==============================================================

class TaskGrammaticEight(models.Model):
    ERROR_TYPES = [
        ('8100', 'Нарушение в построении предложения с подлежащим и сказуемым'),
        ('8200', 'Ошибка в построении предложения с причастным оборотом'),
        ('8300', 'Ошибка в построении предложения с деепричастным оборотом'),
        ('8400', 'Нарушение в построении предложения с однородными членами'),
        ('8500', 'Нарушение видо-временной соотнесённости глагольных форм'),
        ('8600', 'Нарушение в построении предложения с приложением'),
        ('8700', 'Нарушение в управлении (предлог + падеж)'),
        ('8800', 'Ошибка в построении предложения с косвенной речью'),
        ('8900', 'Нарушение в построении сложного предложения'),
        ('8910', 'Нарушение в употреблении числительного'),
    ]
    id = models.CharField(max_length=10, choices=ERROR_TYPES, primary_key=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.get_id_display()

    class Meta:
        verbose_name = "Тип ошибки (задание 8)"
        verbose_name_plural = "Типы ошибок (задание 8)"


class TaskGrammaticEightExample(models.Model):
    text = models.TextField()
    has_error = models.BooleanField(default=True)
    error_type = models.ForeignKey(
        TaskGrammaticEight,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to={'is_active': True}
    )
    explanation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_for_quiz = models.BooleanField(default=False)  # по умолчанию — не для квиза
    grades = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.text[:50]

    class Meta:
        verbose_name = "Пример для задания 8"
        verbose_name_plural = "Примеры для задания 8"

    @staticmethod
    def generate_task_eight_test(user_grade=None):
        import random
        from django.db.models import Q
        
        # Используем локальный импорт для избежания циклических зависимостей
        from .models import TaskGrammaticEight, TaskGrammaticEightExample

        # 1. Выбираем 5 случайных активных типа ошибок
        all_types = list(TaskGrammaticEight.objects.filter(is_active=True))
        if len(all_types) < 5:
            print(f"Активных типов меньше 5: {len(all_types)}")
            return None
        
        selected_types = random.sample(all_types, 5)
        selected_ids = [t.id for t in selected_types]
        print(f"Выбранные типы ошибок: {selected_ids}")

        # 2. Базовый queryset примеров
        examples_qs = TaskGrammaticEightExample.objects.filter(is_active=True)
        
        # 3. Примеры с ошибками — только для выбранных типов
        erroneous_qs = examples_qs.filter(has_error=True, error_type__id__in=selected_ids)
        
        print(f"Примеров с ошибками для выбранных типов: {erroneous_qs.count()}")
        
        # Собираем по одному примеру на каждый тип ошибки
        selected_erroneous = []
        for t_id in selected_ids:
            example = erroneous_qs.filter(error_type_id=t_id).first()
            if not example:
                print(f"Не найдено примера для типа ошибки: {t_id}")
                return None
            selected_erroneous.append(example)

        # 4. Примеры без ошибок
        correct_examples = list(examples_qs.filter(has_error=False))
        print(f"Примеров без ошибок: {len(correct_examples)}")
        
        if len(correct_examples) < 4:
            print(f"Недостаточно примеров без ошибок: {len(correct_examples)}")
            return None
            
        selected_correct = random.sample(correct_examples, 4)

        # 5. Перемешиваем
        all_selected = selected_erroneous + selected_correct
        random.shuffle(all_selected)

        # 6. Назначаем буквы А–Д
        letters = ['А', 'Б', 'В', 'Г', 'Д']
        type_to_letter = {selected_ids[i]: letters[i] for i in range(5)}

        # 7. Формируем данные
        answer_key = {}
        for ex in all_selected:
            if ex.has_error:
                answer_key[str(ex.id)] = type_to_letter.get(ex.error_type_id)
            else:
                answer_key[str(ex.id)] = None

        error_type_names = {
            type_to_letter[t_id]: TaskGrammaticEight.objects.get(id=t_id).get_id_display()
            for t_id in selected_ids
        }

        return {
            'sentences': [{'id': ex.id, 'text': ex.text} for ex in all_selected],
            'answer_key': answer_key,
            'error_type_names': error_type_names
        }


# ===== ЗАДАНИЕ 22 ==============================================================
class TaskGrammaticTwoTwo(models.Model):
    DEVICE_TYPES = [
        ('2201', 'эпитет'),
        ('2202', 'метафора'),
        ('2203', 'развернутая метафора'),
        ('2204', 'метонимия'),
        ('2205', 'синекдоха'),
        ('2206', 'олицетворение'),
        ('2207', 'сравнение'),
        ('2208', 'гипербола'),
        ('2209', 'литота'),
        ('2210', 'оксюморон'),
        ('2211', 'ирония'),
        ('2212', 'антитеза'),
        ('2213', 'анафора'),
        ('2214', 'эпифора'),
        ('2215', 'градация'),
        ('2216', 'парцелляция'),
        ('2217', 'риторическое обращение'),
        ('2218', 'риторический вопрос'),
        ('2219', 'инверсия'),
        ('2220', 'лексический повтор'),
        ('2221', 'вопросно-ответная форма изложения'),
        ('2222', 'цитирование'),
        ('2223', 'синтаксический параллелизм'),
        ('2224', 'многосоюзие'),
        ('2225', 'бессоюзие'),
        ('2226', 'аллитерация'),
        ('2227', 'ассонанс'),
        ('2228', 'индивидуально-авторское слово'),
    ]

    id = models.CharField(max_length=10, choices=DEVICE_TYPES, primary_key=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        # Простой и надежный способ
        return self.get_id_display()  # Это ДОЛЖНО работать для поля с choices!

    class Meta:
        verbose_name = "Средство выразительности (задание 22)"
        verbose_name_plural = "Средства выразительности (задание 22)"


class TaskGrammaticTwoTwoExample(models.Model):
    text = models.TextField()
    device_type = models.ForeignKey(
        TaskGrammaticTwoTwo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to={'is_active': True}
    )
    explanation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_for_quiz = models.BooleanField(default=False)
    grades = models.CharField(max_length=50, blank=True)
    author = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.text[:50]

    class Meta:
        verbose_name = "Пример для задания 22"
        verbose_name_plural = "Примеры для задания 22"


# ========================================================================
# ОГЭ — ОТДЕЛЬНЫЕ МОДЕЛИ (физически разные таблицы)
# ========================================================================

# ===== ТЕКСТЫ (Задания ОГЭ 2, 3, 6, 10, 11, 12) ==========================

class OgeTextAnalysisTask(models.Model):
    """Текст с заданиями ОГЭ"""
    title = models.CharField(max_length=200, verbose_name="Название")
    text_content = models.TextField(verbose_name="Текст")
    author = models.CharField(max_length=100, blank=True, verbose_name="Автор")
    source = models.CharField(max_length=200, blank=True, verbose_name="Источник")
    order = models.IntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активно")

    class Meta:
        verbose_name = "ОГЭ: Текст для анализа"
        verbose_name_plural = "ОГЭ: Тексты для анализа"
        ordering = ['order']

    def __str__(self):
        return self.title


class OgeTextQuestion(models.Model):
    """Вопрос к тексту ОГЭ"""
    QUESTION_TYPES = (
        ('missing_word', 'Подобрать слово'),
        ('multiple_choice', 'Множественный выбор'),
        ('text_characteristics', 'Характеристики текста'),
        ('free_text', 'Свободный текст (выписать из текста)'),
    )

    task = models.ForeignKey(OgeTextAnalysisTask, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(max_length=50, choices=QUESTION_TYPES)
    question_text = models.TextField(verbose_name="Текст вопроса")
    question_number = models.IntegerField(verbose_name="Номер вопроса (2–12)")
    correct_answer = models.TextField(verbose_name="Правильный ответ")

    class Meta:
        verbose_name = "ОГЭ: Вопрос к тексту"
        verbose_name_plural = "ОГЭ: Вопросы к тексту"
        ordering = ['question_number']

    def __str__(self):
        return f"Вопрос {self.question_number} к {self.task.title}"


class OgeQuestionOption(models.Model):
    """Варианты ответов для вопросов ОГЭ"""
    question = models.ForeignKey(OgeTextQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.TextField(verbose_name="Текст варианта")
    option_number = models.IntegerField(verbose_name="Номер варианта")
    is_correct = models.BooleanField(default=False, verbose_name="Правильный")
    orthogram_numbers = models.CharField(max_length=255, blank=True, verbose_name="№№ орфограмм (для ответа)")

    class Meta:
        verbose_name = "ОГЭ: Вариант ответа"
        verbose_name_plural = "ОГЭ: Варианты ответов"
        ordering = ['option_number']

    def __str__(self):
        return f"Вариант {self.option_number}"


# ===== ЗАДАНИЕ ОГЭ 4: Выпадающие списки ================================

class OgeTaskGrammaticEight(models.Model):
    id = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=300, blank=True, default='', verbose_name="Описание правила")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name or self.id

    class Meta:
        verbose_name = "ОГЭ: Пунктуационное правило (задание 4)"
        verbose_name_plural = "ОГЭ: Пунктуационные правила (задание 4)"


class OgeTaskGrammaticEightExample(models.Model):
    text = models.TextField()
    has_error = models.BooleanField(default=True)
    error_type = models.ForeignKey(
        OgeTaskGrammaticEight,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to={'is_active': True}
    )
    explanation = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_for_quiz = models.BooleanField(default=False)
    grades = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.text[:50]

    class Meta:
        verbose_name = "ОГЭ: Пример для задания 4"
        verbose_name_plural = "ОГЭ: Примеры для задания 4"


# ===== ЗАДАНИЕ ОГЭ 5: Пунктуация (смайлики) ============================

class OgePunktum(models.Model):
    """
    Пунктограмма ОГЭ — тире, двоеточие, запятая, КАВЫЧКИ.
    """
    id = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=200)
    rule = models.TextField()

    letters = models.CharField(
        max_length=200,
        default='!, ?, —, :, «»',
        help_text="Символы через запятую: !, ?, —, :, «» (кавычки)"
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        help_text="Через запятую: 5,6,7"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def get_letters_list(self):
        raw = self.letters or ''
        # Если в строке есть пробел — считаем что разделитель пробел
        # (это позволяет использовать запятую как вариант ответа)
        if ' ' in raw:
            return [letter.strip() for letter in raw.split(' ') if letter.strip()]
        return [letter.strip() for letter in raw.split(',') if letter.strip()]

    def __str__(self):
        return f"{self.id}: {self.name}"

    class Meta:
        verbose_name = "ОГЭ: Пунктограмма (задание 5)"
        verbose_name_plural = "ОГЭ: Пунктограммы (задание 5)"


class OgePunktumExample(models.Model):
    """Пример для пунктуационного задания ОГЭ."""
    punktum = models.ForeignKey(
        OgePunktum,
        on_delete=models.CASCADE,
    )
    text = models.TextField()
    masked_word = models.TextField()
    explanation = models.TextField(blank=True, help_text="Правильные ответы через запятую: !, ?, «»")
    correct_letters = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Правильные символы пунктуации (через запятую)"
    )
    difficulty = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    is_for_quiz = models.BooleanField(default=True, verbose_name="Использовать в квизах")
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
        verbose_name="Поле-источник"
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        help_text="Через запятую: 5,6,7"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def get_grades_list(self):
        if self.grades:
            return [
                int(g.strip())
                for g in self.grades.split(',')
                if g.strip().isdigit()
            ]
        return []

    def __str__(self):
        grades_display = self.grades or 'все'
        return f"{self.text[:40]} (пунктограмма {self.punktum.id}, классы: {grades_display})"

    class Meta:
        verbose_name = "ОГЭ: Пример пунктуации (задание 5)"
        verbose_name_plural = "ОГЭ: Примеры пунктуации (задание 5)"


# ===== ЗАДАНИЕ ОГЭ 7: Орфография (смайлики букв) =======================

class OgeOrthogram(models.Model):
    id = models.CharField(max_length=10, primary_key=True)
    name = models.CharField(max_length=200)
    rule = models.TextField()
    letters = models.CharField(
        max_length=200,
        default='а,о,е,и,я',
        help_text="Буквы через запятую"
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        help_text="Через запятую: 5,6,7"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def get_letters_list(self):
        return [letter.strip() for letter in self.letters.split(',') if letter.strip()]

    def __str__(self):
        return f"{self.id}: {self.name}"

    class Meta:
        verbose_name = "ОГЭ: Орфограмма (задание 7)"
        verbose_name_plural = "ОГЭ: Орфограммы (задание 7)"


class OgeOrthogramExample(models.Model):
    orthogram = models.ForeignKey(OgeOrthogram, on_delete=models.CASCADE)
    text = models.CharField(max_length=300)
    masked_word = models.CharField(max_length=300)
    incorrect_variant = models.CharField(max_length=300, blank=True, null=True)
    explanation = models.TextField(blank=True)
    correct_letters = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Правильные буквы (через запятую)"
    )
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
        verbose_name="Поле-источник"
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        help_text="Через запятую: 5,6,7"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def get_grades_list(self):
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

    class Meta:
        verbose_name = "ОГЭ: Пример орфограммы (задание 7)"
        verbose_name_plural = "ОГЭ: Примеры орфограмм (задание 7)"


# ===== ЗАДАНИЯ ОГЭ 8, 9: Инпуты ========================================

class OgeCorrectionExercise(models.Model):
    """ОГЭ: Исправь ошибку (свободный ввод)"""
    incorrect_text = models.CharField(
        max_length=200,
        verbose_name="Неправильный текст (с ошибкой)"
    )
    correct_text = models.CharField(
        max_length=200,
        verbose_name="Правильный текст"
    )
    explanation = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Пояснение"
    )
    exercise_id = models.CharField(
        max_length=20,
        default='711',
        verbose_name="ID задания"
    )
    grades = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Классы (через запятую)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    is_for_quiz = models.BooleanField(default=False, verbose_name="Для квизов")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ОГЭ: Задание 8 — исправь ошибку"
        verbose_name_plural = "ОГЭ: Задание 8 — исправь ошибку"

    def __str__(self):
        return f"{self.incorrect_text} → {self.correct_text}"

    @staticmethod
    def generate_correction_test(num_options=5, wrong_count=1, user_grade=None):
        from django.db.models import Q
        import random
        exercises = OgeCorrectionExercise.objects.filter(is_active=True)
        if user_grade:
            exercises = exercises.filter(
                Q(grades__contains=user_grade) | Q(grades='') | Q(grades__isnull=True)
            )
        exercises = list(exercises)
        if len(exercises) < num_options:
            return None

        wrong_item = random.choice(exercises)
        correct_pool = [ex for ex in exercises if ex.id != wrong_item.id]
        if len(correct_pool) < num_options - wrong_count:
            return None
        correct_items = random.sample(correct_pool, num_options - wrong_count)

        all_words = [ex.correct_text for ex in correct_items]
        all_words.append(wrong_item.incorrect_text)
        random.shuffle(all_words)

        return {
            'words': all_words,
            'correct_answer': wrong_item.correct_text,
            'exercise_id': wrong_item.exercise_id,
            'incorrect_word': wrong_item.incorrect_text,
        }


class OgeWordOk(models.Model):
    TYPE_CHOICES = [
        ('6100', 'Исключить лишнее слово'),
        ('6200', 'Заменить неверное слово'),
    ]

    text = models.TextField(verbose_name="Предложение с лексической ошибкой")
    task_type = models.CharField(max_length=4, choices=TYPE_CHOICES, verbose_name="Тип задания")
    correct_variants = models.TextField(
        verbose_name="Правильные слова (через запятую)",
        help_text="Для 6100 — одно слово. Для 6200 — варианты: одержать,совершить"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_for_quiz = models.BooleanField(default=False, verbose_name="Для квизов")
    grades = models.CharField(max_length=50, blank=True, verbose_name="Классы")

    def get_correct_words(self):
        return [w.strip().lower() for w in self.correct_variants.split(',') if w.strip()]

    def __str__(self):
        return (self.text[:60] + '...') if len(self.text) > 60 else self.text

    class Meta:
        verbose_name = "ОГЭ: Задание 9 — лексические нормы"
        verbose_name_plural = "ОГЭ: Задание 9 — лексические нормы"

# === Отслеживание активности на дашборде ===

class LessonView(models.Model):
    """Просмотр урока."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_views')
    lesson_code = models.CharField(max_length=100)   # идентификатор урока
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'lesson_code')

    def __str__(self):
        return f'{self.user.username} → {self.lesson_code}'


class PaponimView(models.Model):
    """Просмотр статьи паронима."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paponim_views')
    paponim_code = models.CharField(max_length=100)   # идентификатор пары паронимов
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'paponim_code')

    def __str__(self):
        return f'{self.user.username} → {self.paponim_code}'


class EssayScore(models.Model):
    """Балл за сочинение (задание 27 ЕГЭ). Обновляется по прохождению курса."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='essay_score')
    score = models.FloatField(default=0.0)           # текущий балл
    max_score = models.FloatField(default=22.0)      # максимум для ЕГЭ (задание 27)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username}: {self.score}/{self.max_score}'


# === История диалогов с ИИ-ассистентом (вместо кэша) ===

class ChatMessage(models.Model):
    """Один ход диалога с ИИ-ассистентом: вопрос ученика + ответ."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    message = models.TextField()
    reply = models.TextField(default='')
    intent = models.CharField(max_length=50, default='')
    specialist = models.CharField(max_length=50, default='')
    guessed_word = models.CharField(max_length=100, null=True, blank=True)
    feedback = models.SmallIntegerField(null=True, blank=True)   # 1 = 👍, -1 = 👎, None = нет оценки
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} [{self.intent}]: {self.message[:40]}'


class AiQueryLog(models.Model):
    """Лог каждого запроса к ИИ: фундамент аналитики качества и будущего дообучения."""
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='ai_query_logs')
    message = models.TextField()                                     # вопрос ученика
    intent = models.CharField(max_length=50, default='', blank=True)
    specialist = models.CharField(max_length=50, default='', blank=True)
    reply = models.TextField(blank=True, default='')                 # ответ ассистента
    guessed_word = models.CharField(max_length=100, null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)         # время ответа
    error = models.TextField(blank=True, default='')                 # ошибка, если была
    chat_message = models.ForeignKey('ChatMessage', null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='query_logs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Запрос к ИИ'
        verbose_name_plural = 'Логи запросов к ИИ'

    def __str__(self):
        return f'{self.user_id} [{self.specialist or "?"}]: {self.message[:40]}'

# ===== РЕЕСТР ТЕМ RAG (Фаза 4) =================================================

class RagTopic(models.Model):
    """
    Реестр тем RAG: какие источники знаний готовы отвечать ученикам.
    Флаг is_ready — решение разработчика/методиста: бот отвечает по теме
    ТОЛЬКО после включения. Счётчик примеров — подсказка для решения.
    """
    code = models.CharField(max_length=50, unique=True, verbose_name="Код темы")
    name = models.CharField(max_length=150, verbose_name="Название")
    description = models.TextField(blank=True, default='', verbose_name="Описание")
    source = models.CharField(max_length=150, blank=True, default='',
                              verbose_name="Источник данных")
    is_ready = models.BooleanField(default=False, verbose_name="Готова отвечать")
    order = models.IntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ['order']
        verbose_name = 'Тема RAG'
        verbose_name_plural = 'Реестр тем RAG'

    def examples_count(self):
        """Живой счётчик примеров в источнике — подсказка для решения о готовности."""
        try:
            if self.code == 'task3_analysis':
                return -1  # секции md, считаются отдельно
            if self.code == 'task4_stress':
                return OrthoepyWord.objects.filter(is_active=True).count()
            if self.code == 'task5_paronyms':
                import json
                from pathlib import Path
                path = Path(__file__).parent / 'fixtures' / 'paponims.json'
                if path.exists():
                    return len(json.load(open(path, encoding='utf-8')))
                return 0
            if self.code == 'task6_lexical':
                return WordOk.objects.filter(is_active=True).count()
            if self.code == 'task7_morphological':
                return CorrectionExercise.objects.filter(is_active=True).count()
            if self.code == 'task9_1_vowels':
                return OrthogramExample.objects.filter(
                    orthogram_id=1, is_active=True
                ).exclude(explanation='').exclude(explanation__isnull=True).count()
        except Exception:
            return -1
        return 0

    def __str__(self):
        mark = '✅' if self.is_ready else '⏳'
        return f'{mark} {self.name}'


# === ИИ БОТА: кэш ответов и журнал диалогов ===

class LLMCache(models.Model):
    """Кэш ответов LLM: одинаковые вопросы отвечаются мгновенно и бесплатно."""
    cache_key = models.CharField(max_length=64, unique=True, db_index=True)
    category = models.CharField(max_length=30)
    question = models.TextField(blank=True, default='')
    answer = models.TextField()
    provider = models.CharField(max_length=30, blank=True, default='')
    model = models.CharField(max_length=60, blank=True, default='')
    hits = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Кэш LLM'
        verbose_name_plural = 'Кэш LLM'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.category}] {self.question[:40]}'


class BotLog(models.Model):
    """Журнал диалогов бота: аналитика «что спрашивают» и качество ответов."""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='bot_logs')
    username = models.CharField(max_length=150, blank=True, default='')
    platform = models.CharField(max_length=10, default='site')  # site / vk / max
    question = models.TextField(blank=True, default='')
    answer = models.TextField(blank=True, default='')
    category = models.CharField(max_length=30, blank=True, default='')
    specialist = models.CharField(max_length=60, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Лог бота'
        verbose_name_plural = 'Логи бота'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%d.%m %H:%M} [{self.platform}] {self.question[:40]}'

