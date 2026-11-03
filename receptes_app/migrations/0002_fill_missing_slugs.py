from django.db import migrations
from django.utils.text import slugify


def fill_slugs(apps, schema_editor):
    """Give every Recipe/Menu a unique slug before the unique constraint is added."""
    for model_name in ('Recipe', 'Menu'):
        model = apps.get_model('receptes_app', model_name)
        used = set()
        for obj in model.objects.order_by('pk'):
            base = (obj.slug or slugify(obj.name))[:106] or 'item'
            slug, counter = base, 2
            while slug in used:
                slug = f"{base}-{counter}"
                counter += 1
            used.add(slug)
            if obj.slug != slug:
                obj.slug = slug
                obj.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ("receptes_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
    ]
