# main/rag.py
"""
RAG-движок Нейростат (Фаза 4).

Иерархический поиск по ПРОВЕРЕННЫМ источникам знаний. Принцип: чем ближе к
точному совпадению в БД, тем меньше свободы у LLM и тем выше точность.

Источники (по Реестру тем RagTopic, отвечают только при is_ready=True):
  task3_analysis     -> base_ru.md (анализ текста, стили)
  task4_stress       -> OrthoepyWord (ударения)
  task5_paronyms     -> paponims.json (паронимы)
  task6_lexical      -> WordOk (лексические нормы)
  task7_morphological-> CorrectionExercise (морфологические нормы)
  task9_1_vowels     -> OrthogramExample, orthogram_id=1 (проверяемые гласные корня)

Движок также реализует:
  - проверку ЛОЖНОЙ ПОСЫЛКИ (ученик пишет ошибочную форму -> твёрдое опровержение);
  - нейтральный отказ для тем ВНЕ охвата (задания 10-27);
  - мягкое сворачивание заданий 1-2 («нужен текст»).

LLM здесь НЕ сочиняет факты о языке — только отдаёт проверенные данные из БД.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from django.core.cache import cache

from main.models import (
    CorrectionExercise,
    OrthoepyWord,
    OrthogramExample,
    RagTopic,
    WordOk,
)

# База знаний для задания 3 (Markdown). Импортируем лениво, чтобы не падать,
# если загрузчик недоступен.
try:
    from main.assistants.knowledge_loader import knowledge_manager
    KB_AVAILABLE = True
except Exception:  # pragma: no cover
    knowledge_manager = None
    KB_AVAILABLE = False


# ============================================================================
# КОНСТАНТЫ СТИЛЯ (золотые образцы от методиста)
# ============================================================================

# Фирменная концовка: ведёт ученика в планинг. Добавляется к ответам по
# КОНКРЕТНОМУ слову (задания 4, 7, 9.1).
PLANNING_CLOSING = (
    "Запиши это слово в планинг — оно будет включено в квизы и слово дня, "
    "будет чаще встречаться в твоих тестах. Запомнится!"
)

# Нейтральный отказ для тем вне сентябрьского охвата. НЕ подтверждает и не
# опровергает ложную посылку — просто обозначает границы.
OUT_OF_SCOPE_MESSAGE = (
    "Эта тема пока в разработке — мы открываем задания по порядку. "
    "Сейчас полностью готовы задания 1–9.1: ударения, паронимы, "
    "проверяемые гласные в корне и другое. Спроси меня о них!"
)

# Мягкое сворачивание заданий 1-2 (нужен конкретный текст).
TASK12_MESSAGE = (
    "Задания 1–2 строятся вокруг конкретного текста, без него не ответить. "
    "Пришли мне фрагмент текста — посмотрим вместе, либо разберём это на занятии."
)

# Служебные слова, которые НЕ считаем значимыми при поиске слова в БД.
_STOPWORDS = {
    'что', 'как', 'так', 'вот', 'это', 'того', 'чего', 'какая', 'какой',
    'какие', 'какое', 'часть', 'речи', 'слово', 'слова', 'про', 'тебя',
    'меня', 'есть', 'для', 'почему', 'зачем', 'можно', 'ли', 'или', 'не',
    'ни', 'на', 'в', 'из', 'по', 'с', 'со', 'а', 'и', 'но', 'будет', 'было',
    'я', 'ты', 'он', 'она', 'они', 'мы', 'вы', 'кто', 'где', 'когда', 'уже',
    'ещё', 'еще', 'тоже', 'также', 'очень', 'просто', 'если', 'потому',
    'правильно', 'правильное', 'правильный', 'напиши', 'пишется', 'написание',
    'ударение', 'ударения', 'объясни', 'скажи', 'подскажи', 'помоги',
    'нужно', 'надо', 'это', 'такое', 'значит', 'означает',
}

# Темы вне охвата (задания 10-27). Консервативный список, чтобы не задеть
# общие вопросы. При срабатывании даём нейтральный отказ и логируем.
_OUT_OF_SCOPE_PATTERNS = [
    r'н\s*или\s*нн', r'нн\s*или\s*н', r'две\s+н', r'\bнн\b',
    r'н\s+в\s+причаст', r'нн\s+в\s+причаст', r'н\s+в\s+прилаг', r'нн\s+в\s+прилаг',
    r'пре\s*или\s*при', r'пре[-\s]при', r'приставк[аи]\s+пре', r'приставк[аи]\s+при',
    r'не\s+с\s+глагол', r'не\s+с\s+причаст', r'не\s+с\s+дееприч',
    r'не\s+с\s+существ', r'не\s+с\s+прилаг', r'не\s+с\s+нареч',
    r'не\s+слитно', r'не\s+раздельно', r'ни\s+или\s+не', r'не\s+или\s+ни',
    r'чтобы\s+или\s+что\s+бы', r'также\s+или\s+так\s+же', r'зато\s+или\s+за\s+то',
    r'тоже\s+или\s+то\s+же', r'притом\s+или\s+при\s+том', r'причем\s+или\s+при\s+чем',
    r'ё\s+после\s+шипящ', r'о\s+после\s+шипящ', r'е\s+или\s+ё',
    r'слитно\s+или\s+раздельно', r'слитно\s+раздельно\s+дефис',
    r'нареч\w+\s+слитно', r'нареч\w+\s+раздельно', r'нареч\w+\s+через\s+дефис',
    r'спряжени', r'окончани\w+\s+глагол', r'личн\w+\s+окончан',
    r'разноспрягаем', r'архаичн',
]
_OUT_OF_SCOPE_RE = re.compile('|'.join(_OUT_OF_SCOPE_PATTERNS), re.IGNORECASE)

# Маркеры заданий 1-2 (нужен конкретный текст).
_TASK12_PATTERNS = [
    r'задани\w+\s*[12]\b', r'средств\w+\s+связи', r'како\w+\s+слов\w+\s+пропущен',
    r'встав\w+\s+слов\w+', r'пропущен\w+\s+слов\w+',
]
_TASK12_RE = re.compile('|'.join(_TASK12_PATTERNS), re.IGNORECASE)


# ============================================================================
# РЕЗУЛЬТАТ ПОИСКА
# ============================================================================

@dataclass
class RagResult:
    """Структурированный результат поиска знаний."""
    found: bool = False
    # Охранники (guards): если задан, ответ не ищем, возвращаем guard_message.
    guard: Optional[str] = None            # 'out_of_scope' | 'task12'
    guard_message: str = ''
    # Данные ответа
    topic: str = ''                        # код темы из RagTopic
    false_premise: bool = False            # посылка ученика ошибочна
    user_form: str = ''                    # форма, которую написал ученик
    correct_form: str = ''                 # правильная форма
    explanation: str = ''                  # объяснение из БД
    extra: dict = field(default_factory=dict)  # доп. данные (значения паронимов и т.п.)


# ============================================================================
# РЕЕСТР ТЕМ: готовы ли источники отвечать
# ============================================================================

_registry_cache = None


def _ready_topics() -> set:
    """Множество кодов тем, у которых is_ready=True (кэшируем на 60 с)."""
    global _registry_cache
    if _registry_cache is None:
        try:
            codes = set(
                RagTopic.objects.filter(is_ready=True).values_list('code', flat=True)
            )
        except Exception:
            codes = set()
        _registry_cache = codes
        cache.set('rag_ready_topics', codes, 60)
    return _registry_cache


def _topic_ready(code: str) -> bool:
    return code in _ready_topics()


def invalidate_registry_cache():
    """Вызывать после смены is_ready в админке."""
    global _registry_cache
    _registry_cache = None
    cache.delete('rag_ready_topics')


# ============================================================================
# УТИЛИТЫ: токенизация и нормализация
# ============================================================================

def _tokenize(message: str) -> List[str]:
    """Все слова (кириллица/латиница/цифры) с сохранением РЕГИСТРА."""
    return re.findall(r"[а-яёА-ЯЁa-zA-Z0-9]+(?:-[а-яёА-ЯЁa-zA-Z0-9]+)*", message or '')


def _content_tokens(message: str) -> List[str]:
    """Значимые слова в нижнем регистре (без служебных), длина >= 3."""
    out = []
    for tok in _tokenize(message):
        low = tok.lower()
        if len(low) >= 3 and low not in _STOPWORDS:
            out.append(low)
    return out


def _strip_stress(word: str) -> str:
    """Убирает ударение (комбинируемый акут U+0301) и приводит к нижнему регистру."""
    return word.replace('\u0301', '').lower()


def _has_inner_capital(word: str) -> bool:
    """Есть ли заглавная буква НЕ в начале (признак помеченного ударения)."""
    return any(ch.isupper() for ch in word[1:])


# ============================================================================
# АДАПТЕР: ЗАДАНИЕ 9.1 — проверяемые гласные корня (орфограмма 1)
# ============================================================================

def _search_task9(message: str, tokens: List[str]) -> Optional[RagResult]:
    qs = OrthogramExample.objects.filter(orthogram_id=1, is_active=True)
    for tok in tokens:
        # 1) Прямое совпадение: ученик спрашивает правильное слово.
        ex = qs.filter(text__iexact=tok).exclude(explanation='').first()
        if ex:
            return RagResult(
                found=True, topic='task9_1_vowels', false_premise=False,
                user_form=tok, correct_form=ex.text,
                explanation=(ex.explanation or '').strip(),
            )
        # 2) Ложная посылка: ученик написал ошибочный вариант.
        bad = qs.filter(incorrect_variant__iexact=tok).exclude(explanation='').first()
        if bad:
            return RagResult(
                found=True, topic='task9_1_vowels', false_premise=True,
                user_form=tok, correct_form=bad.text,
                explanation=(bad.explanation or '').strip(),
            )
    return None


# ============================================================================
# АДАПТЕР: ЗАДАНИЕ 4 — ударения (OrthoepyWord)
# ============================================================================

def _search_task4(message: str, tokens: List[str], raw_tokens: List[str]) -> Optional[RagResult]:
    # Строим карту: lemma -> (correct_word, incorrect_word)
    for raw in raw_tokens:
        low = _strip_stress(raw)
        if len(low) < 3 or low in _STOPWORDS:
            continue
        entries = OrthoepyWord.objects.filter(is_active=True).filter(
            lemma__iexact=low
        )
        if not entries.exists():
            # Пробуем по самому слову (на случай, если lemma не совпала)
            entries = OrthoepyWord.objects.filter(is_active=True).filter(
                word__iexact=low
            )
        if not entries.exists():
            continue

        lemma = entries[0].lemma
        correct = entries.filter(is_correct=True).first()
        incorrect = entries.filter(is_correct=False).first()

        # Ложная посылка: ученик написал форму с ударением, и она = неверной.
        # Сравниваем с учётом регистра (заглавная гласная = ударение).
        if incorrect and raw == incorrect.word:
            return RagResult(
                found=True, topic='task4_stress', false_premise=True,
                user_form=raw, correct_form=correct.word if correct else lemma,
                explanation='',
                extra={'lemma': lemma},
            )
        # Обычный ответ: правильная форма с ударением.
        if correct:
            return RagResult(
                found=True, topic='task4_stress', false_premise=False,
                user_form=raw, correct_form=correct.word,
                explanation='',
                extra={'lemma': lemma},
            )
    return None


# ============================================================================
# АДАПТЕР: ЗАДАНИЕ 5 — паронимы (paponims.json)
# ============================================================================

_PAPONIMS_CACHE_KEY = 'rag_paponims_cards'


def _load_paponims() -> List[List[dict]]:
    """Список карточек: каждая = список колонок {word, meaning}."""
    cached = cache.get(_PAPONIMS_CACHE_KEY)
    if cached is not None:
        return cached
    path = Path(__file__).parent / 'fixtures' / 'paponims.json'
    cards = []
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
        for card in raw:
            if 'cols' in card:
                cols = card['cols']
            else:
                cols = [
                    {'word': card.get('word1', ''), 'meaning': card.get('meaning1', '')},
                    {'word': card.get('word2', ''), 'meaning': card.get('meaning2', '')},
                ]
            cards.append(cols)
    except (OSError, json.JSONDecodeError):
        cards = []
    cache.set(_PAPONIMS_CACHE_KEY, cards, 3600)
    return cards


def _clean_meaning(text: str) -> str:
    """Убирает <br> и лишние пробелы из значения паронима."""
    text = re.sub(r'<br\s*/?>', ', ', text or '', flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text).strip(' ,')
    return text


def _search_task5(message: str, tokens: List[str]) -> Optional[RagResult]:
    msg_low = (message or '').lower()
    for cols in _load_paponims():
        for col in cols:
            word = (col.get('word') or '').strip()
            if not word:
                continue
            # Совпадение: слово паронима встречается в сообщении целиком.
            if re.search(r'(^|[^а-яё])' + re.escape(word.lower()) + r'($|[^а-яё])', msg_low):
                return RagResult(
                    found=True, topic='task5_paronyms', false_premise=False,
                    user_form=word, correct_form='',
                    explanation='',
                    extra={
                        'paronyms': [
                            {'word': c.get('word', ''), 'meaning': _clean_meaning(c.get('meaning', ''))}
                            for c in cols
                        ]
                    },
                )
    return None


# ============================================================================
# АДАПТЕР: ЗАДАНИЕ 7 — морфологические нормы (CorrectionExercise)
# ============================================================================

def _search_task7(message: str, tokens: List[str]) -> Optional[RagResult]:
    msg_low = (message or '').lower()
    for ex in CorrectionExercise.objects.filter(is_active=True):
        # Ключевые слова: из неправильного и правильного вариантов.
        incorrect_tokens = set(t.lower() for t in re.findall(r'[а-яёА-ЯЁ]+', ex.incorrect_text))
        correct_tokens = set(t.lower() for t in re.findall(r'[а-яёА-ЯЁ]+', ex.correct_text))
        # Ищем пересечение значимых слов (длина >= 4).
        hit_incorrect = any(t in incorrect_tokens and len(t) >= 4 for t in tokens)
        hit_correct = any(t in correct_tokens and len(t) >= 4 for t in tokens)
        if hit_incorrect or hit_correct:
            return RagResult(
                found=True, topic='task7_morphological',
                false_premise=bool(hit_incorrect and not hit_correct),
                user_form=ex.incorrect_text, correct_form=ex.correct_text,
                explanation=(ex.explanation or '').strip(),
            )
    return None


# ============================================================================
# АДАПТЕР: ЗАДАНИЕ 6 — лексические нормы (WordOk)
# ============================================================================

def _search_task6(message: str, tokens: List[str]) -> Optional[RagResult]:
    msg_low = (message or '').lower()
    token_set = set(tokens)
    best = None
    best_score = 0
    for w in WordOk.objects.filter(is_active=True).exclude(explanation=''):
        # Значимые слова предложения (длина >= 5).
        text_tokens = set(t for t in re.findall(r'[а-яё]+', w.text.lower()) if len(t) >= 5)
        variant_tokens = set(t.lower() for t in re.split(r'[,;]', w.correct_variants or '') if t.strip())
        overlap = len(token_set & text_tokens)
        # Бонус, если упомянуто слово из correct_variants.
        variant_hit = any(v in msg_low for v in variant_tokens if len(v) >= 4)
        score = overlap + (3 if variant_hit else 0)
        if score > best_score and score >= 2:
            best_score = score
            best = w
    if best:
        return RagResult(
            found=True, topic='task6_lexical', false_premise=False,
            user_form='', correct_form=best.correct_variants,
            explanation=(best.explanation or '').strip(),
            extra={'sentence': best.text},
        )
    return None


# ============================================================================
# АДАПТЕР: ЗАДАНИЕ 3 — анализ текста (base_ru.md через knowledge_manager)
# ============================================================================

# Ключевые слова, указывающие на задание 3 / анализ текста / стилистику.
_TASK3_KEYWORDS = [
    'задание 3', 'задании 3', 'заданием 3', 'анализ текста', 'стили речи',
    'функциональн', 'научный стиль', 'публицистическ', 'официально-деловой',
    'разговорн', 'художественн', 'средства выразительности', 'стилистик',
    'тип речи', 'стиль текста',
]


def _search_task3(message: str) -> Optional[RagResult]:
    if not KB_AVAILABLE:
        return None
    msg_low = (message or '').lower()
    if not any(kw in msg_low for kw in _TASK3_KEYWORDS):
        return None
    try:
        kbs = knowledge_manager.get_knowledge_base('russian')
        if not kbs:
            return None
        # Собираем все секции, ищем наилучшую по пересечению слов.
        query_tokens = set(_content_tokens(message))
        best_content = None
        best_score = 0
        for kb in kbs:
            for topic_id, section in kb.sections.items():
                content = section.get('content', '')
                sec_tokens = set(re.findall(r'[а-яё]{4,}', content.lower()))
                score = len(query_tokens & sec_tokens)
                # Бонус за совпадение темы.
                if any(kw in topic_id.lower() for kw in ['задание_3', 'стил']):
                    score += 2
                if score > best_score:
                    best_score = score
                    best_content = content
        if best_content and best_score >= 2:
            cleaned = _clean_markdown(best_content)
            if len(cleaned) > 700:
                cleaned = cleaned[:700] + '…'
            return RagResult(
                found=True, topic='task3_analysis', false_premise=False,
                user_form='', correct_form='', explanation=cleaned,
            )
    except Exception as e:
        print(f"⚠️ RAG task3 error: {e}")
    return None


def _clean_markdown(text: str) -> str:
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'\|.*?\|', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ============================================================================
# ОХРАННИКИ: вне охвата и задания 1-2
# ============================================================================

def _detect_out_of_scope(message: str) -> bool:
    return bool(_OUT_OF_SCOPE_RE.search(message or ''))


def _detect_task12(message: str) -> bool:
    return bool(_TASK12_RE.search(message or ''))


# ============================================================================
# ГЛАВНАЯ ТОЧКА ВХОДА
# ============================================================================

def search_knowledge(message: str, user=None) -> Optional[RagResult]:
    """
    Ищет ответ по готовым источникам. Возвращает RagResult или None.

    Порядок:
      1. Охранники: задания 1-2 (нужен текст), темы вне охвата.
      2. Точные совпадения по словам (9.1, 4, 7, 5, 6) — с проверкой ложной посылки.
      3. Теория задания 3 (base_ru.md).
    """
    message = (message or '').strip()
    if not message:
        return None

    # --- Охранники ---
    if _detect_task12(message):
        return RagResult(guard='task12', guard_message=TASK12_MESSAGE)
    if _detect_out_of_scope(message):
        return RagResult(guard='out_of_scope', guard_message=OUT_OF_SCOPE_MESSAGE)

    raw_tokens = _tokenize(message)
    tokens = _content_tokens(message)

    # --- Подсказки для приоритета ---
    msg_low = message.lower()
    wants_stress = any(k in msg_low for k in ['ударени', 'ударение', 'куда удар', 'на какой слог'])
    wants_spelling = any(k in msg_low for k in ['пишется', 'написани', 'правописан', 'как напис', 'почему'])
    wants_meaning = any(k in msg_low for k in ['значит', 'что такое', 'разница', 'отличие', 'пароним'])

    # --- Адаптеры в порядке приоритета ---
    adapters = []
    if wants_stress:
        adapters.append(('task4_stress', lambda: _search_task4(message, tokens, raw_tokens)))
    if wants_meaning:
        adapters.append(('task5_paronyms', lambda: _search_task5(message, tokens)))
    if wants_spelling:
        adapters.append(('task9_1_vowels', lambda: _search_task9(message, tokens)))

    # Базовый порядок: сначала самые точные (слово-в-слово), затем широкие.
    adapters.extend([
        ('task9_1_vowels', lambda: _search_task9(message, tokens)),
        ('task4_stress', lambda: _search_task4(message, tokens, raw_tokens)),
        ('task7_morphological', lambda: _search_task7(message, tokens)),
        ('task5_paronyms', lambda: _search_task5(message, tokens)),
        ('task6_lexical', lambda: _search_task6(message, tokens)),
    ])

    seen = set()
    for code, fn in adapters:
        if code in seen:
            continue
        seen.add(code)
        if not _topic_ready(code):
            continue
        try:
            result = fn()
        except Exception as e:
            print(f"⚠️ RAG adapter {code} error: {e}")
            result = None
        if result and result.found:
            return result

    # --- Теория задания 3 ---
    if _topic_ready('task3_analysis'):
        t3 = _search_task3(message)
        if t3 and t3.found:
            return t3

    return None


# ============================================================================
# ФОРМАТИРОВАНИЕ ОТВЕТА (золотой стиль, без LLM — детерминированно)
# ============================================================================

def _capitalize_word(word: str) -> str:
    """Одиночное слово — капсом для акцента; фразу оставляем как есть."""
    word = (word or '').strip()
    if not word:
        return word
    if ' ' not in word and len(word) <= 20:
        return word.upper()
    return word


def format_rag_answer(result: RagResult) -> str:
    """Собирает финальный текст ответа в стиле золотых образцов."""
    topic = result.topic

    # --- Задание 5: паронимы ---
    if topic == 'task5_paronyms':
        lines = ["Это паронимы — не путай их:"]
        for p in result.extra.get('paronyms', []):
            lines.append(f"• {p['word']} — {p['meaning']}")
        return "\n".join(lines)

    # --- Задание 3: теория ---
    if topic == 'task3_analysis':
        return f"📖 {result.explanation}"

    # --- Задание 6: лексические нормы ---
    if topic == 'task6_lexical':
        return f"💡 {result.explanation}"

    # --- Задание 7: морфологические нормы ---
    if topic == 'task7_morphological':
        if result.false_premise:
            head = f"Нет, так неверно. Правильно: {result.correct_form}"
        else:
            head = f"Правильно: {result.correct_form}"
        return f"{head}\nТакова сложившаяся литературная норма — запоминаем!\n\n{PLANNING_CLOSING}"

    # --- Задание 4: ударения ---
    if topic == 'task4_stress':
        if result.false_premise:
            head = f"Нет, {result.user_form} — неверно. Правильно: {result.correct_form}"
        else:
            head = f"Правильно: {result.correct_form}"
        note = "Такова строгая литературная норма — запоминаем!"
        return f"{head}\n{note}\n\n{PLANNING_CLOSING}"

    # --- Задание 9.1: проверяемые гласные корня ---
    if topic == 'task9_1_vowels':
        correct_cap = _capitalize_word(result.correct_form)
        expl = result.explanation or ''
        # Если объяснение уже начинается с «проверочное» — оставляем как есть.
        if expl and not expl.lower().startswith('проверочн'):
            expl = f"Проверочное слово: {expl}"
        if result.false_premise:
            head = f"Нет, «{result.user_form}» — ошибка. Правильно пишется {correct_cap}."
        else:
            head = f"Правильно пишется {correct_cap}."
        parts = [head]
        if expl:
            parts.append(expl)
        parts.append(PLANNING_CLOSING)
        return "\n".join(parts)

    # --- Общий fallback ---
    if result.explanation:
        return result.explanation
    return result.correct_form
