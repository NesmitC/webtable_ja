# main/bot_core.py
"""
Ядро ботовой логики Нейростат. Транспортонезависимое (VK / MAX / любой другой).

НЕ знает про формат клавиатур конкретного мессенджера — возвращает обычные dict,
а адаптеры (vk_bot.py, max_bot.py) уже преобразуют их в свои кнопки.

Логика портирована один в один из рабочих вьюх views.py:
  - _get_personalized_preposition_quiz  ->  quiz_personalized()
  - get_general_orthography_api         ->  quiz_orthography()
  - get_orthoepy_pair                   ->  quiz_orthoepy()
  - get_hot_word_quiz                   ->  quiz_hot_word()
  - log_quiz_answer_site                ->  log_answer()
  - get_user_quiz_stats_site            ->  get_stats()
"""

import re
import random
import logging
import json
import time as _time
from collections import defaultdict, deque
from datetime import timedelta
from django.db.models import Count
from django.utils import timezone
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

from .models import (
    AI_LIMITS,
    UserProfile,
    UserWord,
    OrthogramExample,
    OrthoepyWord,
    QuizHistory,
    DailyWord,
)
from .assistants.knowledge_bases.russian.hot_words import HOT_WORDS_LIST


logger = logging.getLogger(__name__)

# Кэш готовых горячих слов (как _READY_HOT_WORDS во views)
_READY_HOT_WORDS = None


# ========================================================================
# ТАРИФНЫЙ ШЛЮЗ
# ========================================================================

def user_can_use_bot(profile) -> bool:
    """Доступ к боту: триал и все тарифы, кроме «0». level>=1 это покрывает."""
    return profile.level >= 1


def get_profile_by_platform(platform: str, platform_id):
    """Ищет профиль по id мессенджера. platform: 'vk' | 'max'."""
    if not platform_id:
        return None
    if platform == 'vk':
        return UserProfile.objects.filter(vk_id=platform_id).select_related('user').first()
    if platform == 'max':
        return UserProfile.objects.filter(max_id=platform_id).select_related('user').first()
    return None


def iter_bot_eligible_profiles():
    """Все профили, которым можно слать «Слово дня» (есть доступ и привязан VK или MAX)."""
    qs = UserProfile.objects.select_related('user')
    for profile in qs:
        if not user_can_use_bot(profile):
            continue
        if profile.vk_id or profile.max_id:
            yield profile


# ========================================================================
# ХЕЛПЕРЫ
# ========================================================================

def _extract_diff_letters(correct: str, incorrect: str):
    """Возвращает первые отличающиеся буквы из двух вариантов (порт из views)."""
    if not correct or not incorrect:
        return '?', '?'
    for c_char, i_char in zip(correct, incorrect):
        if c_char != i_char:
            return c_char, i_char
    return (correct[-1] if correct else '?'), (incorrect[-1] if incorrect else '?')


def _masked(word) -> str:
    """Маскирует слово: *1* -> 😊 (как на сайте)."""
    return re.sub(r'\*\d+\*', '😊', word.masked_word or word.text)


def _empty(message: str) -> dict:
    """Единый формат «нет вопросов»."""
    return {'available': False, 'message': message}


def _build_quiz(word, source: str, user_word_id=None, extra=None) -> dict:
    """Собирает единый dict квиза из эталонного слова OrthogramExample."""
    l_corr, l_incorr = _extract_diff_letters(word.text, word.incorrect_variant)
    options = [
        {'text': word.text, 'is_correct': True},
        {'text': word.incorrect_variant.strip(), 'is_correct': False},
    ]
    random.shuffle(options)
    explanation = word.explanation or (
        word.orthogram.rule if getattr(word, 'orthogram', None) else 'Правило не указано'
    )
    result = {
        'available': True,
        'question': f'Как пишется правильно:\n{_masked(word)}',
        'options': options,
        'correct_text': word.text,
        'explanation': explanation,
        'example_id': word.id,
        'user_word_id': user_word_id,
        'letter_correct': l_corr,
        'letter_incorrect': l_incorr,
        'source': source,
    }
    if extra:
        result.update(extra)
    return result


# ========================================================================
# КВИЗЫ
# ========================================================================
def _planning_fresh_candidates(profile):
    """Свежие (не показанные сегодня) слова планинга с валидным эталоном."""
    user_id = profile.user_id
    today = timezone.now().date()
    shown_today = set(
        QuizHistory.objects.filter(user_id=user_id, answer_time__date=today)
        .values_list('word_id', flat=True)
    )
    cands = []
    for pw in UserWord.objects.filter(user_id=user_id, is_active=True).select_related('reference_word'):
        ref = pw.reference_word
        if ref and ref.is_active and ref.explanation and ref.incorrect_variant and ref.id not in shown_today:
            cands.append({'word': ref, 'user_word_id': pw.id, 'source': 'planning'})
    return cands


def quiz_personalized(profile) -> dict:
    """Только планинг (для режима «Мои слова» в ботах)."""
    has_any = UserWord.objects.filter(user_id=profile.user_id, is_active=True).exists()
    if not has_any:
        return {'available': False,
                'message': '📖 Слов в планинге пока нет.\nДобавьте слова в планинг, чтобы тренировать их здесь.'}
    cands = _planning_fresh_candidates(profile)
    if not cands:
        return {'available': False,
                'message': '✅ Слова в планинге закончились.\nВозвращайтесь завтра или добавьте новые слова.'}
    selected = random.choice(cands)
    return _build_quiz(selected['word'], selected['source'], user_word_id=selected['user_word_id'])


# ========================================================================
# СЛОВО ДНЯ ДЛЯ САЙТА (МИКС)
# ========================================================================

def get_mix_quiz(profile) -> dict:
    """
    Слово дня для сайта.
    - Планинг есть и есть свежие слова: 80% планинг, 10% горячие, 10% орфография.
    - Планинг пуст или свежие закончились: случайный раздел БД.
    """
    has_any = UserWord.objects.filter(user_id=profile.user_id, is_active=True).exists()
    if has_any:
        fresh = _planning_fresh_candidates(profile)
        if fresh:
            roll = random.random()
            if roll < 0.10:                       # 10% горячие
                q = _random_hot_quiz(profile)
                if q.get('available'):
                    return q
            elif roll < 0.20:                     # 10% орфография
                q = quiz_orthography(profile)
                if q.get('available'):
                    return q
            selected = random.choice(fresh)       # 80% планинг
            return _build_quiz(selected['word'], selected['source'],
                               user_word_id=selected['user_word_id'])
    # планинг пуст или закончился -> случайный раздел БД
    return _random_db_section(profile)


def _random_hot_quiz(profile) -> dict:
    """Случайное горячее слово (без строгого порядка)."""
    ready = _init_ready_hot_words()
    if not ready:
        return _empty('Нет готовых горячих слов')
    return _build_quiz(random.choice(ready), 'hot')


def _random_db_section(profile) -> dict:
    """Случайный раздел БД: орфография / ударения / горячие."""
    order = ['orthography', 'orthoepy', 'hot']
    random.shuffle(order)
    for choice in order:
        if choice == 'orthography':
            q = quiz_orthography(profile)
        elif choice == 'orthoepy':
            q = quiz_orthoepy(profile)
        else:
            q = _random_hot_quiz(profile)
        if q.get('available'):
            return q
    return _empty('Вопросы пока закончились. Попробуйте позже.')


def quiz_orthography(profile) -> dict:
    """Общая орфография из эталонной базы (всё, кроме грамматики 661)."""
    qs = OrthogramExample.objects.filter(
        is_active=True, is_user_added=False,
        explanation__isnull=False, incorrect_variant__isnull=False,
    ).exclude(explanation='', incorrect_variant='') \
     .exclude(orthogram_id=661) \
     .select_related('orthogram')

    if not qs.exists():
        return _empty('Нет вопросов по орфографии')

    word = qs.order_by('?').first()
    return _build_quiz(word, 'general')


def quiz_grammar(profile) -> dict:
    """Грамматика: орфограмма 661."""
    qs = OrthogramExample.objects.filter(
        is_active=True, is_user_added=False,
        explanation__isnull=False, incorrect_variant__isnull=False,
        orthogram_id=661,
    ).exclude(explanation='', incorrect_variant='').select_related('orthogram')

    if not qs.exists():
        return _empty('Нет вопросов по грамматике')

    word = qs.order_by('?').first()
    return _build_quiz(word, 'grammar')


def quiz_orthoepy(profile) -> dict:
    """Ударения: пара вариантов одной леммы (порт get_orthoepy_pair)."""
    lemmas_with_both = OrthoepyWord.objects.filter(
        is_active=True
    ).values('lemma').annotate(
        variant_count=Count('id')
    ).filter(variant_count__gte=2)

    if not lemmas_with_both:
        return _empty('Нет слов для ударений')

    selected_lemma = random.choice(list(lemmas_with_both))['lemma']
    variants = list(OrthoepyWord.objects.filter(lemma=selected_lemma, is_active=True))

    correct_variant = None
    incorrect_variant = None
    for v in variants:
        if v.is_correct:
            correct_variant = v
        else:
            incorrect_variant = v

    if not correct_variant or not incorrect_variant:
        return _empty('Нет пары для слова')

    options = [
        {'text': correct_variant.word, 'is_correct': True},
        {'text': incorrect_variant.word, 'is_correct': False},
    ]
    random.shuffle(options)

    return {
        'available': True,
        'question': f'Как правильно поставить ударение в слове «{selected_lemma}»?',
        'options': options,
        'correct_text': correct_variant.word,
        'explanation': '',
        'example_id': None,           # у орфоэпии нет OrthogramExample
        'orthoepy_lemma': selected_lemma,
        'user_word_id': None,
        'source': 'orthoepy',
    }


def _init_ready_hot_words():
    """Инициализирует список готовых горячих слов в порядке файла (порт из views)."""
    global _READY_HOT_WORDS
    if _READY_HOT_WORDS is not None:
        return _READY_HOT_WORDS

    _READY_HOT_WORDS = []
    for word_text in HOT_WORDS_LIST:
        word = OrthogramExample.objects.filter(
            text__iexact=word_text,
            is_active=True,
            explanation__isnull=False,
            incorrect_variant__isnull=False,
        ).exclude(explanation='', incorrect_variant='').first()
        if word:
            _READY_HOT_WORDS.append(word)

    return _READY_HOT_WORDS


def quiz_hot_word(profile, index: int = 0) -> dict:
    """Горячие слова ЕГЭ: строгий порядок по списку (порт get_hot_word_quiz)."""
    ready = _init_ready_hot_words()
    if not ready:
        return _empty('Нет готовых горячих слов')

    word = ready[index % len(ready)]
    quiz = _build_quiz(word, 'hot')
    quiz['next_index'] = (index + 1) % len(ready)
    quiz['total_available'] = len(ready)
    return quiz


def get_quiz(profile, mode: str, index: int = 0) -> dict:
    """Единая точка входа. mode: personalized|orthography|grammar|orthoepy|hot_word."""
    dispatch = {
        'personalized': lambda: quiz_personalized(profile),
        'planning': lambda: quiz_personalized(profile),   # планинг идёт через personalized
        'orthography': lambda: quiz_orthography(profile),
        'all_orthography': lambda: quiz_orthography(profile),
        'grammar': lambda: quiz_grammar(profile),
        'orthoepy': lambda: quiz_orthoepy(profile),
        'hot_word': lambda: quiz_hot_word(profile, index),
        'hot': lambda: quiz_hot_word(profile, index),
        'weak': lambda: quiz_weak(profile),
    }
    func = dispatch.get(mode)
    if not func:
        return _empty('Неизвестный режим')
    try:
        return func()
    except Exception as e:
        logger.exception(f"bot_core.get_quiz error mode={mode}: {e}")
        return _empty('Внутренняя ошибка')


# ========================================================================
# СЛОВО ДНЯ (рассылка 12:00)
# ========================================================================

def get_daily_word(profile) -> dict:
    """
    Слово дня для рассылки. Приоритет по ТЗ:
    планинг ученика -> горячие слова -> эталонная база.
    """
    try:
        # 1) Планинг (без исключения показанных сегодня — рассылка раз в день)
        pw = UserWord.objects.filter(
            user=profile.user, is_active=True, reference_word__isnull=False,
        ).select_related('reference_word').order_by('?').first()

        if pw and pw.reference_word and pw.reference_word.is_active \
                and pw.reference_word.explanation and pw.reference_word.incorrect_variant:
            return _build_quiz(pw.reference_word, 'planning', user_word_id=pw.id)

        # 2) Горячие слова
        ready = _init_ready_hot_words()
        if ready:
            return _build_quiz(random.choice(ready), 'hot')

        # 3) Эталонная база
        general = OrthogramExample.objects.filter(
            is_active=True, is_user_added=False,
            explanation__isnull=False, incorrect_variant__isnull=False,
        ).exclude(explanation='', incorrect_variant='').order_by('?').first()

        if general:
            return _build_quiz(general, 'general')

        return _empty('Слов для тренировки пока нет')

    except Exception as e:
        logger.exception(f"bot_core.get_daily_word error user={profile.user_id}: {e}")
        return _empty('Внутренняя ошибка')

def remember_max_chat(max_id, chat_id):
    """Запоминаем chat_id для исходящих сообщений MAX (рассылки)."""
    if max_id and chat_id:
        UserProfile.objects.filter(max_id=max_id).update(max_chat_id=chat_id)

# ========================================================================
# ЛОГИРОВАНИЕ ОТВЕТА
# ========================================================================

def log_answer(profile, word_id, user_word_id, was_correct: bool) -> dict:
    """
    Логирует ответ (порт log_quiz_answer_site).
    Счётчики слова планинга обновляются ОДИН раз.

    word_id=None (орфоэпия) — историю не пишем: у орфоэпии нет OrthogramExample,
    а писать чужой id — значит загрязнять статистику (это был баг старого VK-бота).
    """
    if word_id is None:
        return {
            'status': 'ok',
            'was_correct': was_correct,
            'explanation': '',
            'correct_text': '',
        }

    try:
        # Получаем explanation и правильный текст
        word = OrthogramExample.objects.filter(id=word_id, is_active=True).first()
        explanation = word.explanation if word else "Правило не найдено"
        correct_text = word.text if word else "?"

        # Сохраняем в историю
        QuizHistory.objects.create(
            user=profile.user,
            word_id=word_id,
            user_word_id=user_word_id,
            was_correct=was_correct,
            answer_time=timezone.now(),
        )

        # Обновляем статистику слова из планинга (один раз, с проверкой владельца)
        if user_word_id:
            try:
                uw = UserWord.objects.get(id=user_word_id, user=profile.user)
                if was_correct:
                    uw.success_count += 1
                else:
                    uw.error_count += 1
                    uw.last_error = timezone.now()
                uw.last_shown = timezone.now()
                uw.save(update_fields=['success_count', 'error_count', 'last_error', 'last_shown'])
            except UserWord.DoesNotExist:
                pass  # слово не из планинга этого пользователя

        return {
            'status': 'ok',
            'was_correct': was_correct,
            'explanation': explanation,
            'correct_text': correct_text,
        }

    except Exception as e:
        logger.exception(f"bot_core.log_answer error user={profile.user_id}: {e}")
        return {'status': 'error', 'was_correct': was_correct, 'explanation': '', 'correct_text': ''}


# ========================================================================
# СТАТИСТИКА
# ========================================================================

def get_stats(profile) -> dict:
    """Статистика за неделю (порт get_user_quiz_stats_site / weekly_report)."""
    week_ago = timezone.now() - timedelta(days=7)
    user_id = profile.user_id

    total_planning = UserWord.objects.filter(user_id=user_id, is_active=True).count()

    weekly_history = QuizHistory.objects.filter(
        user_id=user_id, answer_time__date__gte=week_ago
    )
    total_attempts = weekly_history.count()
    correct_attempts = weekly_history.filter(was_correct=True).count()
    success_rate = round(correct_attempts / total_attempts * 100) if total_attempts else 0

    # Слабые темы: группировка ошибок по орфограммам
    weak = {}
    for answer in weekly_history.filter(was_correct=False).select_related('word__orthogram'):
        if answer.word and answer.word.orthogram:
            orth = answer.word.orthogram
            if orth.id not in weak:
                weak[orth.id] = {'id': orth.id, 'name': orth.name, 'errors': 0}
            weak[orth.id]['errors'] += 1

    weak_orthograms = sorted(weak.values(), key=lambda x: x['errors'], reverse=True)[:5]

    return {
        'total_words': total_planning,
        'total_attempts': total_attempts,
        'correct_answers': correct_attempts,
        'success_rate': success_rate,
        'weak_orthograms': weak_orthograms,
    }


def format_stats_message(stats: dict) -> str:
    """Готовый текст статистики — одинаковый для VK и MAX."""
    lines = [
        "📊 Ваша статистика за неделю",
        f"📚 Слов в планинге: {stats['total_words']}",
        f"🎯 Попыток: {stats['total_attempts']}",
        f"✅ Правильно: {stats['correct_answers']}",
        f"📈 Успешность: {stats['success_rate']}%",
    ]
    if stats['weak_orthograms']:
        lines.append("")
        lines.append("⚠️ Сложные темы:")
        for o in stats['weak_orthograms']:
            lines.append(f"• {o['name']} — {o['errors']} ош.")
    else:
        lines.append("")
        lines.append("✅ Нет частых ошибок! Так держать!")
    return "\n".join(lines)


def format_daily_message(quiz: dict, name: str = '') -> str:
    """Текст для рассылки «Слово дня» (кнопки вариантов добавляет адаптер)."""
    greeting = f"⚡ Слово дня"
    if name:
        greeting += f", {name}"
    return f"{greeting}!\n\n{quiz['question']}"

# ========================================================================
# ПРИВЯЗКА АККАУНТА ПО КОДУ
# ========================================================================

def link_by_code(code: str, platform: str, platform_id) -> dict:
    """
    Привязывает профиль к аккаунту мессенджера по одноразовому коду.
    platform: 'vk' | 'max'. Код генерируется на сайте в ЛК.
    """
    code = (code or '').strip().upper()
    if not code or not platform_id:
        return {'success': False, 'message': '❌ Пустой код'}

    profile = UserProfile.objects.filter(
        link_code__iexact=code,
        link_code_expires__gt=timezone.now(),
    ).select_related('user').first()

    if not profile:
        return {'success': False, 'message': '❌ Код не подошёл или устарел'}

    # Отвязываем этот id мессенджера от других профилей (поля unique)
    if platform == 'vk':
        UserProfile.objects.filter(vk_id=platform_id).exclude(id=profile.id).update(vk_id=None)
        profile.vk_id = platform_id
    elif platform == 'max':
        UserProfile.objects.filter(max_id=platform_id).exclude(id=profile.id).update(max_id=None)
        profile.max_id = platform_id
    else:
        return {'success': False, 'message': '❌ Неизвестная платформа'}

    # Код одноразовый — гасим
    profile.link_code = None
    profile.link_code_expires = None
    profile.save()

    name = (profile.first_name or profile.user.first_name or profile.user.username)
    logger.info(f'Linked {platform} id={platform_id} -> user {profile.user_id}')
    return {'success': True, 'username': name, 'profile': profile}

MSK = ZoneInfo('Europe/Moscow')
REVEAL_HOUR = 12


# ========================================================================
# ПРОАКТИВНЫЕ РЕКОМЕНДАЦИИ («бот сам замечает и предлагает»)
# ========================================================================

def quiz_weak(profile) -> dict:
    """Прицельная тренировка по слабым орфограммам недели (≥3 ошибок)."""
    stats = get_stats(profile)
    ids = [w['id'] for w in stats['weak_orthograms'] if w['errors'] >= 3]
    if ids:
        qs = OrthogramExample.objects.filter(
            is_active=True, is_user_added=False,
            explanation__isnull=False, incorrect_variant__isnull=False,
            orthogram_id__in=ids,
        ).exclude(explanation='', incorrect_variant='').select_related('orthogram')
        word = qs.order_by('?').first()
        if word:
            return _build_quiz(word, 'weak')
    return quiz_orthography(profile)


def recommend_next(profile):
    """
    Одна самая актуальная рекомендация на сегодня (без LLM — чистая статистика).
    Возвращает dict {'text', 'mode', 'button', 'url'} или None (не дёргаем).
    """
    stats = get_stats(profile)

    # 1) Слабая орфограмма недели
    weak = next((w for w in stats['weak_orthograms'] if w['errors'] >= 3), None)
    if weak:
        return {
            'mode': 'weak',
            'button': '🎯 Потренировать слабое место',
            'url': '/ege/quizzes/',
            'text': (f"📉 Вижу, тема «{weak['name']}» пока буксует — "
                     f"{weak['errors']} ошибки за неделю. Потренируемся 5 минут?"),
        }

    # 2) Слова планинга, до которых не дошли руки (≥3 дней)
    three_days_ago = timezone.now() - timedelta(days=3)
    untouched = (
        UserWord.objects.filter(user_id=profile.user_id, is_active=True)
        .exclude(quizhistory__answer_time__gte=three_days_ago)
        .count()
    )
    if untouched:
        return {
            'mode': 'personalized',
            'button': '📖 Разобрать мои слова',
            'url': '/ege/quizzes/',
            'text': (f'📖 В планинге {untouched} слов(а), которые давно не тренировали. '
                     'Разберём их за пару минут?'),
        }

    # 3) Давно не занимался (≥2 дней) — мягкая разминка
    last = (QuizHistory.objects.filter(user_id=profile.user_id)
            .order_by('-answer_time').first())
    if last and (timezone.now() - last.answer_time) >= timedelta(days=2):
        return {
            'mode': 'hot_word',
            'button': '🔥 Разминка на 3 минуты',
            'url': '/ege/quizzes/',
            'text': '🕊️ Давно не тренировались. Короткая разминка, чтобы не терять темп?',
        }

    return None


def proactive_sent_today(user) -> bool:
    """Рекомендация уже показана сегодня (на любом канале)."""
    from .models import BotLog
    return BotLog.objects.filter(
        user=user, category='proactive',
        created_at__date=timezone.now().date(),
    ).exists()


def log_proactive(user, platform, text):
    """Помечаем рекомендацию показанной (кросс-канальный анти-спам)."""
    from .models import BotLog
    BotLog.objects.create(user=user, username=user.username, platform=platform,
                          question='[proactive]', answer=text, category='proactive')

# ========================================================================
# СВОБОДНЫЙ ТЕКСТ ИЗ БОТОВ → ОРКЕСТРАТОР (общий «мозг»)
# ========================================================================

FREE_CHAT_FOR_UNLINKED = True   # False — непривязанные сразу получают LINK_PROMPT
UNLINKED_CHAT_PER_HOUR = 10     # анти-абьюз для гостей: сообщений в час

_unlinked_times = defaultdict(deque)


def sales_goal_answer(profile, goal):
    """Ответ на кнопку цели в продающем диалоге (боты)."""
    from .assistants.marketing import sales_recommendation
    return sales_recommendation(goal, profile.user if profile else None)

def _ai_limit_message(profile):
    """Текст при исчерпанной месячной квоте ИИ: free — апсейл, платный — дата обновления."""
    if profile.level == 0:
        return ('⚡ Бесплатный лимит сообщений ИИ на этот месяц исчерпан. '
                'Квизы, слово дня и статистика работают без ограничений. '
                'Больше ИИ — в тарифах: https://neurostat.ru/profile/')
    return ('⚡ Лимит сообщений ИИ вашего тарифа на этот месяц исчерпан. '
            'Он обновится 1-го числа. Квизы и тренажёры доступны без ограничений.')

def free_chat(platform, platform_id, text, simplify=False):
    """
    Пропускает свободный текст из бота через оркестратор.
    Возвращает dict: {'allowed': bool, 'linked': bool, 'reply': str}
    """
    profile = get_profile_by_platform(platform, platform_id)
    if profile is None and not FREE_CHAT_FOR_UNLINKED:
        return {'allowed': False, 'linked': False, 'reply': ''}

    if profile is None:
        q = _unlinked_times[platform_id]
        now = _time.time()
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= UNLINKED_CHAT_PER_HOUR:
            return {'allowed': True, 'linked': False,
                    'reply': ('⏳ Лимит вопросов для гостей исчерпан на час. '
                              'Привяжи аккаунт — и ограничения снимутся.')}
        q.append(now)

    # Месячная квота ИИ — общая с сайтом (единый счётчик в профиле)
    if profile is not None and not profile.can_use_ai():
        return {'allowed': True, 'linked': True, 'reply': _ai_limit_message(profile)}

    from main.assistant import get_orchestrator
    user = profile.user if profile else None
    res = get_orchestrator().get_response(user, text, platform=platform,
                                          simplify=simplify)
    reply = res['reply']

    if profile is not None:
        profile.try_consume_ai()
        limit = AI_LIMITS[profile.level]
        if limit is not None and profile.level == 0:
            left = limit - profile.ai_used
            if 0 < left <= 2:
                reply += (f'\n\n⚡ Осталось сообщений ИИ в этом месяце: {left}. '
                          'Больше — в тарифах на сайте.')

    return {'allowed': True, 'linked': bool(profile), 'reply': reply,
            'buttons': res.get('buttons'),
            'simplifiable': bool(res.get('simplifiable'))}

def now_msk():
    return timezone.now().astimezone(MSK)


def get_daily_word_state(profile):
    """
    Состояние «Слова дня».
    Период: открывается в 12:00 МСК и активен до следующих 12:00.
    Возвращает dict: state ('revealed'|'waiting'), now_msk, next_reveal,
    и при revealed — question/options/...
    """
    n = now_msk()
    today = n.date()
    reveal_today = datetime.combine(today, dtime(hour=REVEAL_HOUR), tzinfo=MSK)
    period_date = today if n >= reveal_today else today - timedelta(days=1)
    next_reveal = datetime.combine(period_date + timedelta(days=1), dtime(hour=REVEAL_HOUR), tzinfo=MSK)

    base = {
        'now_msk': n.strftime('%H:%M:%S'),
        'now_msk_epoch': int(n.timestamp()),
        'next_reveal': next_reveal.strftime('%d.%m %H:%M'),
        'next_reveal_epoch': int(next_reveal.timestamp()),
    }

    daily = DailyWord.objects.filter(user=profile.user, period_date=period_date).first()

    # генерируем слово только для сегодняшнего периода (если его ещё нет)
    if daily is None and period_date == today:
        quiz = get_mix_quiz(profile)
        if quiz.get('available'):
            daily = DailyWord.objects.create(
                user=profile.user, period_date=period_date,
                source=quiz.get('source', ''),
                example_id=quiz.get('example_id'),
                user_word_id=quiz.get('user_word_id'),
                question=quiz.get('question', ''),
                options_json=json.dumps(quiz.get('options', []), ensure_ascii=False),
                correct_text=quiz.get('correct_text', ''),
                explanation=quiz.get('explanation', ''),
            )
        else:
            return {**base, 'state': 'waiting', 'message': quiz.get('message', 'Слово дня скоро появится.')}

    if daily is None or daily.answered:
        return {**base, 'state': 'waiting'}

    return {
        **base,
        'state': 'revealed',
        'period_date': period_date.isoformat(),
        'question': daily.question,
        'options': json.loads(daily.options_json or '[]'),
        'example_id': daily.example_id,
        'user_word_id': daily.user_word_id,
        'correct_text': daily.correct_text,
        'explanation': daily.explanation,
    }


def answer_daily_word(profile, period_date, selected_index):
    """Отмечает слово дня отвеченным. В QuizHistory (статистику) НЕ пишет."""
    daily = DailyWord.objects.filter(user=profile.user, period_date=period_date).first()
    if not daily:
        return {'status': 'error', 'message': 'Слово не найдено'}
    if daily.answered:
        return {'status': 'already', 'was_correct': daily.answered_correctly,
                'correct_text': daily.correct_text, 'explanation': daily.explanation}

    options = json.loads(daily.options_json or '[]')
    is_correct = False
    if isinstance(selected_index, int) and 0 <= selected_index < len(options):
        is_correct = bool(options[selected_index].get('is_correct'))

    daily.answered = True
    daily.answered_correctly = is_correct
    daily.answered_at = timezone.now()
    daily.save(update_fields=['answered', 'answered_correctly', 'answered_at'])
    return {'status': 'ok', 'was_correct': is_correct,
            'correct_text': daily.correct_text, 'explanation': daily.explanation}
