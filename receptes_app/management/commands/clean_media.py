import os

from django.conf import settings
from django.core.management.base import BaseCommand

from receptes_app.models import Recipe, Make, Menu


class Command(BaseCommand):
    help = "List (or delete with --delete) files in media/uploads/ that no recipe or make uses."

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true', help="Actually delete the unused files")

    def handle(self, *args, **options):
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        if not os.path.isdir(upload_dir):
            self.stdout.write("No uploads directory.")
            return

        used = set(Recipe.objects.exclude(image='').values_list('image', flat=True))
        used |= set(Make.objects.exclude(image='').values_list('image', flat=True))

        # Rich text may embed uploaded images too; keep anything mentioned there
        rich_text = ' '.join(
            text or ''
            for qs in (
                Recipe.objects.values_list('ingredients', 'preparation'),
                Make.objects.values_list('notes'),
                Menu.objects.values_list('description'),
            )
            for row in qs
            for text in row
        )

        unused = [
            name for name in sorted(os.listdir(upload_dir))
            if f'uploads/{name}' not in used and name not in rich_text
        ]

        total = sum(os.path.getsize(os.path.join(upload_dir, name)) for name in unused)
        for name in unused:
            self.stdout.write(f"uploads/{name}")
            if options['delete']:
                os.remove(os.path.join(upload_dir, name))

        verb = "Deleted" if options['delete'] else "Found"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} {len(unused)} unused file(s), {total / 1024 / 1024:.1f} MB."
            + ("" if options['delete'] else " Run with --delete to remove them.")
        ))
