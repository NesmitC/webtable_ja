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

# ==============================================================================
class TextAnalysisTask(models.Model):
    """Текст с заданиями 1-3"""
    title = models.CharField(max_length=200, verbose_name="Название")
    text_content = models.TextField(verbose_name="Текст")
    author = models.CharField(max_length=100, blank=True, verbose_name="Автор")
    source = models.CharField(max_length=200, blank=True, verbose_name="Источник")
    order = models.IntegerField(default=0, verbose_name="Порядок")
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    
    class Meta:
        verbose_name = "Текст для анализа 1-3"
        verbose_name_plural = "Тексты для анализа 1-3"
        ordering = ['order']
    
    def __str__(self):
        return self.title


class TextQuestion(models.Model):
    """Вопрос к тексту (1, 2 или 3)"""
    QUESTION_TYPES = (
        ('missing_word', 'Подобрать слово'),
        ('multiple_choice', 'Множественный выбор'),
        ('text_characteristics', 'Характеристики текста'),
    )
    
    task = models.ForeignKey(TextAnalysisTask, on_delete=models.CASCADE, related_name='questions')
    question_type = models.CharField(max_length=50, choices=QUESTION_TYPES)
    question_text = models.TextField(verbose_name="Текст вопроса")
    question_number = models.IntegerField(verbose_name="Номер вопроса (1, 2, 3)")
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

# ==============================================================================
class OrthoepyWord(models.Model):
    correct_variant = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Слово с правильным ударением"
    )
    incorrect_variants = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Неправильные варианты"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    is_for_quiz = models.BooleanField(
        default=False,
        verbose_name="Для квизов",
        help_text="Используется в будущих квизах (не в основном тесте)"
    )
    grades = models.CharField(max_length=50, blank=True, verbose_name="Классы")

    class Meta:
        verbose_name = "Слово для орфоэпии"
        verbose_name_plural = "Слова для орфоэпии"
        ordering = ['correct_variant']

    def __str__(self):
        return self.correct_variant

    def get_incorrect_variants_list(self):
        return [v.strip() for v in self.incorrect_variants.split(',') if v.strip()]

    def get_all_variants(self):
        return [self.correct_variant] + self.get_incorrect_variants_list()

    def get_grades_list(self):
        return [int(g.strip()) for g in self.grades.split(',') if g.strip().isdigit()]

    @staticmethod
    def generate_test(num_options=5, correct_min=2, correct_max=4, user_grade=None):
        from django.db.models import Q
        import random

        # Получаем активные слова
        words = OrthoepyWord.objects.filter(is_active=True)
        if user_grade:
            words = words.filter(Q(grades__contains=user_grade) | Q(grades='') | Q(grades__isnull=True))
        words = list(words)

        if len(words) < num_options:
            return None

        # 🔴 Шаг 1: Выбираем случайные РАЗНЫЕ слова
        selected_words = random.sample(words, num_options)
        
        # 🔴 Шаг 2: Для каждого слова выбираем ОДИН вариант
        all_variants = []
        selected_correct = []
        
        for word in selected_words:
            # Все варианты для этого слова
            word_variants = word.get_all_variants()
            
            # Если у слова только один вариант (правильный)
            if len(word_variants) == 1:
                variant = word.correct_variant
                selected_correct.append(variant)
            else:
                # Выбираем случайный вариант
                variant = random.choice(word_variants)
                if variant == word.correct_variant:
                    selected_correct.append(variant)
            
            all_variants.append(variant)
        
        # 🔴 Шаг 3: Корректируем количество правильных ответов
        current_correct = len(selected_correct)
        
        # Если правильных слишком мало
        if current_correct < correct_min:
            needed = correct_min - current_correct
            changed = 0
            
            for i, word in enumerate(selected_words):
                if changed >= needed:
                    break
                    
                current_variant = all_variants[i]
                # Если текущий вариант неправильный
                if current_variant != word.correct_variant:
                    # Меняем на правильный
                    all_variants[i] = word.correct_variant
                    if word.correct_variant not in selected_correct:
                        selected_correct.append(word.correct_variant)
                    changed += 1
        
        # Если правильных слишком много
        elif current_correct > correct_max:
            extra = current_correct - correct_max
            
            for i, word in enumerate(selected_words):
                if extra <= 0:
                    break
                    
                current_variant = all_variants[i]
                # Если текущий вариант правильный и есть неправильные альтернативы
                if current_variant == word.correct_variant and word.get_incorrect_variants_list():
                    # Меняем на случайный неправильный
                    all_variants[i] = random.choice(word.get_incorrect_variants_list())
                    selected_correct.remove(word.correct_variant)
                    extra -= 1
        
        return {
            'variants': all_variants,
            'correct_answers': selected_correct,
            'correct_ids': [],
        }

# ==============================================================================

# main/models.py
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
