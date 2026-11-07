import datetime
import importlib
import os
import shutil
import tempfile
from io import BytesIO, StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import Dish, Make, Menu, Recipe, RestaurantVisit, Tag
from .templatetags.recipe_text import quantities, sections, servings

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

    def test_replaced_and_deleted_images_are_removed(self):
        recipe = Recipe.objects.create(name="Foto", image=make_image())
        old_path = recipe.image.path

        with self.captureOnCommitCallbacks(execute=True):
            recipe.image = make_image()
            recipe.save()
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(recipe.image.path))

        new_path = recipe.image.path
        with self.captureOnCommitCallbacks(execute=True):
            recipe.delete()
        self.assertFalse(os.path.exists(new_path))

    def test_display_image_falls_back_to_latest_make(self):
        recipe = Recipe.objects.create(name="Sense foto")
        self.assertIsNone(recipe.display_image)
        Make.objects.create(recipe=recipe, date=datetime.date(2026, 1, 1), image=make_image())
        latest = Make.objects.create(recipe=recipe, date=datetime.date(2026, 5, 1), image=make_image())
        Make.objects.create(recipe=recipe, date=datetime.date(2026, 9, 1))  # No photo
        self.assertEqual(recipe.display_image.name, latest.image.name)

    def test_text_is_stripped(self):
        recipe = Recipe.objects.create(name="Buida", ingredients="  \n ", preparation="Fregir\n")
        self.assertEqual(recipe.ingredients, "")
        self.assertEqual(recipe.preparation, "Fregir")

    def test_clean_media_keeps_used_files(self):
        recipe = Recipe.objects.create(name="Usada", image=make_image())
        orphan = os.path.join(MEDIA_ROOT, 'uploads', 'orphan.jpg')
        with open(orphan, 'wb') as f:
            f.write(b'x')

        out = StringIO()
        call_command('clean_media', stdout=out)
        self.assertIn('uploads/orphan.jpg', out.getvalue())
        self.assertTrue(os.path.exists(orphan))

        call_command('clean_media', '--delete', stdout=StringIO())
        self.assertFalse(os.path.exists(orphan))
        self.assertTrue(os.path.exists(recipe.image.path))


class RecipeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tag = Tag.objects.create(name="Plat principal")
        cls.recipe = Recipe.objects.create(name="Croquetes d'espinacs", ingredients="300g d'espinacs\nPer a la beixamel:\n- 30g de farina")
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
        self.assertContains(response, '<li><span class="qty" data-q="300">300</span>g d&#x27;espinacs</li>', html=True)
        self.assertContains(response, '<h3 class="section-title">Per a la beixamel</h3>', html=True)
        self.assertContains(response, '<li><span class="qty" data-q="30">30</span>g de farina</li>', html=True)

    def test_scaler_on_detail(self):
        recipe = Recipe.objects.create(name="Poke", ingredients="Per a 2 persones:\n200g d'arròs",
                                       preparation="Rentar els 200g d'arròs")
        response = self.client.get(recipe.get_absolute_url())
        self.assertContains(response, 'data-mode="servings"')
        self.assertContains(response, 'data-base="2"')
        self.assertContains(response, '<span class="qty" data-q="200">200</span>', count=2)
        self.assertNotContains(response, '<h3 class="section-title">Per a 2 persones</h3>', html=True)

    def test_text_is_escaped(self):
        recipe = Recipe.objects.create(name="XSS", preparation="<script>alert(1)</script>")
        response = self.client.get(recipe.get_absolute_url())
        self.assertNotContains(response, "<script>alert(1)")
        self.assertContains(response, "&lt;script&gt;")

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

    def test_edit(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@a.a", "pass"))
        url = reverse('recipe_edit', args=[self.recipe.slug])
        self.assertContains(self.client.get(url), "Editar recepta")

        response = self.client.post(url, {'name': "Croquetes", 'slug': self.recipe.slug, 'prep_time': 40})
        self.assertRedirects(response, self.recipe.get_absolute_url())
        self.recipe.refresh_from_db()
        self.assertEqual((self.recipe.name, self.recipe.prep_time), ("Croquetes", 40))

    def test_edit_requires_staff(self):
        response = self.client.get(reverse('recipe_edit', args=[self.recipe.slug]))
        self.assertEqual(response.status_code, 302)

    def test_cooking_log_on_detail(self):
        Make.objects.create(recipe=self.recipe, date=datetime.date(2026, 10, 12), notes="Més sal")
        response = self.client.get(self.recipe.get_absolute_url())
        self.assertContains(response, "12/10/2026")
        self.assertContains(response, "Més sal")
        self.assertContains(self.client.get(reverse('recipe_list')), "1× cuinada")

    def test_menus(self):
        menu = Menu.objects.create(name="Sopar de Nadal", date=datetime.date(2026, 12, 24))
        menu.recipes.add(self.recipe)
        self.assertContains(self.client.get(reverse('menu_list')), "Sopar de Nadal")
        response = self.client.get(menu.get_absolute_url())
        self.assertContains(response, "24/12/2026")
        self.assertContains(response, "Croquetes d&#x27;espinacs")

    def test_create_shows_errors(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@a.a", "pass"))
        response = self.client.post(reverse('recipe_create'), {'name': "Una altra", 'slug': self.recipe.slug})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invalid-feedback d-block')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RestaurantTests(TestCase):
    def setUp(self):
        self.visit = RestaurantVisit.objects.create(
            name="Disfrutar", city="Barcelona", date=datetime.date(2026, 10, 4),
            menu_name="Menú Festival", notes="Increïble <b>de debò</b>")
        Dish.objects.create(visit=self.visit, name="Olivas verdes", order=2)
        Dish.objects.create(visit=self.visit, name="Panchino de caviar", order=1, image=make_image())

    def test_slug_and_photos(self):
        self.assertEqual(self.visit.slug, "disfrutar")
        again = RestaurantVisit.objects.create(name="Disfrutar", date=datetime.date(2026, 11, 1))
        self.assertEqual(again.slug, "disfrutar-2")
        self.assertEqual(len(self.visit.photos), 1)

    def test_list(self):
        response = self.client.get(reverse('visit_list'))
        self.assertContains(response, "Disfrutar")
        self.assertContains(response, "Menú Festival")
        self.assertContains(response, reverse('visit_list'))  # Nav link

    def test_detail_orders_dishes_and_escapes_notes(self):
        response = self.client.get(reverse('visit_detail', args=[self.visit.slug]))
        content = response.content.decode()
        self.assertLess(content.index("Panchino de caviar"), content.index("Olivas verdes"))
        self.assertContains(response, "&lt;b&gt;de debò&lt;/b&gt;")
        self.assertNotContains(response, "Editar")

    def test_detail_404(self):
        self.assertEqual(self.client.get(reverse('visit_detail', args=["no-existeix"])).status_code, 404)

    def test_dish_image_removed_with_visit(self):
        path = self.visit.dishes.get(order=1).image.path
        with self.captureOnCommitCallbacks(execute=True):
            self.visit.delete()
        self.assertFalse(os.path.exists(path))


class PlainTextTests(TestCase):
    def test_sections(self):
        text = "1. Bullir\n\n- Escórrer\nPer a la salsa:\n• Triturar 2) tomàquets"
        self.assertEqual(sections(text), [
            {'title': None, 'items': ["Bullir", "Escórrer"]},
            {'title': "Per a la salsa", 'items': ["Triturar 2) tomàquets"]},
        ])
        self.assertEqual(sections(""), [])

    def test_servings(self):
        self.assertEqual(servings("Per a 24 crestes:\n3 llaunes"), {'title': "Per a 24 crestes", 'amount': 24, 'unit': "crestes"})
        self.assertEqual(servings("per 2,5 persones:"), {'title': "per 2,5 persones", 'amount': 2.5, 'unit': "persones"})
        self.assertIsNone(servings("Per a la salsa:\n1 ou"))

    def test_quantities_scaled(self):
        html = quantities("Els 200g d'arròs, 1/2 mango, 1½ ous i 2-3 pebrots")
        for value, text in [("200", "200"), ("0.5", "1/2"), ("1.5", "1½"), ("2", "2"), ("3", "3")]:
            self.assertIn(f'<span class="qty" data-q="{value}">{text}</span>', html)

    def test_quantities_fixed(self):
        for line in ["Coure 20min a 180 graus", "1.5x d'aigua", "Barreja 50/50", "Daus de 2cm", "Repetir 2 vegades",
                     "Forn a 200°C", "Vitamina B12"]:
            self.assertNotIn('class="qty"', quantities(line), line)

    def test_quantities_escape_and_links(self):
        html = quantities('<b>2</b> ous, mira https://ex.cat/3')
        self.assertIn('&lt;b&gt;', html)
        self.assertIn('<a href="https://ex.cat/3"', html)
        self.assertNotIn('data-q="3"', html)

    def test_html_conversion(self):
        html_to_text = importlib.import_module('receptes_app.migrations.0005_html_to_plain_text').html_to_text
        self.assertEqual(html_to_text("<ul><li>1 ou</li><li>200g&nbsp;farina</li></ul>"), ("1 ou\n200g farina", 0))
        self.assertEqual(html_to_text("<p><strong>Massa</strong></p><h3>Salsa</h3>"), ("Massa:\nSalsa:", 0))
        self.assertEqual(html_to_text('<p>Mira <a href="https://x.cat">aqui</a></p>'), ("Mira aqui (https://x.cat)", 0))
        self.assertEqual(html_to_text("<p>&nbsp;</p>"), ("", 0))
        self.assertEqual(html_to_text('<figure><img src="/media/a.png"></figure>'), ("", 1))


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class ProxyTests(TestCase):
    def test_https_from_cloudflare_is_detected(self):
        recipe = Recipe.objects.create(name="Amb foto", image=make_image())
        # As forwarded by Cloudflare -> nginx: original host without port, protocol in a header
        with self.settings(ALLOWED_HOSTS=['receptes.example']):
            response = self.client.get(recipe.get_absolute_url(), HTTP_HOST='receptes.example',
                                       HTTP_X_FORWARDED_PROTO='https')
        self.assertContains(response, 'content="https://receptes.example/media/')
