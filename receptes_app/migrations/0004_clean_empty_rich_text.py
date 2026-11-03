from django.db import migrations
from django.utils.html import strip_tags


def is_blank(html):
    return not html or (
        '<img' not in html
        and not strip_tags(html).replace('&nbsp;', '').replace('\xa0', '').strip()
    )


def clean_empty_rich_text(apps, schema_editor):
    """Replace editor leftovers like '<p>&nbsp;</p>' with ''."""
    fields = {'Recipe': ['ingredients', 'preparation'], 'Menu': ['description'], 'Make': ['notes']}
    for model_name, field_names in fields.items():
        model = apps.get_model('receptes_app', model_name)
        for obj in model.objects.all():
            changed = [f for f in field_names if getattr(obj, f) and is_blank(getattr(obj, f))]
            for f in changed:
                setattr(obj, f, '')
            if changed:
                obj.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("receptes_app", "0003_unique_slugs"),
    ]

    operations = [
        migrations.RunPython(clean_empty_rich_text, migrations.RunPython.noop),
    ]
