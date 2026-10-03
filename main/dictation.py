# -*- coding: utf-8 -*-
"""main/dictation.py — парсер текста онлайн-диктантов.

Формат пропусков (как в диагностике, но варианты встроены в текст):
  (а,о)      — орфографический слот: выбор из букв/кусков слова;
  [х ,]      — пунктограмма: 'х' = знака нет, пустой вариант = запятая;
  [/ ,| ,-]  — выбор из / | - ;
  (н(е,и))   — внешние скобки без запятой верхнего уровня = группировка,
               внутри разбирается слот (е,и), скобки остаются текстом.

parse_dictation(text) -> (segments, slots)
  segments: [{'type':'text','text':...} | {'type':'slot','index':i,'options':[...]}]
  slots:    [{'index':i,'options':[...]}] — по порядку появления.

split_answers('и|х|,|ъ') -> ['и','х',',','ъ'] — ключи через '|'.
"""


def _find_close(text, start, open_ch, close_ch):
    """Индекс парной скобки для text[start] == open_ch; -1 если не закрыта."""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top_level(content, sep=','):
    """Делит по сепаратору верхнего уровня, не режа вложенные скобки."""
    parts, depth, cur = [], 0, []
    for ch in content:
        if ch in '([':
            depth += 1
            cur.append(ch)
        elif ch in ')]':
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append(''.join(cur))
    return parts


def _dedupe(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def parse_dictation(text):
    segments, slots, plain = [], [], []

    def flush():
        if plain:
            segments.append({'type': 'text', 'text': ''.join(plain)})
            plain.clear()

    def add_slot(options):
        flush()
        idx = len(slots)
        slots.append({'index': idx, 'options': options})
        segments.append({'type': 'slot', 'index': idx, 'options': options})

    i, n = 0, len(text or '')
    while i < n:
        ch = text[i]

        if ch == '[':
            close = _find_close(text, i, '[', ']')
            if close == -1:
                plain.append(ch)
                i += 1
                continue
            content = text[i + 1:close]
            raw = content.split(',') if ',' in content else content.split()
            options = _dedupe([(o.strip() or ',') for o in raw])
            if options:
                add_slot(options)
            else:
                plain.append(text[i:close + 1])
            i = close + 1
            continue

        if ch == '(':
            close = _find_close(text, i, '(', ')')
            if close == -1:
                plain.append(ch)
                i += 1
                continue
            content = text[i + 1:close]
            top = _split_top_level(content)
            options = [o.strip() for o in top]
            if len(top) > 1 and all(o != '' for o in options):
                add_slot(_dedupe(options))
                i = close + 1
                continue
            # группировка: скобки — текст, содержимое разбираем вложенно
            plain.append('(')
            flush()
            sub_segs, _sub_slots = parse_dictation(content)
            for sg in sub_segs:
                if sg['type'] == 'text':
                    segments.append(sg)
                else:
                    add_slot(sg['options'])
            plain.append(')')
            flush()
            i = close + 1
            continue

        plain.append(ch)
        i += 1

    flush()
    return segments, slots


def split_answers(answers):
    """Ключи через '|'. Пустая строка -> []. Токены только strip'ятся."""
    if not answers or not answers.strip():
        return []
    return [t.strip() for t in answers.split('|')]
