import re

from django import template
from django.utils.html import escape, urlize
from django.utils.safestring import mark_safe

register = template.Library()

# Bullets or numbers people type or paste at the start of a line: "- ", "• ", "1. ", "2) "
LIST_PREFIX = re.compile(r'^(?:[-*•·]|\d{1,2}[.)])\s+')


@register.filter
def sections(text):
    """
    Split one-item-per-line text into sections for display.

    A line ending in ":" starts a new section with that title; every other
    non-empty line is an item. Returns [{'title': str | None, 'items': [str]}].
    """
    result = [{'title': None, 'items': []}]
    for raw in (text or '').splitlines():
        line = LIST_PREFIX.sub('', raw.strip())
        if not line:
            continue
        if line.endswith(':'):
            result.append({'title': line[:-1].strip(), 'items': []})
        else:
            result[-1]['items'].append(line)
    return [s for s in result if s['title'] or s['items']]


# "Per a 24 crestes", "Per 4 persones" (a section title, without the colon)
SERVINGS = re.compile(r'^per\s+(?:a\s+)?(\d+(?:[.,]\d+)?)\s+(.+)$', re.IGNORECASE)


@register.filter
def servings(text):
    """Find the "Per a N <unit>" section title that scaling is based on, if any."""
    for section in sections(text):
        match = SERVINGS.match(section['title'] or '')
        if match:
            return {
                'title': section['title'],
                'amount': float(match.group(1).replace(',', '.')),
                'unit': match.group(2),
            }
    return None


URL = re.compile(r'(https?://\S+)')
UNICODE_FRACTIONS = {'½': .5, '¼': .25, '¾': .75, '⅓': 1 / 3, '⅔': 2 / 3}
# 200, 1,5, 1.5, 1/2, 1½, ½  (not part of a word or a longer number)
NUMBER = re.compile(r'(?<![\w.,/])(\d+(?:[.,]\d+)?(?:/\d+)?[½¼¾⅓⅔]?|[½¼¾⅓⅔])(?![\d/])')
# What follows a number that must not be scaled: times, temperatures, ratios, sizes, repetitions
NEXT_WORD = re.compile(r'\s?([^\W\d_]+|[%°])')
FIXED_UNITS = {
    'min', 'mins', 'minut', 'minuts', 'minuto', 'minutos', 'h', 'hr', 'hora', 'hores', 'horas',
    's', 'seg', 'segon', 'segons', 'sec', 'graus', 'grau', 'grados', 'º', 'ºc', '°', 'c',
    'x', '%', 'cm', 'mm', 'w', 'vegada', 'vegades', 'cop', 'cops',
    'dia', 'dies', 'nit', 'nits', 'setmana', 'setmanes',
}


def _number_value(token):
    """Numeric value of a quantity token, or None if it should not be scaled (e.g. "50/50")."""
    if token in UNICODE_FRACTIONS:
        return UNICODE_FRACTIONS[token]
    extra = 0
    if token[-1] in UNICODE_FRACTIONS:
        extra = UNICODE_FRACTIONS[token[-1]]
        token = token[:-1]
    if '/' in token:
        numerator, denominator = (int(part) for part in token.split('/'))
        # Real fractions only; "50/50" is a ratio
        if denominator not in (2, 3, 4, 8) or numerator >= denominator * 4:
            return None
        return numerator / denominator
    return float(token.replace(',', '.')) + extra


def _mark_quantities(text):
    parts = []
    position = 0
    for match in NUMBER.finditer(text):
        next_word = NEXT_WORD.match(text, match.end())
        if next_word and next_word.group(1).lower() in FIXED_UNITS:
            continue
        value = _number_value(match.group(1))
        if value is None:
            continue
        parts.append(escape(text[position:match.start()]))
        parts.append(f'<span class="qty" data-q="{value:g}">{escape(match.group(1))}</span>')
        position = match.end()
    parts.append(escape(text[position:]))
    return ''.join(parts)


@register.filter
def quantities(line):
    """Escape a line, link its URLs and wrap scalable quantities in <span class="qty" data-q="...">."""
    html = []
    for i, piece in enumerate(URL.split(line or '')):
        html.append(urlize(piece) if i % 2 else _mark_quantities(piece))
    return mark_safe(''.join(html))
