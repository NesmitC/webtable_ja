# main/assistants/analyst.py
"""
Нейро-аналитик
Отвечает на вопросы УЧЕНИКА о статистике, прогрессе, рекомендациях
"""

from main.llm_utils import call_deepseek, get_fallback_response, INJECTION_GUARD, user_block


class Analyst:
    def handle(self, user, message, context, history=None):
        """Обрабатывает запрос к аналитику"""
        
        # Формируем промпт со статистикой
        prompt = self._build_analyst_prompt(message, context['stats'], user.username)
        
        reply = call_deepseek(prompt)
        
        return reply
    
    def _build_analyst_prompt(self, message, stats, username):
        """Формирует промпт для DeepSeek"""
        system_prompt = """Ты — Нейро-аналитик образовательной платформы.
        
        Твоя задача:
        1. Показывай статистику понятно и мотивирующе
        2. Давай персонализированные рекомендации
        3. Поддерживай ученика, но не хвали чрезмерно
        4. Используй эмодзи (📊 🎯 ✅)"""
        
        stats_text = f"""
        Статистика {username}:
        • Всего квизов: {stats['total']}
        • Правильно: {stats['correct']} ({stats['rate']}%)
        """ if stats else "Статистика пока недоступна"
        
        question_block = user_block(message)
        user_prompt = f"""
        {stats_text}
        
        ВОПРОС:
        {question_block}
        
        ОТВЕТ:"""
        
        return [
            {"role": "system", "content": system_prompt + "\n" + INJECTION_GUARD},
            {"role": "user", "content": user_prompt}
        ]