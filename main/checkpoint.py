# -*- coding: utf-8 -*-
"""Рубежные тесты: снимок варианта, текстовый дайджест, LLM-выжимка,
блоки разбора для преподавателя.

Слои данных попытки CheckpointAttempt:
  test_data    — «что видел ученик»: тексты заданий и эталоны (снимок);
  answers_data — «что сделал»: сырые ответы с браузера;
  results_data — верно/неверно по каждому ключу;
  digest       — кэшированная LLM-выжимка для преподавателя.
Дайджест склеивает слои по ключам и служит одним источником правды
для преподавателя и для ассистента.
"""


def _short(t, n=90):
    t = ' '.join(str(t).split())
    return t if len(t) <= n else t[:n] + '…'


def digest_text(attempt):
    """Компактный текстовый слепок попытки: факт по каждому заданию."""
    td = attempt.test_data or {}
    ans = attempt.answers_data or {}
    res = attempt.results_data or {}
    when = attempt.created_at.strftime('%d.%m.%Y %H:%M')
    lines = [
        f'Рубеж {attempt.checkpoint_code}, {when}: '
        f'{attempt.correct_count}/{attempt.total_tasks} верно, '
        f'ошибок {attempt.error_count}, '
        f'{"сдан" if attempt.passed else "не сдан"}.'
    ]

    def st(key):
        return 'верно' if (res.get(key) or {}).get('correct') else 'НЕВЕРНО'

    q3 = td.get('1_3') or {}
    for q in q3.get('questions', []):
        num = q.get('num')
        lines.append(
            f'З{num}: {_short(q.get("text"))} | ответ: {_short(ans.get(num, "-"))} | '
            f'эталон: {_short((q3.get("correct") or {}).get(num, "-"))} | {st(num)}')

    s4 = td.get('4') or {}
    if s4:
        lines.append(
            f'З4 (ударения): {_short("; ".join(map(str, s4.get("variants", []))), 140)} | '
            f'ответ: {_short(ans.get("4", "-"))} | '
            f'эталон: {_short(",".join(map(str, s4.get("correct", []))))} | {st("4")}')

    s5 = td.get('5') or {}
    if s5:
        lines.append(
            f'З5 (паронимы): {_short(" / ".join(s5.get("sentences", [])), 180)} | '
            f'ответ: {_short(ans.get("5", "-"))} | эталон: {s5.get("correct", "-")} | {st("5")}')

    s6 = td.get('6') or {}
    if s6:
        lines.append(
            f'З6: {_short(s6.get("text", ""), 150)} | ответ: {_short(ans.get("6", "-"))} | '
            f'эталон: {_short(s6.get("correct", "-"))} | {st("6")}')

    s7 = td.get('7') or {}
    if s7:
        lines.append(
            f'З7: {_short("; ".join(s7.get("phrases", [])), 150)} | '
            f'ответ: {_short(ans.get("7", "-"))} | эталон: {s7.get("correct", "-")} | {st("7")}')

    s8 = td.get('8') or {}
    if s8:
        parts = []
        for letter in 'АБВГД':
            parts.append(
                f'{letter}: ученик {ans.get("8_" + letter, "-")} / '
                f'эталон {(s8.get("matches") or {}).get(letter, "-")} '
                f'({"верно" if (res.get("8_" + letter) or {}).get("correct") else "неверно"})')
        lines.append(f'З8: {"; ".join(parts)} | {st("8")}')

    s9 = td.get('9') or {}
    if s9:
        exp = s9.get('expected', [])
        wrong = [i for i in range(1, len(exp) + 1)
                 if not (res.get(f'9-{i}') or {}).get('correct')]
        lines.append(
            f'З9: букв верно {len(exp) - len(wrong)}/{len(exp)}; '
            f'ошибки в масках: {", ".join(map(str, wrong)) or "-"}')

    return '\n'.join(lines)


def ensure_summary(attempt):
    """LLM-выжимка для преподавателя: один раз на попытку.
    Кэш двойной: LLMCache по тексту дайджеста + поле attempt.digest.
    Сбой LLM не роняет страницу — возвращаем пустую строку."""
    if attempt.digest:
        return attempt.digest
    try:
        from main.llm_utils import cached_llm
        system = (
            'Ты — методист платформы подготовки к ЕГЭ по русскому языку. '
            'По фактическим данным попытки рубежного теста напиши 3–5 строк для '
            'преподавателя: какие правила у ученика плавают и что тренировать в первую '
            'очередь. Опирайся только на переданные данные, не выдумывай.')
        text = cached_llm('checkpoint_digest', digest_text(attempt), system,
                          max_tokens=300)
        if text:
            attempt.digest = text
            attempt.save(update_fields=['digest'])
            return text
    except Exception:
        pass
    return ''


def review_blocks(attempt):
    """Блоки разбора для страницы преподавателя: текст варианта, ответ
    ученика и эталон рядом, с признаком верности."""
    td = attempt.test_data or {}
    ans = attempt.answers_data or {}
    res = attempt.results_data or {}

    def ok(key):
        return bool((res.get(key) or {}).get('correct'))

    blocks = []
    q3 = td.get('1_3') or {}
    for q in q3.get('questions', []):
        num = q.get('num')
        blocks.append({
            'task': num,
            'title': f'Задание {num}',
            'body': q.get('text', ''),
            'options': q.get('options', []),
            'student': ans.get(num, ''),
            'correct': (q3.get('correct') or {}).get(num, ''),
            'ok': ok(num),
        })

    s4 = td.get('4') or {}
    if s4:
        blocks.append({
            'task': '4', 'title': 'Задание 4. Ударения', 'body': '',
            'options': [str(v) for v in s4.get('variants', [])],
            'student': ans.get('4', ''),
            'correct': ', '.join(map(str, s4.get('correct', []))),
            'ok': ok('4'),
        })

    s5 = td.get('5') or {}
    if s5:
        blocks.append({
            'task': '5', 'title': 'Задание 5. Паронимы', 'body': '',
            'options': s5.get('sentences', []),
            'student': ans.get('5', ''),
            'correct': s5.get('correct', ''),
            'ok': ok('5'),
        })

    s6 = td.get('6') or {}
    if s6:
        blocks.append({
            'task': '6', 'title': 'Задание 6. Лексика',
            'body': s6.get('text', ''), 'options': [],
            'student': ans.get('6', ''),
            'correct': s6.get('correct', ''),
            'ok': ok('6'),
        })

    s7 = td.get('7') or {}
    if s7:
        blocks.append({
            'task': '7', 'title': 'Задание 7. Грамматика', 'body': '',
            'options': s7.get('phrases', []),
            'student': ans.get('7', ''),
            'correct': s7.get('correct', ''),
            'ok': ok('7'),
        })

    s8 = td.get('8') or {}
    if s8:
        rows = []
        for letter in 'АБВГД':
            rows.append({
                'label': letter,
                'student': ans.get('8_' + letter, ''),
                'correct': (s8.get('matches') or {}).get(letter, ''),
                'ok': ok('8_' + letter),
            })
        options = [f'{l}) {n}' for l, n in (s8.get('error_types') or {}).items()]
        options += [f"{s.get('position')}) {s.get('text')}"
                    for s in s8.get('sentences', [])]
        blocks.append({
            'task': '8', 'title': 'Задание 8. Грамматические ошибки',
            'body': '', 'options': options, 'student_rows': rows,
            'student': '', 'correct': '', 'ok': ok('8'),
        })

    s9 = td.get('9') or {}
    if s9:
        rows = []
        for i, letter in enumerate(s9.get('expected', []), 1):
            rows.append({
                'label': f'9-{i}',
                'student': ans.get(f'9-{i}', ''),
                'correct': letter,
                'ok': ok(f'9-{i}'),
            })
        blocks.append({
            'task': '9', 'title': 'Задание 9. Корни (смайлики)', 'body': '',
            'options': s9.get('lines', []), 'student_rows': rows,
            'student': '', 'correct': '', 'ok': ok('9'),
        })

    return blocks
