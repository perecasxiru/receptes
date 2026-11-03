from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("receptes_app", "0002_fill_missing_slugs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="menu",
            name="slug",
            field=models.SlugField(blank=True, max_length=110, unique=True),
        ),
        migrations.AlterField(
            model_name="recipe",
            name="slug",
            field=models.SlugField(blank=True, max_length=110, unique=True),
        ),
    ]
