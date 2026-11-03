import re

from django import template

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
