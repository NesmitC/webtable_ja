# main/assistant.py
"""
Оркестратор Нейро-команды
Маршрутизирует запросы между специалистами
"""

import re
from main.llm_utils import call_deepseek, get_fallback_response

from .assistants.teacher_russian import TeacherRussian
from .assistants.analyst import Analyst
from .assistants.methodist import Methodist
from .assistants.marketing import Marketing


class NeuroOrchestrator:
    """Единая точка входа для всех запросов к чат-боту"""
    
    def __init__(self):
        self.teacher = TeacherRussian()
        self.analyst = Analyst()
        self.methodist = Methodist()
        self.marketing = Marketing()
    
    def get_response(self, user, message, conversation_history=None):
        """
        Главный метод: принимает запрос → возвращает ответ
        """
        if isinstance(user, str):
            print(f"⚠️ WARNING: user passed as string '{user}' instead of User object")
            username = user
        else:
            username = user.username if user else 'anonymous'
        
        # Проверяем, не ответ ли это на уточнение
        if conversation_history and len(conversation_history) > 0:
            last = conversation_history[-1]
            if isinstance(last, dict):
                last_intent = last.get('intent')
                last_guess = last.get('guessed_word')
                
                if last_intent == 'clarification' and last_guess:
                    if message.lower().strip() in ['да', 'yes', 'ага', 'точно', 'правильно', 'ок']:
                        message = f"почему {last_guess}"
                        print(f"✅ Подтверждено: {last_guess}")
        
        # Классифицируем интент
        intent = self._classify_intent(message)
        
        # Выбираем специалиста
        specialist = self._select_specialist(intent)
        
        # Собираем контекст
        context = self._build_context(user, intent)
        
        # Передаём запрос специалисту
        response = specialist.handle(user, message, context, conversation_history)
        
        # Логируем
        log_data = {
            'user': username,
            'message': message[:50],
            'response': response[:50],
            'intent': intent,
            'specialist': specialist.__class__.__name__
        }
        
        if intent == 'clarification':
            words = re.findall(r'[а-яё]{3,}', message.lower())
            words = [w for w in words if w not in ['что', 'как', 'так', 'вот', 'это', 'про', 'слово']]
            if words:
                log_data['guessed_word'] = words[0]
        
        self._log_query(**log_data)
        
        return {
            'reply': response,
            'specialist': specialist.__class__.__name__,
            'intent': intent,
            'guessed_word': log_data.get('guessed_word')
        }
    
    def _classify_intent(self, message):
        """
        Определяет намерение пользователя по ключевым словам
        """
        message_lower = message.lower().strip()
        
        # ✅ Ответ на уточнение
        if message_lower in ['почему', 'а почему', 'как так', 'что', '??', '???']:
            # Если в истории был провал (intent='clarification' или fallback)
            # → возвращаем специальный интент для уточнения
            return 'follow_up'
        
        # 🔥 Части речи (ВАЖНО: ставим выше маркетинга!)
        if any(k in message_lower for k in [
            'какая часть речи', 'часть речи', 'причастие', 'деепричастие',
            'глагол', 'существительное', 'прилагательное', 'наречие',
            'местоимение', 'числительное', 'союз', 'предлог'
        ]):
            return 'parts_of_speech'
        
        # 📚 Орфография
        if any(k in message_lower for k in [
            'как пишется', 'почему', 'орфогр', 'корень', 'пристав', 'суффикс',
            'безударн', 'проверочн', 'пишется', 'объясни', 'правописани', 'написани'
        ]):
            return 'orthography'
        
        # ✍️ Пунктуация
        if any(k in message_lower for k in [
            'запят', 'тире', 'двоеточ', 'пунктуаци', 'обособл', 'причаст', 'деепричаст'
        ]):
            return 'punctuation'
        
        # 📊 Статистика и прогресс
        if any(k in message_lower for k in [
            'статистик', 'прогресс', 'ошибк', 'повтор', 'слаб', 'результат'
        ]):
            return 'stats'
        
        # 📋 ЕГЭ/ОГЭ
        if any(k in message_lower for k in [
            'егэ', 'огэ', 'критерий', 'апелляц', 'балл', 'экзамен', 'структур'
        ]):
            return 'ege'
        
        # 💰 Маркетинг (только если нет других совпадений)
        if any(k in message_lower for k in [
            'тариф', 'цена', 'стоим', 'оплат', 'купить', 'пробн', 'регистрац',
            'привет', 'помощ', 'начать', 'где', 'как', 'нейростат'
        ]):
            return 'marketing'
        
        # ❌ Не поняли — нужно уточнение
        return 'clarification'
    
    def _select_specialist(self, intent):
        """Выбирает специалиста по интенту"""
        mapping = {
            'parts_of_speech': self.teacher,    # 👈 Добавили
            'follow_up': self.teacher,  # TeacherRussian умеет задавать уточняющие вопросы
            'orthography': self.teacher,
            'punctuation': self.teacher,
            'confirmation': self.teacher,
            'stats': self.analyst,
            'ege': self.methodist,
            'marketing': self.marketing,
            'clarification': self.teacher,
            'unknown': self.teacher
        }
        return mapping.get(intent, self.teacher)
    
    def _build_context(self, user, intent):
        """Собирает релевантный контекст из БД"""
        context = {
            'user': user,
            'intent': intent,
            'stats': None,
            'planning_words': [],
            'weak_topics': [],
            'orthogram_rule': None
        }
        
        if isinstance(user, str):
            return context
        
        if intent == 'stats':
            try:
                from main.models import QuizHistory, UserWord
                total = QuizHistory.objects.filter(user=user).count()
                correct = QuizHistory.objects.filter(user=user, was_correct=True).count()
                context['stats'] = {
                    'total': total,
                    'correct': correct,
                    'rate': round(correct / total * 100) if total > 0 else 0
                }
            except Exception as e:
                print(f"⚠️ Stats context error: {e}")
        
        if intent in ['orthography', 'punctuation', 'parts_of_speech', 'confirmation', 'clarification']:
            try:
                from main.models import UserWord
                context['planning_words'] = list(
                    UserWord.objects.filter(user=user, is_active=True)
                    .values_list('text', flat=True)[:10]
                )
            except Exception as e:
                print(f"⚠️ Planning context error: {e}")
        
        return context
    
    def _log_query(self, user, message, response, intent, specialist, guessed_word=None):
        """Логирует запрос для аналитики"""
        if guessed_word:
            print(f"📝 [{specialist}] {user}: {message[:50]} → {response[:50]} [guess: {guessed_word}]")
        else:
            print(f"📝 [{specialist}] {user}: {message[:50]} → {response[:50]}")


# Глобальный экземпляр
_orchestrator = None

def get_orchestrator():
    """Возвращает единый экземпляр оркестратора"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = NeuroOrchestrator()
    return _orchestrator