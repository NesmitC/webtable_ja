from django.db import models
import random
from django.db.models import Q
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

# ========== ЗАДАНИЯ 1-3 ====================================================
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
        ('free_text', 'Свободный текст (выписать из текста)'),
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
        Генерирует тест по орфоэпии
        
        Гарантии:
        - 2-4 правильных варианта
        - 1-3 неправильных варианта
        - НЕТ повторений лемм в одном тесте
        """
        from django.db.models import Q
        import random

        # Фильтруем только активные слова
        queryset = OrthoepyWord.objects.filter(is_active=True)
        
        # Фильтрация по классам
        if user_grade:
            queryset = queryset.filter(
                Q(grades__contains=str(user_grade)) | 
                Q(grades='') | 
                Q(grades__isnull=True)
            )
        
        # Разделяем на правильные и неправильные
        correct_words = list(queryset.filter(is_correct=True))
        incorrect_words = list(queryset.filter(is_correct=False))
        
        # Проверяем, достаточно ли слов
        if len(correct_words) < correct_min or len(incorrect_words) < 1:
            return None
        
        # Случайное количество правильных ответов (2-4)
        num_correct = random.randint(correct_min, correct_max)
        num_incorrect = num_options - num_correct
        
        # Если неправильных слов меньше, чем нужно — корректируем
        if len(incorrect_words) < num_incorrect:
            num_incorrect = len(incorrect_words)
            num_correct = num_options - num_incorrect
        
        # === ВЫБИРАЕМ УНИКАЛЬНЫЕ ЛЕММЫ ===
        selected_correct = []
        used_lemmas = set()
        
        # Выбираем правильные варианты с уникальными леммами
        random.shuffle(correct_words)
        for word in correct_words:
            if len(selected_correct) >= num_correct:
                break
            if word.lemma not in used_lemmas:
                selected_correct.append(word)
                used_lemmas.add(word.lemma)
        
        # Выбираем неправильные варианты с уникальными леммами
        selected_incorrect = []
        random.shuffle(incorrect_words)
        for word in incorrect_words:
            if len(selected_incorrect) >= num_incorrect:
                break
            if word.lemma not in used_lemmas:
                selected_incorrect.append(word)
                used_lemmas.add(word.lemma)
        
        # Проверяем, что набрали достаточно вариантов
        if len(selected_correct) < num_correct or len(selected_incorrect) < num_incorrect:
            return None
        
        # Объединяем и перемешиваем
        all_variants = selected_correct + selected_incorrect
        random.shuffle(all_variants)
        
        # Формируем результат
        variants = [word.word for word in all_variants]
        correct_answers = [word.word for word in selected_correct]
        
        return {
            'variants': variants,
            'correct_answers': correct_answers,
        }

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
