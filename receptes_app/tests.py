import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Recipe, Tag

MEDIA_ROOT = tempfile.mkdtemp()


def make_image(size=(1600, 1200), fmt='PNG'):
    buffer = BytesIO()
    Image.new('RGBA', size, 'red').save(buffer, fmt)
    return SimpleUploadedFile(f'photo.{fmt.lower()}', buffer.getvalue())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RecipeModelTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_slug_is_unique(self):
        first = Recipe.objects.create(name="Pa amb tomàquet")
        second = Recipe.objects.create(name="Pa amb tomàquet")
        self.assertEqual(first.slug, "pa-amb-tomaquet")
        self.assertEqual(second.slug, "pa-amb-tomaquet-2")

    def test_long_name_fits_slug(self):
        recipe = Recipe.objects.create(name="x" * 100)
        self.assertLessEqual(len(recipe.slug), 110)

    def test_image_resized_once(self):
        recipe = Recipe.objects.create(name="Amb foto", image=make_image())
        name = recipe.image.name
        self.assertTrue(name.endswith('.jpg'))
        with Image.open(recipe.image.path) as img:
            self.assertEqual(img.size, (800, 600))

        # Editing other fields must not re-process or duplicate the image
        recipe = Recipe.objects.get(pk=recipe.pk)
        recipe.name = "Amb foto 2"
        recipe.save()
        self.assertEqual(recipe.image.name, name)


class RecipeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(name="Plat principal")
        cls.recipe = Recipe.objects.create(name="Croquetes d'espinacs", ingredients="<ul><li>300g d'espinacs</li></ul>")
        cls.recipe.tags.add(cls.tag)
        Recipe.objects.create(name="Pastís de carbassa")

    def test_list(self):
        response = self.client.get(reverse('recipe_list'))
        self.assertContains(response, "Croquetes d&#x27;espinacs")
        self.assertContains(response, "?tag=Plat%20principal")
        self.assertNotContains(response, reverse('recipe_create'))

    def test_filter_by_tag(self):
        response = self.client.get(reverse('recipe_list'), {'tag': "Plat principal"})
        self.assertContains(response, "Croquetes")
        self.assertNotContains(response, "Pastís de carbassa")

    def test_search_ingredients(self):
        response = self.client.get(reverse('recipe_list'), {'search': "espinacs"})
        self.assertEqual(list(response.context['page_obj']), [self.recipe])

    def test_detail(self):
        response = self.client.get(reverse('recipe_detail', args=[self.recipe.slug]))
        self.assertContains(response, "300g d'espinacs")

    def test_detail_404(self):
        response = self.client.get(reverse('recipe_detail', args=["no-existeix"]))
        self.assertEqual(response.status_code, 404)

    def test_create_requires_staff(self):
        response = self.client.get(reverse('recipe_create'))
        self.assertEqual(response.status_code, 302)

    def test_create(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@a.a", "pass"))
        self.assertContains(self.client.get(reverse('recipe_list')), reverse('recipe_create'))

        response = self.client.post(reverse('recipe_create'), {'name': "Croquetes d'espinacs", 'tags': [self.tag.pk]})
        self.assertRedirects(response, reverse('recipe_list'))
        created = Recipe.objects.get(slug="croquetes-despinacs-2")
        self.assertEqual(list(created.tags.all()), [self.tag])

    def test_create_shows_errors(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@a.a", "pass"))
        response = self.client.post(reverse('recipe_create'), {'name': "Una altra", 'slug': self.recipe.slug})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invalid-feedback d-block')
