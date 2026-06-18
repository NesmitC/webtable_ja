# main/assistants/teacher_russian.py
"""
Нейро-преподаватель: Русский язык
Приоритет: БД → pymorphy3 (с пометкой) → ЛЛМ (few-shot) → Заглушка
"""

import re
from typing import Optional, List, Tuple

from main.models import OrthogramExample
from main.assistants.knowledge_loader import knowledge_manager

try:
    from main.llm_utils import call_deepseek
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# 🔹 Морфологический анализатор (pymorphy3)
try:
    import pymorphy3
    MORPH = pymorphy3.MorphAnalyzer()
    print("✅ pymorphy3 loaded")
except ImportError:
    MORPH = None
    print("⚠️ pymorphy3 not available")


class TeacherRussian:
    """
    Обработчик запросов по русскому языку.
    Стратегия: БД (источник истины) → pymorphy3 (справочно) → ЛЛМ (форматирование)
    """
    
    def __init__(self):
        self.kb_manager = knowledge_manager
        self.subject = "russian"
    
    # ========================================================================
    # 🔹 FEW-SHOT ПРОМПТ: примеры для ЛЛМ
    # ========================================================================
    
    FEW_SHOT_EXAMPLES = """
ПРИМЕРЫ ПРАВИЛЬНЫХ ОТВЕТОВ (точно так же):

• «красивый» — это прилагательное, обозначает признак предмета, отвечает на вопрос какой?
• «медлить» — это глагол, обозначает действие, отвечает на вопрос что делать?
• «поняв» — это деепричастие, образовано от глагола «понять», обозначает добавочное действие, отвечает на вопрос что сделав?
• «смеявшийся» — это причастие, образовано от глагола «смеяться», обозначает признак предмета по действию, отвечает на вопрос какой?
• «быстро» — это наречие, обозначает признак действия, отвечает на вопрос как?
• «книга» — это существительное, обозначает предмет или понятие, отвечает на вопрос что?
• «и» — это союз.
• «в» — это предлог.
"""
    
    # ========================================================================
    # 🔹 ГЛАВНЫЙ МЕТОД: обработка запроса
    # ========================================================================
    
    def handle(self, user, message, context, history=None) -> str:
        print(f"\n🔹 TeacherRussian: '{message[:100]}'")
        
        # 🔹 Если это уточнение после ошибки — даём человеческий ответ
        if context.get('prev_intent') in ['clarification', 'unknown']:
            return "Уточни, пожалуйста: ты про ЕГЭ, правило или что-то другое?"
        
        # 🔹 1. Обработка подтверждения после уточнения
        if history and len(history) > 0:
            last = history[-1]
            if last.get('intent') == 'clarification' and last.get('guessed_word'):
                if message.lower().strip() in ['да', 'yes', 'ага', 'точно', 'правильно', 'ок']:
                    message = f"почему {last['guessed_word']}"
        
        # 🔹 2. Извлекаем слово
        word = self._extract_word(message)
        print(f"  📝 Word: '{word}'")
        
        # 🔹 3. ПРИОРИТЕТ 1: БД (источник истины)
        if word:
            db_entry = OrthogramExample.objects.filter(
                text__iexact=word,
                is_active=True,
                is_user_added=False
            ).select_related('orthogram').first()
            
            if db_entry and db_entry.explanation:
                print(f"  ✅ БД: найдено")
                return self._format_from_db(db_entry)
        
        # 🔹 4. ПРИОРИТЕТ 2: pymorphy3 (с пометкой, если нет в БД)
        if word and MORPH:
            morph_answer = self._format_from_morphology(word)
            if morph_answer:
                print(f"  ✅ pymorphy3: {morph_answer[:50]}...")
                return morph_answer
        
        # 🔹 5. ПРИОРИТЕТ 3: Теория из Markdown-справочника
        intent, terms = self._analyze_question(message)
        if intent in ['definition', 'rule_explanation'] and terms:
            md_result = self._search_markdown(message, terms)
            if md_result:
                print(f"  ✅ Markdown: найдено")
                return self._clean_response(md_result)
        
        # 🔹 6. ПРИОРИТЕТ 4: ЛЛМ с few-shot промптом (только если разрешено)
        if word and LLM_AVAILABLE:
            llm_answer = self._generate_with_few_shot(word)
            if llm_answer:
                print(f"  ✅ LLM (few-shot): {llm_answer[:50]}...")
                return f"{llm_answer}\n\n⚠️ Это слово пока нет в нашей базе. Добавьте в планинг для точного объяснения!"
        
        # 🔹 7. Fallback: честная заглушка
        if word:
            return f"🤔 Слова «{word}» пока нет в нашей базе.\n\n💡 Добавьте его в планинг — и мы подготовим объяснение!"
        
        return self._ask_clarification(message)
    
    # ========================================================================
    # 🔹 Форматирование из БД (приоритет)
    # ========================================================================
    
    def _format_from_db(self, example) -> str:
        """Формирует ответ из данных БД — 100% точность"""
        answer = f"📖 {example.text}\n\n💡 {example.explanation}"
        
        if example.orthogram:
            answer += f"\n\n📚 Орфограмма №{example.orthogram_id}: {example.orthogram.name}"
        
        return answer.strip()
    
    # ========================================================================
    # 🔹 Форматирование из pymorphy3 (с пометкой)
    # ========================================================================
    
    def _format_from_morphology(self, word: str) -> Optional[str]:
        """
        Определяет часть речи через pymorphy3.
        Возвращает ответ с пометкой, если слова нет в БД.
        """
        if not MORPH:
            return None
        
        try:
            parse = MORPH.parse(word)[0]
            tag = parse.tag
            normal_form = parse.normal_form
            
            # 🔹 Надёжное получение POS
            pos = getattr(tag, 'POS', None)
            tag_str = str(tag).upper()
            
            # 🔹 Словарь шаблонов
            POS_TEMPLATES = {
                'NOUN': ('существительное', 'предмет, лицо, явление или понятие', 'кто? / что?'),
                'ADJF': ('прилагательное', 'признак предмета', 'какой?'),
                'ADJS': ('прилагательное (краткое)', 'признак предмета', 'каков?'),
                'PRON': ('местоимение', 'указание на предмет/признак без названия', 'кто? / какой?'),
                'NUMR': ('числительное', 'количество или порядок при счёте', 'сколько? / который?'),
                'VERB': ('глагол', 'действие или состояние', 
                        'что сделать?' if 'PERF' in tag_str else 'что делать?'),
                'PRTF': ('причастие', 'признак предмета по действию', 'какой?'),
                'PRTS': ('причастие (краткое)', 'признак предмета по действию', 'каков?'),
                'GRND': ('деепричастие', 'добавочное действие', 
                        'что сделав?' if 'PERF' in tag_str else 'что делая?'),
                'ADVB': ('наречие', 'признак действия', 'как?'),
                'PREP': ('предлог', '', ''),
                'CONJ': ('союз', '', ''),
                'PRCL': ('частица', '', ''),
                'INTJ': ('междометие', '', ''),
            }
            
            # 🔹 Ищем совпадение
            matched_pos = None
            for pos_tag in POS_TEMPLATES:
                if pos == pos_tag or pos_tag in tag_str:
                    matched_pos = pos_tag
                    break
            
            if not matched_pos:
                return None
            
            pos_name, meaning, question = POS_TEMPLATES[matched_pos]
            
            # 🔹 Решаем, добавлять ли "образовано от"
            # Только для форм, образованных от глаголов (причастия, деепричастия, глаголы)
            needs_origin = matched_pos in ['PRTF', 'PRTS', 'GRND'] and normal_form.lower() != word.lower()

            # 🔹 Формируем ответ
            if matched_pos in ['PREP', 'CONJ', 'PRCL', 'INTJ', 'VERB']:
                return f"«{word}» — это {pos_name}."
            elif needs_origin:
                return (f"«{word}» — это {pos_name}, образовано от «{normal_form}», "
                    f"обозначает {meaning}, отвечает на вопрос {question}")
            else:
                return (f"«{word}» — это {pos_name}, обозначает {meaning}, отвечает на вопрос {question}")
            
        except Exception as e:
            print(f"⚠️ Morph error: {e}")
            return None
    
    # ========================================================================
    # 🔹 ЛЛМ с few-shot промптом
    # ========================================================================
    
    def _generate_with_few_shot(self, word: str) -> Optional[str]:
        """
        Генерирует ответ через ЛЛМ с few-shot примерами.
        Используется только если слова нет в БД и pymorphy3 не справился.
        """
        if not LLM_AVAILABLE:
            return None
        
        system = f"""Ты — учитель русского языка. Определи часть речи слова.

ОТВЕЧАЙ СТРОГО ПО ШАБЛОНУ (без отклонений):

🔹 Для причастий и деепричастий (образованы от глаголов):
«[слово]» — это [часть речи], образовано от глагола «[инфинитив]», обозначает [значение], отвечает на вопрос [вопрос]

🔹 Для остальных самостоятельных частей речи:
«[слово]» — это [часть речи], обозначает [значение], отвечает на вопрос [вопрос]

🔹 Для служебных частей речи:
«[слово]» — это [союз/предлог/частица].

{self.FEW_SHOT_EXAMPLES}

ПРАВИЛА:
1. ТОЛЬКО одна строка, точно по шаблону
2. Без приветствий, без пояснений, без рекламы
3. Кавычки-ёлочки « »
4. НЕ добавляй "образовано от" для прилагательных, существительных, наречий
5. В вопросе УЖЕ есть знак "?" — не добавляй второй в конце!
6. Для глаголов: «что делать?» (несов. вид) или «что сделать?» (сов. вид)
7. Для причастий: «какой?», для деепричастий: «что делая?» / «что сделав?»"""

        user = f"""Слово: {word}

Определи часть речи и ответь по шаблону:"""

        try:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ]
            response = call_deepseek(messages)
            
            # 🔹 Проверка, что ответ в нужном формате
            if response and any(kw in response for kw in ['это', 'образовано', 'отвечает']):
                return response.strip()
            
            return None
            
        except Exception as e:
            print(f"⚠️ LLM few-shot error: {e}")
            return None
    
    # ========================================================================
    # 🔹 Вспомогательные методы
    # ========================================================================
    
    def _clean_response(self, response: str) -> str:
        """Очищает ответ, сохраняя формат"""
        if not response:
            return response
        
        # Если ответ уже в нужном формате — не трогаем
        if re.match(r'^«?.+?»? — это ', response):
            return response.strip()
        
        paragraphs = response.split('\n\n')
        if paragraphs:
            first = paragraphs[0]
            first = re.sub(r'^Привет,?\s*\w*!?\s*', '', first)
            first = re.sub(r'^👋\s*', '', first)
            return first.strip()
        
        return response
    
    def _search_markdown(self, question: str, terms: List[str]) -> Optional[str]:
        """Ищет теорию в Markdown-справочнике"""
        try:
            kbs = self.kb_manager.get_knowledge_base(self.subject)
            if not kbs:
                return None
            
            q_lower = question.lower()
            
            topic_mapping = {
                'причастие': ['причастие', 'причастия'],
                'деепричастие': ['деепричастие', 'деепричастия'],
                'прилагательное': ['прилагательное', 'прилагательные'],
                'глагол': ['глагол', 'глаголы'],
                'нн_в_причастиях': ['нн', 'причастия', 'пишется'],
            }
            
            for topic, keywords in topic_mapping.items():
                if any(kw in q_lower for kw in keywords):
                    for kb in kbs:
                        for topic_id, section in kb.sections.items():
                            if topic in topic_id.lower():
                                content = self._clean_markdown(section['content'])
                                return content[:500] + "..." if len(content) > 500 else content
            
            return None
        except Exception as e:
            print(f"⚠️ Markdown search error: {e}")
            return None
    
    def _clean_markdown(self, text: str) -> str:
        """Очищает Markdown от разметки"""
        text = re.sub(r'#{1,6}\s*', '', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\|.*?\|', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    def _analyze_question(self, question: str) -> Tuple[str, List[str]]:
        """Определяет интент и извлекает термины"""
        q_lower = question.lower()
        terms = []
        
        term_dict = {
            'причастие': ['причастие', 'причастия', 'причастный'],
            'деепричастие': ['деепричастие', 'деепричастия'],
            'прилагательное': ['прилагательное', 'прилагательные'],
            'глагол': ['глагол', 'глаголы'],
            'нн': ['нн', 'две н'],
        }
        
        for term, keywords in term_dict.items():
            for kw in keywords:
                if kw in q_lower:
                    terms.append(term)
                    break
        
        terms = list(set(terms))
        
        if any(w in q_lower for w in ['отличие', 'разница', 'чем отличается']):
            intent = 'comparison'
        elif any(w in q_lower for w in ['что такое', 'определение', 'понятие']):
            intent = 'definition'
        else:
            intent = 'general'
        
        return intent, terms
    
    def _extract_word(self, message: str) -> Optional[str]:
        """Извлекает слово из запроса (от 3 букв)"""
        # Если вопрос теоретический — не извлекаем
        if any(q in message.lower() for q in ['что такое', 'объясни правило', 'чем отличается', 'определение']):
            return None
        
        # Ищем слова от 3 букв
        words = re.findall(r'[а-яё]{3,}', message.lower())
        
        # Исключаем служебные слова вопроса
        excluded = {
            'что', 'как', 'так', 'вот', 'это', 'того', 'чего',
            'какая', 'какой', 'какие', 'часть', 'речи', 'слово',
            'про', 'тебя', 'меня', 'у', 'слова', 'есть', 'для'
        }
        
        for word in words:
            if word not in excluded:
                return word
        
        return None
    
    def _ask_clarification(self, message: str) -> str:
        """Просит пользователя уточнить запрос"""
        words = re.findall(r'[а-яё]{3,}', message.lower())
        words = [w for w in words if w not in ['что', 'как', 'так', 'вот', 'это', 'про', 'слово']]
        
        if words:
            guessed_word = words[0]
            return f"🤔 Вы имели в виду слово «{guessed_word}»? Напишите «Да» или задайте вопрос иначе."
        else:
            return "🤔 Напишите конкретное слово, например: «почему вода?» или «какая часть речи у слова красивый?»"