# main/assistants/marketing.py
"""
Нейро-маркетолог: продающий диалог подбора тарифа.

Схема диалога (без LLM — мгновенно и бесплатно):
  триггер цены → вопрос о цели (с кнопками в ботах) → рекомендация тарифа.
Отдельно: отработка возражения «дорого».
Свободные маркетинговые вопросы («чем отличаетесь от курсов») — кэш + LLM.

Цены, названия, квоты и триал берутся ТОЛЬКО из main/models.py
(PLAN_PRICES / PLAN_NAMES / AI_LIMITS / TRIAL_DAYS) — единый источник правды.
"""

from main.models import (
    PLAN_PRICES, PLAN_NAMES, PLAN_LEVEL, AI_LIMITS, TRIAL_DAYS,
)
from main.llm_utils import cached_llm, INJECTION_GUARD, user_block

SITE = 'https://neurostat.ru'

# ---------------------------------------------------------------------------
# Маркетинговый контент (описания фич). Цены/имена/квоты — не здесь!
# ---------------------------------------------------------------------------

PLAN_DESCRIPTIONS = {
    'free': 'Витрина: попробуйте систему',
    'self': 'Самостоятельная подготовка с ИИ и растущим курсом',
    'group': 'Поток: платформа + живой преподаватель (популярный тариф)',
    'premium': 'Личная траектория с репетитором',
}

PLAN_FEATURES = {
    'free': [
        '1 диагностика в месяц',
        '1 пробный урок',
        '1 тренажёр и горячие квизы',
    ],
    'self': [
        'Безлимитные диагностики и тренажёры',
        'Растущий курс + визуальные материалы',
        'Квизы и «Слово дня» в ботах VK и MAX',
        'Полная статистика и прогресс',
    ],
    'group': [
        'Всё из тарифа «Я сам»',
        'Групповая встреча каждую неделю',
        'Пробники в формате ЕГЭ еженедельно',
        'Чат с преподавателем 30 минут в день',
        'Отчёты родителям',
    ],
    'premium': [
        'Всё из тарифа «Вместе»',
        '4 личные встречи с репетитором в месяц',
        'Индивидуальная траектория обучения',
    ],
}

PLAN_ORDER = ('free', 'self', 'group', 'premium')


def build_tariffs_text():
    """Собирает справку о тарифах из единого источника правды (models.py)."""
    lines = []
    for code in PLAN_ORDER:
        name = PLAN_NAMES[code]
        price = PLAN_PRICES[code]
        ai_limit = AI_LIMITS[PLAN_LEVEL[code]]
        ai_text = ('ИИ-ассистент: безлимит'
                   if ai_limit is None
                   else f'ИИ-ассистент: {ai_limit} сообщений/мес')
        price_text = '0 ₽/мес' if price == 0 else f'{price} ₽/мес'

        lines.append(f'Тариф «{name}» ({price_text}) — {PLAN_DESCRIPTIONS[code]}')
        for feat in PLAN_FEATURES[code]:
            lines.append(f'  • {feat}')
        lines.append(f'  • {ai_text}')
        lines.append('')
    lines.append(f'Все платные тарифы включают {TRIAL_DAYS} дней полного доступа бесплатно.')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# ПРОДАЮЩИЙ ДИАЛОГ: цель → рекомендация
# ---------------------------------------------------------------------------

GOAL_PATTERNS = {
    'weak': ('подтян', 'слаб', 'пробел', 'закрыть тем'),
    'ege': ('85', 'высокий балл', 'поступ', 'наставник', 'максимум'),
    'try': ('попроб', 'просто', 'бесплат', 'впервые', 'с чего начать'),
}

OBJECTION_KEYS = ('дорог', 'нет денег', 'не по карман', 'дороже, чем')

_YES = ('да', 'давай', 'конечно', 'ок', 'ага', 'хочу', 'расскажи')


def _is_yes(m):
    m = (m or '').strip().lower().strip('!?. ')
    return m in _YES or m.startswith('да,') or m.startswith('да ')

PRICING_TRIGGERS = ('тариф', 'цен', 'стоим', 'сколько стоит', 'купить',
                    'оплат', 'подписк', 'абонемент')


def parse_sales_goal(message):
    """Распознаёт цель ученика в диалоге подбора. None = не ответ на вопрос."""
    m = (message or '').strip().lower()
    if m in ('1', '1️⃣', 'один'):
        return 'weak'
    if m in ('2', '2️⃣', 'два'):
        return 'ege'
    if m in ('3', '3️⃣', 'три'):
        return 'try'
    for goal, keys in GOAL_PATTERNS.items():
        if any(k in m for k in keys):
            return goal
    return None


def is_objection(message):
    m = (message or '').lower()
    return any(k in m for k in OBJECTION_KEYS)


def is_pricing_trigger(message):
    m = (message or '').lower()
    if 'оцен' in m:  # «оценка сочинения» — не про деньги
        return False
    return any(k in m for k in PRICING_TRIGGERS)


def continues_sales_dialog(message):
    """Продолжение диалога после вопроса о цели (цель, возражение или «да»)."""
    return bool(parse_sales_goal(message)) or is_objection(message) or _is_yes(message)


def sales_intro():
    """Шаг 1: вопрос о цели. Кнопки — для ботов, цифры — для сайта."""
    return {
        'reply': ("🎈 Тарифы — от бесплатного до персонального ведения.\n"
                  "Подберу твой за один вопрос. Какая у тебя цель?\n\n"
                  "1️⃣ Подтянуть слабые темы\n"
                  "2️⃣ ЕГЭ на 85+\n"
                  "3️⃣ Просто попробовать"),
        'buttons': [
            [{'label': '1️⃣ Подтянуть темы', 'payload': {'a': 'sales_goal', 'g': 'weak'}}],
            [{'label': '2️⃣ ЕГЭ на 85+', 'payload': {'a': 'sales_goal', 'g': 'ege'}}],
            [{'label': '3️⃣ Просто попробовать', 'payload': {'a': 'sales_goal', 'g': 'try'}}],
        ],
    }


def _already_on_plan(user, code):
    """Не продавать уже купленное."""
    try:
        if user is None or isinstance(user, str):
            return False
        prof = getattr(user, 'profile', None)
        if prof is None:
            return False
        return prof.plan == code and prof.level > 0
    except Exception:
        return False


def sales_recommendation(goal, user=None):
    """Шаг 2: рекомендация тарифа под цель. Цены — из models.py."""
    note = ''

    if goal == 'try':
        text = (f"✅ Начни с тарифа «{PLAN_NAMES['free']}» — бесплатно: квизы, "
                f"«слово дня» и {AI_LIMITS[0]} сообщений ИИ в месяц. "
                f"После регистрации — {TRIAL_DAYS} дней полного доступа, "
                f"карта не нужна. Регистрируйся: {SITE}/")

    elif goal == 'weak':
        code = 'self'
        text = (f"💪 Твой формат — «{PLAN_NAMES[code]}» ({PLAN_PRICES[code]} ₽/мес): "
                "безлимитные тренажёры и диагностики, 150 сообщений ИИ в месяц "
                "и полная статистика, чтобы закрывать слабые темы каждый день. "
                f"Это дешевле одного часа репетитора. Выбрать: {SITE}/profile/")
        if _already_on_plan(user, code):
            note = "\n\nКстати, ты уже на этом тарифе 😉"

    else:  # ege
        g, p = PLAN_PRICES['group'], PLAN_PRICES['premium']
        text = (f"🚀 На 85+ идут с наставником. «{PLAN_NAMES['group']}» ({g} ₽/мес): "
                "еженедельные занятия с преподавателем, пробники в формате ЕГЭ "
                f"и отчёты родителям. «{PLAN_NAMES['premium']}» ({p} ₽/мес): "
                "4 личные встречи и личная траектория. В пересчёте на занятие — "
                f"от 600 ₽ против 2 000 ₽/час у репетитора. Выбрать: {SITE}/profile/")
        if _already_on_plan(user, 'group') or _already_on_plan(user, 'premium'):
            note = "\n\nКстати, ты уже на этом тарифе 😉"

    return text + note


SELF_PREP_REPLY = (
    "Подготовиться реально самому к любому экзамену, но быстрее и качественнее "
    "это сделать со специалистом. Позвони или напиши Александру, обсудите варианты. "
    "Или выбери план обучения. Рассказать про подходящие тарифы?"
)


OBJECTION_REPLY = (
    "Понимаю 🙂 Сравни: час репетитора — около 2 000 ₽. У нас занятие выходит "
    "от 600 ₽, а тренажёры и ИИ работают каждый день. Плюс родителям вернётся "
    "13% налоговым вычетом. А начать можно вообще бесплатно — тариф «0»."
)


# ---------------------------------------------------------------------------
# Специалист
# ---------------------------------------------------------------------------

class Marketing:
    def handle(self, user, message, context, history=None):
        low = (message or '').lower().strip()

        # 0) «Справлюсь ли сам / с бесплатным» — честный продажный ответ
        from main.assistants.router import is_self_prep
        if is_self_prep(low):
            return SELF_PREP_REPLY

        # 0.5) «Да, расскажи» после продажного вопроса — продолжаем воронку
        if _is_yes(low):
            return sales_intro()

        # 1) Продолжение диалога: цель или возражение
        goal = parse_sales_goal(low)
        if goal:
            return sales_recommendation(goal, user)
        if is_objection(low):
            return OBJECTION_REPLY

        # 2) Вход в воронку: вопрос о цене/тарифе
        if is_pricing_trigger(low):
            return sales_intro()

        # 3) Свободный маркетинговый вопрос — кэш + LLM
        try:
            return cached_llm('marketing', message, self._system_prompt(),
                              max_tokens=400)
        except Exception as e:
            print(f"Marketing LLM error: {e}")
            return self._get_fallback_response(message)

    def _current_plan_note(self, user):
        try:
            info = user.profile.subscription_info()
            return (f"Текущий статус пользователя: {info.get('plan_name', 'неизвестно')} "
                    f"(тип: {info.get('kind', 'неизвестно')}). "
                    f"Не предлагай тариф, который уже активен.")
        except Exception:
            return ''

    def _system_prompt(self):
        guard = INJECTION_GUARD
        return f"""Ты — Нейро-маркетолог образовательной платформы "Нейростат".

Твоя задача:
1. Презентовать возможности платформы понятно и убедительно
2. Помогать с выбором тарифа под потребности ученика
3. Отвечать на вопросы об оплате и пробном периоде
4. Быть дружелюбным, но не навязчивым
5. При необходимости — направлять в Личный кабинет ({SITE}/profile/)

ВАЖНО:
- Называй ТОЛЬКО тарифы, цены и условия из блока "ТАРИФЫ ПЛАТФОРМЫ".
  Не выдумывай другие цены, скидки и тарифы.
- Если не знаешь ответа — предложи связаться с администратором
- Используй эмодзи умеренно (🎯 ✅ 💡), без маркдауна

{guard}"""

    def _get_fallback_response(self, message):
        """Ответ без LLM (если API недоступно)."""
        message_lower = message.lower()

        if any(k in message_lower for k in ('тариф', 'цена', 'стоим', 'сколько')):
            return f"""💡 Актуальные тарифы платформы:

{build_tariffs_text()}

Подробности и оплата — в Личном кабинете: {SITE}/profile/"""

        if 'оплат' in message_lower or 'купить' in message_lower:
            return f"""💳 Перейти к оплате можно в Личном кабинете: {SITE}/profile/

Оплата банковской картой через ЮKassa. Есть пробный период после регистрации!"""

        if 'пробн' in message_lower or 'тест' in message_lower:
            return (f"✅ После регистрации открывается {TRIAL_DAYS} дней полного "
                    "доступа бесплатно.\n\nТриал даёт все возможности Премиум-тарифа — "
                    "можно всё попробовать и потом выбрать подходящий тариф.")

        return ("🤔 Не совсем понял вопрос.\n\nМогу рассказать:\n"
                "• О тарифах (напиши \"тарифы\")\n"
                "• Об оплате (напиши \"оплата\")\n"
                "• О пробном периоде (напиши \"пробный\")")
