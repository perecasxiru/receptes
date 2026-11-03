from html.parser import HTMLParser

from django.db import migrations

BLOCK_TAGS = {'p', 'li', 'div', 'ul', 'ol', 'blockquote', 'figure', 'figcaption', 'tr', 'pre',
              'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
HEADING_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
BOLD_TAGS = {'strong', 'b'}


class _HtmlToLines(HTMLParser):
    """Turn editor HTML into one line per block (paragraph, list item, heading)."""

    def __init__(self):
        super().__init__()  # convert_charrefs=True: &nbsp; etc. arrive unescaped
        self.lines = []
        self.images = 0
        self._reset_block()
        self._bold = 0
        self._href = None
        self._link_text = ''

    def _reset_block(self):
        self._parts = []
        self._heading = False
        self._chars = 0
        self._bold_chars = 0

    def _flush(self):
        text = ' '.join(''.join(self._parts).split())
        if text:
            # Headings and fully bold lines become "Section:" titles
            if (self._heading or self._bold_chars == self._chars) and not text.endswith(':'):
                text += ':'
            self.lines.append(text)
        self._reset_block()

    def handle_starttag(self, tag, attrs):
        if tag in BLOCK_TAGS or tag == 'br':
            self._flush()
        if tag in HEADING_TAGS:
            self._heading = True
        elif tag in BOLD_TAGS:
            self._bold += 1
        elif tag == 'a':
            self._href = dict(attrs).get('href')
            self._link_text = ''
        elif tag == 'img':
            self.images += 1

    def handle_endtag(self, tag):
        if tag in BOLD_TAGS:
            self._bold = max(0, self._bold - 1)
        elif tag == 'a':
            # Keep the URL so links survive as plain text (they are auto-linked on display)
            if self._href and self._href.startswith('http') and self._href not in self._link_text:
                self._parts.append(f' ({self._href})')
            self._href = None
        if tag in BLOCK_TAGS:
            self._flush()

    def handle_data(self, data):
        self._parts.append(data)
        if self._href is not None:
            self._link_text += data
        visible = len(data.strip())
        self._chars += visible
        if self._bold:
            self._bold_chars += visible


def html_to_text(html):
    """Return (plain_text, number_of_dropped_images)."""
    if not html:
        return '', 0
    if '<' not in html:
        return html.strip(), 0
    parser = _HtmlToLines()
    parser.feed(html)
    parser.close()
    parser._flush()
    return '\n'.join(parser.lines), parser.images


FIELDS = {
    'Recipe': ['ingredients', 'preparation'],
    'Menu': ['description'],
    'Make': ['notes'],
}


def convert(apps, schema_editor):
    for model_name, field_names in FIELDS.items():
        model = apps.get_model('receptes_app', model_name)
        for obj in model.objects.all():
            dropped = 0
            for field in field_names:
                text, images = html_to_text(getattr(obj, field))
                setattr(obj, field, text)
                dropped += images
            obj.save(update_fields=field_names)
            if dropped:
                label = getattr(obj, 'name', None) or f"recipe #{obj.recipe_id}, {obj.date}"
                print(f"\n  {model_name} #{obj.pk} ({label}): {dropped} image(s) inside the text were dropped")


class Migration(migrations.Migration):

    dependencies = [
        ("receptes_app", "0004_clean_empty_rich_text"),
    ]

    operations = [
        migrations.RunPython(convert, migrations.RunPython.noop),
    ]
