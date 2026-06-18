# main/assistants/methodist.py
"""
Нейро-методист
Отвечает на вопросы по ЕГЭ/ОГЭ: структура, критерии, апелляция
"""

import re
from main.llm_utils import call_deepseek, get_fallback_response
from main.assistants.knowledge_loader import knowledge_manager


class Methodist:

    def _search_knowledge_base(self, question: str) -> str:
        """Ищет ответ в methodic.md по простым правилам"""
        try:
            kbs = knowledge_manager.get_knowledge_base('russian')
            if not kbs:
                return None
            
            q = question.lower()
            
            # 🔹 Прямые ответы на частые вопросы (быстрый путь)
            quick_answers = {
                'сколько времени': '3 часа 30 минут (210 минут).',
                'длится экзамен': '3 часа 30 минут (210 минут).',
                '210 минут': '3 часа 30 минут (210 минут).',
                'бланк №1': 'Для заданий 1–26 (краткий ответ).',
                'бланк №2': 'Для сочинения (задание 27).',
                'задание 8': 'Оценивается в 2 балла. 1 балл — при 1-2 ошибках.',
                'задание 22': 'Оценивается в 2 балла. 1 балл — при 1-2 ошибках.',
                'часть 1': '26 заданий с кратким ответом.',
                'часть 2': '1 задание — сочинение.',
            }
            
            for key, answer in quick_answers.items():
                if key in q:
                    return answer
            
            # 🔹 Если не нашли — ищем по ключевым словам в БД
            for kb in kbs:
                for topic_id, section in kb.sections.items():
                    content = section.get('content', '')
                    keywords = section.get('keywords', [])
                    
                    # Если вопрос содержит ключевое слово из БД
                    if any(kw in q for kw in keywords):
                        # Возвращаем первое предложение из секции
                        first_sent = re.split(r'[.!?]', content)[0].strip()
                        return first_sent + '.' if first_sent else None
            
            return None
        except Exception as e:
            print(f"⚠️ KB search error: {e}")
            return None

    def handle(self, user, message, context, history=None):
        # 🔹 1. Ищем в БД (methodic.md)
        kb_answer = self._search_knowledge_base(message)
        if kb_answer:
            return self._clean_answer(kb_answer)
        
        # 🔹 2. Если вопрос короткий/неясный — просим уточнить
        if self._is_ambiguous(message):
            return self._ask_clarification(message)
        
        # 🔹 3. Fallback: LLM с жёсткими ограничениями
        prompt = self._build_methodist_prompt(message, context.get('prev_question'))
        reply = call_deepseek(prompt)
        return self._clean_answer(reply)
    
    def _is_ambiguous(self, message: str) -> bool:
        """Проверяет, неясен ли вопрос"""
        msg = message.lower().strip()
        # Короткие вопросы без предмета
        short_patterns = [
            r'^каких? ', r'^что это', r'^какой ', r'^почему$', 
            r'^как$', r'^а если', r'^а что', r'^ну и'
        ]
        # Исключаем явные вопросы про экзамен
        exam_keywords = ['экзамен', 'егэ', 'огэ', 'задание', 'балл', 'время', 'часть']
        
        is_short = any(re.match(p, msg) for p in short_patterns)
        has_exam_kw = any(kw in msg for kw in exam_keywords)
        
        return is_short and not has_exam_kw
    
    def _ask_clarification(self, message: str) -> str:
        """Возвращает шаблонный запрос на уточнение"""
        return "Уточни, пожалуйста: ты про ЕГЭ или что-то другое?"
    
    def _build_methodist_prompt(self, message: str, context: str = None):
        system = """Ты — справочник по ЕГЭ/ОГЭ. Отвечай СТРОГО:

ПРАВИЛА:
1. ТОЛЬКО факты из официальных материалов ФИПИ
2. МАКСИМУМ 1-2 предложения, без списков и маркдауна
3. ❌ ЗАПРЕЩЕНО: упоминать тарифы, цены, подписки, «платформу», «аккаунт»
4. ЕСЛИ вопрос не про экзамен — напиши: «Это про ЕГЭ? Уточни, пожалуйста.»
5. ЕСЛИ не знаешь — «Нет данных по этому вопросу.»
6. БЕЗ вступлений, эмодзи (кроме ⚠️), ссылок

ПРИМЕРЫ:
В: Сколько времени? → О: 3 часа 30 минут (210 минут).
В: Структура? → О: 2 части, 27 заданий: часть 1 — 26 кратких, часть 2 — сочинение.
В: Каких частей? → О: Уточни: ты про части экзамена или что-то другое?
В: Сколько стоит? → О: Это про ЕГЭ? Уточни, пожалуйста."""

        # 🔹 Добавляем контекст, если есть
        ctx = f"\nКонтекст предыдущего вопроса: {context}" if context else ""
        
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Вопрос: {message}{ctx}\nОтвет:"}
        ]
    
    def _clean_answer(self, text: str) -> str:
        """Убирает маркдаун, списки, лишние переносы"""
        if not text:
            return "Нет данных."
        
        # 🔹 Удаляем маркдаун-разметку
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **жирный**
        text = re.sub(r'\*([^*]+)\*', r'\1', text)       # *курсив*
        text = re.sub(r'`([^`]+)`', r'\1', text)         # `код`
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # [ссылка](url)
        
        # 🔹 Удаляем маркеры списков
        text = re.sub(r'^[\*\-\•]\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s*', '', text, flags=re.MULTILINE)
        
        # 🔹 Берём только первое предложение/абзац
        text = text.split('\n\n')[0].strip()
        text = re.split(r'[.!?]', text)[0].strip() + '.'
        
        # 🔹 Обрезаем, если всё ещё длинно
        if len(text) > 200:
            text = text[:197] + '...'
        
        return text