# main/assistant.py
"""
Оркестратор Нейро-команды
Маршрутизирует запросы между специалистами
"""

import re
from django.conf import settings

from main.llm_utils import cached_llm, user_block, get_fallback_response
from main.assistants.knowledge_loader import knowledge_manager
from main.assistants.router import (
    route, WORD, THEORY, ESSAY, STATS, EGE, MARKETING,
    SUPPORT, MOTIVATION, PLATFORM, CLARIFY,
)

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
    
    def get_response(self, user, message, conversation_history=None, platform='site',
                       simplify=False):
        """
        Главный метод: принимает запрос → возвращает ответ
        """
        # 🔹 Санитизация входа: обрезка длины (защита от злоупотреблений)
        message = (message or '').strip()[:500]

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
                
                if last_intent in ('clarification', CLARIFY) and last_guess:
                    if message.lower().strip() in ['да', 'yes', 'ага', 'точно', 'правильно', 'ок']:
                        message = f"почему {last_guess}"
                        print(f"✅ Подтверждено: {last_guess}")
        
        # Классифицируем интент (ресепшен: правила → Qwen)
        intent = route(message)
        # Продающий диалог: цель/возражение после вопроса о тарифах
        if intent != MARKETING and conversation_history:
            _last = conversation_history[-1]
            if isinstance(_last, dict) and _last.get('intent') == MARKETING:
                from main.assistants.marketing import continues_sales_dialog
                if continues_sales_dialog(message):
                    intent = MARKETING

        # Новые категории обрабатываются напрямую, остальные — специалистами
        if intent in (THEORY, ESSAY, SUPPORT, MOTIVATION, PLATFORM):
            response = self._handle_direct(user, message, intent, simplify)
            specialist_name = 'Direct'
        else:
            specialist = self._select_specialist(intent)
            context = self._build_context(user, intent)
            response = specialist.handle(user, message, context, conversation_history)
            specialist_name = specialist.__class__.__name__

        buttons = None
        if isinstance(response, dict):
            buttons = response.get('buttons')
            response = response.get('reply', '')

        # Логируем
        log_data = {
            'user': username,
            'message': message[:50],
            'response': response[:50],
            'intent': intent,
            'specialist': specialist_name
        }

        if intent == CLARIFY:
            words = re.findall(r'[а-яё]{3,}', message.lower())
            words = [w for w in words if w not in ['что', 'как', 'так', 'вот', 'это', 'про', 'слово']]
            if words:
                log_data['guessed_word'] = words[0]
        
        self._log_query(user if not isinstance(user, str) else None,
                        username, platform, message, response,
                        intent, specialist_name)
        
        return {
            'reply': response,
            'specialist': specialist_name,
            'intent': intent,
            'guessed_word': log_data.get('guessed_word'),
            'buttons': buttons,
            'simplifiable': intent in (THEORY, MOTIVATION) and not simplify,
        }
    
    # ==================================================================
    # Прямые обработчики новых категорий (теория, сочинение, поддержка,
    # мотивация, платформа). Специалисты — в assistants/.
    # ==================================================================

    THEORY_SYSTEM = (
        f"Ты — {getattr(settings, 'BOT_NAME', 'Алекс')}, репетитор русского языка платформы "
        "Нейростат (подготовка к ЕГЭ). Объясни термин или правило просто и точно: "
        "2–4 предложения, один короткий пример. Говори по-человечески, без канцелярита "
        "и маркдауна. Если не уверен в фактах или вопрос не про русский язык ЕГЭ — "
        "честно скажи: «По этому пока нет проверенного объяснения — спроси преподавателя». "
        "Не выдумывай факты ФИПИ."
    )

    MOTIVATION_SYSTEM = (
        f"Ты — {getattr(settings, 'BOT_NAME', 'Алекс')}, наставник школьника, который готовится "
        "к ЕГЭ. Поддержи тепло и коротко (2–4 предложения). Не обесценивай "
        "(нельзя «не переживай», «это ерунда»), не давай медицинских советов. "
        "Признай чувство, напомни, что уставать — нормально, и предложи один маленький "
        "шаг: 10 минут квиза или слово дня."
    )

    SIMPLIFY_SUFFIX = (
        " А теперь объясни ещё проще: как для десятилетнего. "
        "Короткие предложения, бытовой пример, без терминов. До 3 предложений."
    )

    CRISIS_WORDS = ('не хочу жить', 'нет смысла жить', 'ненавижу себя',
                    'покончить', 'всё бессмысленно', 'исчезнуть')
    CRISIS_REPLY = (
        "Мне важно, что ты это написал. Пожалуйста, поговори со взрослым, которому "
        "доверяешь, и позвони на детскую линию 8-800-2000-122 — бесплатно и анонимно. "
        "Ты не один. А с ЕГЭ мы справимся шаг за шагом."
    )

    # Мини-глоссарий внутренних терминов платформы: отвечаем из паспорта,
    # а не из общих знаний LLM
    PLATFORM_GLOSSARY = {
        'квиз': ('Квиз в Нейростате — короткая тренировка: вопросы по словам из '
                 'твоего планинга и горячим темам. Решил — сразу видишь разбор '
                 'ошибок.'),
        'планинг': ('Планинг — твой личный словарь: записываешь слова-примеры, '
                    'и они попадают в личные квизы, пока не усвоишь их. Слово '
                    'можно стереть — и оно перестанет крутиться в квизах.'),
        'слово дня': ('«Слово дня» — одно слово с разбором каждый день, на сайте '
                      'и в ботах. Формат «10 минут в день»: в дороге и между '
                      'уроками.'),
        'диагностик': ('Диагностика — короткий тест, который показывает, на каких '
                       'заданиях теряются баллы. Бывает входящая, текущая и '
                       'контрольная — все видны в твоей статистике.'),
        'тренаж': ('Тренажёры — упражнения по заданиям ЕГЭ с мгновенной проверкой '
                   'и разбором ошибок.'),
    }

    def _platform_glossary(self, message):
        low = message.lower()
        for key, value in self.PLATFORM_GLOSSARY.items():
            if key in low:
                return value
        return None

    def _handle_direct(self, user, message, intent, simplify=False):
        """Раздача прямых обработчиков."""
        if intent == ESSAY:
            return self._reply_essay()
        if intent == SUPPORT:
            return self._reply_support(message)
        if intent == PLATFORM:
            return self._reply_platform(message)
        if intent == MOTIVATION:
            return self._reply_motivation(message, simplify)
        if intent == THEORY:
            return self._reply_theory(user, message, simplify)
        return get_fallback_response(message)

    def _reply_theory(self, user, message, simplify=False):
        """Теория: термины платформы → RAG (проверенное) → Qwen-объяснение."""
        gloss = self._platform_glossary(message)
        if gloss:
            return gloss
        try:
            from main.rag import search_knowledge, format_rag_answer
            rag = search_knowledge(message, user)
            if rag is not None:
                if rag.guard:
                    return rag.guard_message
                if rag.found:
                    return format_rag_answer(rag)
        except Exception as e:
            print(f"⚠️ RAG error: {e}")
        try:
            cat = 'theory_simple' if simplify else 'theory'
            system = self.THEORY_SYSTEM + (self.SIMPLIFY_SUFFIX if simplify else '')
            return cached_llm(cat, message, system, max_tokens=400)
        except Exception as e:
            print(f"⚠️ Theory LLM error: {e}")
            return ("🤔 Сейчас сервис объяснений занят. Попробуй через минуту "
                    "или спроси иначе, например: «что такое метонимия?»")

    def _reply_essay(self):
        return ("✍️ Сочинение проверяет эксперт ЕГЭ по официальным критериям — так честно. "
                "Отправь сочинение преподавателю на проверку, а ИИ-проверка скоро появится. "
                "Подсказка: за сочинение — до 24 из 58 баллов, поэтому уделяем ему особое внимание.")

    def _reply_support(self, message):
        section = self._kb_platform_search(message)
        if section:
            return section
        return ("😔 Похоже, что-то пошло не так. Я передал вопрос человеку — "
                f"он ответит на почту. Срочно: {settings.OWNER_NOTIFY_EMAIL}.")

    IDENTITY_KEYS = ('кто ты', 'кто ты такой', 'как тебя зовут', 'представься',
                     'ты кто', 'ты бот', 'ты робот')
    IDENTITY_REPLY = (
        "Я бот Алекс, твой персональный помощник в подготовке к ЕГЭ по русскому 🙂 "
        "Что я умею: объясню любое правило простыми словами (и ещё проще по кнопке «Простыми словами»), "
        "потренирую твои слова из планинга в квизах, "
        "подскажу, что учить завтра, если вижу слабую тему, и поддержу, когда тяжело. "
        "Напиши слово или вопрос и начнём!"
    )

    def _reply_platform(self, message):
        m = message.lower()
        if any(k in m for k in self.IDENTITY_KEYS):
            return self.IDENTITY_REPLY
        if any(k in m for k in ('привет', 'здравствуй', 'добрый')):
            return (f"Привет! Я {getattr(settings, 'BOT_NAME', 'Алекс')} — ассистент Нейростата. "
                    "Могу разобрать слово, объяснить правило, подсказать по ЕГЭ, "
                    "рассказать о тарифах и поддержать, когда тяжело. "
                    "Напиши слово или вопрос — или нажми кнопку меню.")
        gloss = self._platform_glossary(message)
        if gloss:
            return gloss
        section = self._kb_platform_search(message)
        if section:
            return section
        return ("Я ассистент Нейростата: разбираю слова и правила, подсказываю по ЕГЭ, "
                "тарифам и поддерживаю, когда тяжело. "
                "Спроси, например: «что такое метонимия?»")

    def _reply_motivation(self, message, simplify=False):
        if any(k in message.lower() for k in self.CRISIS_WORDS):
            return self.CRISIS_REPLY
        try:
            cat = 'motivation_simple' if simplify else 'motivation'
            system = self.MOTIVATION_SYSTEM + (self.SIMPLIFY_SUFFIX if simplify else '')
            return cached_llm(cat, message, system, max_tokens=300)
        except Exception as e:
            print(f"⚠️ Motivation LLM error: {e}")
            return ("Слышу тебя. Подготовка к ЕГЭ — марафон, и уставать — нормально. "
                    "Давай маленький шаг: 10 минут квиза или просто слово дня. "
                    "Ты уже молодец, что занимаешься.")

    def _kb_platform_search(self, query):
        """Ищет ответ только в platform.md — паспорте платформы."""
        try:
            results = knowledge_manager.search_all('russian', query, 2)
            results = [r for r in results if r.get('file') == 'platform.md']
            if results:
                text = results[0]['content']
                text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                return text.strip()[:600]
        except Exception as e:
            print(f"⚠️ Platform KB error: {e}")
        return None
    
    def _select_specialist(self, intent):
        """Выбирает специалиста по интенту"""
        mapping = {
            WORD: self.teacher,
            'parts_of_speech': self.teacher,
            'follow_up': self.teacher,
            'orthography': self.teacher,
            'punctuation': self.teacher,
            'confirmation': self.teacher,
            'clarification': self.teacher,
            'unknown': self.teacher,
            STATS: self.analyst,
            EGE: self.methodist,
            MARKETING: self.marketing,
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
        
        if intent in ['orthography', 'punctuation', 'parts_of_speech', 'confirmation',
                       'clarification', WORD, CLARIFY]:
            try:
                from main.models import UserWord
                context['planning_words'] = list(
                    UserWord.objects.filter(user=user, is_active=True)
                    .values_list('text', flat=True)[:10]
                )
            except Exception as e:
                print(f"⚠️ Planning context error: {e}")
        
        return context
    
    def _log_query(self, user_obj, username, platform, message, response,
                   intent, specialist):
        """Пишет диалог в БД (аналитика «что спрашивают») вместо print."""
        try:
            from main.models import BotLog
            BotLog.objects.create(
                user=user_obj, username=username, platform=platform,
                question=message[:500], answer=response[:1000],
                category=intent, specialist=specialist)
        except Exception as e:
            print(f"⚠️ BotLog error: {e}")


# Глобальный экземпляр
_orchestrator = None

def get_orchestrator():
    """Возвращает единый экземпляр оркестратора"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = NeuroOrchestrator()
    return _orchestrator