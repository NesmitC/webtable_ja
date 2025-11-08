# main/assistant.py
from datetime import timedelta  # type: ignore
from django.utils import timezone  # type: ignore
from .models import UserExample, OrthogramExample, UserProfile




class NeuroAssistant:
    def __init__(self, user_id):
        self.user_id = user_id
        self.profile = UserProfile.objects.get(user_id=user_id)
        self.grade = self.profile.grade

    def analyze_current_exercise(self, user_words, exercise_context=None):
        """
        Анализирует ТОЛЬКО ЧТО ВЫПОЛНЕННОЕ упражнение.
        user_words: список слов, собранных учеником (например, ['вода', 'цветы'])
        exercise_context: опционально — данные об упражнении (например, orthogram_id)
        """
        results = []
        weak_orthograms = set()
        mistakes = []

        for word in user_words:
            # Ищем слово в базе (регистронезависимо)
            example = OrthogramExample.objects.filter(
                text__iexact=word,
                is_active=True
            ).first()

            is_correct = example is not None

            if not is_correct:
                mistakes.append(word)

            if example:
                orth_id = example.orthogram_id
                results.append({
                    'word': word,
                    'is_correct': True,
                    'orthogram_id': orth_id,
                    'explanation': example.explanation or example.orthogram.rule,
                    'example': example
                })
                # Если ошибка — запоминаем орфограмму как слабую
                if not is_correct:
                    weak_orthograms.add(orth_id)
            else:
                results.append({
                    'word': word,
                    'is_correct': False,
                    'orthogram_id': None,
                    'explanation': "Это слово не найдено в нашей базе. Возможно, ошибка в написании.",
                    'example': None
                })

        return {
            'results': results,
            'mistakes': mistakes,
            'weak_orthograms': list(weak_orthograms)
        }

    def get_planning_words(self):
        """Возвращает ВСЕ слова из UserExample — независимо от field_name"""
        planning_entries = UserExample.objects.filter(
            user_id=self.user_id
        )
        words = []
        for entry in planning_entries:
            words.extend(entry.content.splitlines())
        return [w.strip().lower() for w in words if w.strip()]

    def get_analogous_examples(self, orthogram_id, exclude_word=None, limit=3):
        """Возвращает аналогичные слова для объяснения"""
        queryset = OrthogramExample.objects.filter(
            orthogram_id=orthogram_id,
            is_active=True
        )
        if exclude_word:
            queryset = queryset.exclude(text__iexact=exclude_word)
        return queryset[:limit]

    def generate_explanation_for_mistakes(self, analysis_result):
        """
        Генерирует текстовое объяснение на основе анализа ошибок
        """
        mistakes = analysis_result['mistakes']
        results = analysis_result['results']

        if not mistakes:
            return "Отлично! Все слова написаны правильно. Так держать!"

        explanations = []
        for item in results:
            if not item['is_correct']:
                explanations.append(f"• «{item['word']}» — {item['explanation']}")
            else:
                # Для правильных слов — можно не объяснять, или дать краткое подтверждение
                pass

        # Добавляем аналоги для первой ошибки
        first_mistake_item = next((item for item in results if not item['is_correct']), None)
        if first_mistake_item and first_mistake_item['example']:
            orth_id = first_mistake_item['orthogram_id']
            analogs = self.get_analogous_examples(orth_id, exclude_word=first_mistake_item['word'])
            if analogs:
                analog_words = ", ".join([ex.text for ex in analogs])
                explanations.append(f"\nЗапомни похожие слова: {analogs_words}.")

        return "\n".join(explanations) if explanations else "Обрати внимание на написание этих слов."


        
    def get_planning_count(self):
        return len(self.get_planning_words())

    def get_progress_summary(self):
        """
        Возвращает реальную статистику по прогрессу ученика.
        """
        planning_count = self.get_planning_count()
        return {
            'total_answers': 0,
            'correct_answers': 0,
            'success_rate': 0,
            'weak_orthograms': 0,
            'planning_words': planning_count,
            'summary': f"У тебя {planning_count} слов в планинге. Выполняй упражнения, чтобы я мог отслеживать твой прогресс!"
        }



    def get_orthogram_for_word(self, word):
        """Возвращает орфограмму для слова (первую найденную)"""
        example = OrthogramExample.objects.filter(
            text__iexact=word,
            is_active=True
        ).first()
        return example.orthogram if example else None

    def generate_advice_for_exercise(self, analysis_result):
        """
        Генерирует персонализированный комментарий по результатам упражнения
        """
        mistakes = analysis_result['mistakes']

        if not mistakes:
            return "Отлично! Все правильно. Так держать! Двигайся дальше — выполни другие упражнения."

        # Если есть ошибки — попробуем определить орфограмму
        first_mistake_word = next((item for item in analysis_result['results'] if not item['is_correct']), None)

        orthogram = None
        if first_mistake_word and first_mistake_word['example']:
            orthogram = first_mistake_word['example'].orthogram

        # По умолчанию — общий текст
        advice = "Выполнено с ошибками. "
        advice += "Постарайся сам разобраться — найди в планинге твой случай, прочитай объяснение, запиши слово в ячейку. Тут нужно подумать!\n\n"
        advice += "Если сложно — Нейростат поможет."

        # Специфичные комментарии по орфограмме
        if orthogram:
            if orthogram.id == '2':
                advice = "Выполнено с ошибками. "
                advice += "Слова на орфоргамму 2 запоминаются, поэтому записывай их в ячейку - это будет твой словарик! "

            elif orthogram.id == '661':
                advice = "Ты допустил ошибки в предлогах (орфограмма 66.1). Попробуй вспомнить, что пишется на конце производных предлогов. Посмотри (создай) словарик в планинге. "
                advice += "Запиши слово в планинг."

            # Добавляй новые орфограммы по мере необходимости

        return advice
    
    


    def get_quiz_question(self):
        """Генерирует вопрос дня для квиза (с двумя кнопками)"""
        # Берём случайный пример для орфограммы 661, который помечен как is_for_quiz=True
        examples = OrthogramExample.objects.filter(
            orthogram__id='661',
            is_for_quiz=True,
            is_active=True
        ).order_by('?')[:1]

        if not examples:
            return None

        example = examples[0]
        correct_word = example.text
        incorrect_word = example.incorrect_variant

        # Генерируем текст вопроса с смайликом
        question_text = example.masked_word.replace(f"*{example.orthogram.id}*", "😊")

        return {
            'question': f"Как правильно пишется:\n\n{question_text}",
            'options': [
                {'text': correct_word, 'is_correct': True},
                {'text': incorrect_word, 'is_correct': False}
            ],
            'explanation': example.explanation or example.orthogram.rule,
            'orthogram_id': example.orthogram.id
        }
        
    
    def get_planning_count(self):
        """Возвращает количество слов в планинге"""
        words = self.get_planning_words()
        return len(words)
    
    
    def get_weekly_report(self):
        week_ago = timezone.now() - timedelta(days=7)
        answers = StudentAnswer.objects.filter(
            user_id=self.user_id,
            answered_at__gte=week_ago
        )

        if not answers.exists():
            return {
                'status': 'inactive',
                'message': 'За последнюю неделю ты не выполнял упражнений. Пора начать!'
            }

        total = answers.count()
        correct = answers.filter(is_correct=True).count()
        success_rate = round(correct / total * 100, 1)

        # Топ-3 слабых орфограмм
        from django.db.models import Count
        weak_orthograms = answers.filter(is_correct=False)\
            .values('orthogram__id', 'orthogram__name')\
            .annotate(errors=Count('id'))\
            .order_by('-errors')[:3]

        return {
            'status': 'active',
            'total': total,
            'correct': correct,
            'success_rate': success_rate,
            'weak_orthograms': list(weak_orthograms),
            'message': f"Ты выполнил {total} заданий, {correct} из них — правильно ({success_rate}%)."
        }