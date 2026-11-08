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
        visit = RestaurantVisit.objects.create(name="Fora", date=datetime.date(2026, 10, 4))
        dish = Dish.objects.create(visit=visit, name="Plat", image=make_image())
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
        self.assertTrue(os.path.exists(dish.image_large.path))  # The viewer's copy counts as used


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

    def test_menu_photo_kept_large_and_shown(self):
        self.visit.menu_photo = make_image(size=(3000, 4000))
        self.visit.save()
        with Image.open(self.visit.menu_photo.path) as img:
            self.assertEqual(img.size, (1500, 2000))
        self.assertEqual(len(self.visit.photos), 1)  # Not part of the collage
        self.assertContains(self.client.get(self.visit.get_absolute_url()), self.visit.menu_photo.url)

        path = self.visit.menu_photo.path
        with self.captureOnCommitCallbacks(execute=True):
            self.visit.delete()
        self.assertFalse(os.path.exists(path))

    def test_dish_keeps_large_copy_for_viewer(self):
        dish = Dish.objects.create(visit=self.visit, name="Gran", order=3, image=make_image(size=(4000, 3000)))
        with Image.open(dish.image.path) as img:
            self.assertEqual(img.size, (800, 600))
        with Image.open(dish.image_large.path) as img:
            self.assertEqual(img.size, (1800, 1350))
        # The grid shows the small file; the viewer link points at the large one
        response = self.client.get(self.visit.get_absolute_url())
        self.assertContains(response, f'src="{dish.image.url}"')
        self.assertContains(response, f'href="{dish.image_large.url}"')

        # Clearing the photo drops both files
        small, large = dish.image.path, dish.image_large.path
        dish.image = None
        with self.captureOnCommitCallbacks(execute=True):
            dish.save()
        self.assertIsNone(dish.image_large.name)
        self.assertFalse(os.path.exists(small) or os.path.exists(large))

        # Deleting the dish removes both too
        dish.image = make_image()
        dish.save()
        small, large = dish.image.path, dish.image_large.path
        with self.captureOnCommitCallbacks(execute=True):
            dish.delete()
        self.assertFalse(os.path.exists(small) or os.path.exists(large))

    def test_bulk_dish_photos_in_admin(self):
        def photo(name, colour, taken=None):
            img, buffer = Image.new('RGB', (1200, 900), colour), BytesIO()
            exif = img.getexif()
            if taken:
                exif[306] = taken  # DateTime
            img.save(buffer, 'JPEG', exif=exif)
            return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/jpeg')

        self.client.force_login(User.objects.create_superuser("admin", "a@a.a", "pass"))
        url = reverse('admin:receptes_app_restaurantvisit_change', args=[self.visit.pk])
        existing = list(self.visit.dishes.all())
        data = {
            'name': self.visit.name, 'slug': self.visit.slug, 'city': self.visit.city,
            'date': '2026-10-04', 'menu_name': self.visit.menu_name, 'notes': '',
            'dishes-TOTAL_FORMS': len(existing), 'dishes-INITIAL_FORMS': len(existing),
            'dishes-MIN_NUM_FORMS': 0, 'dishes-MAX_NUM_FORMS': 1000,
            'dish_photos': [
                photo('c.jpg', 'green', '2026:10:04 22:10:00'),
                photo('undated.jpg', 'blue'),
                photo('a.jpg', 'red', '2026:10:04 20:30:00'),
            ],
        }
        for i, dish in enumerate(existing):
            data.update({f'dishes-{i}-id': dish.pk, f'dishes-{i}-visit': self.visit.pk,
                         f'dishes-{i}-order': dish.order, f'dishes-{i}-name': dish.name})

        response = self.client.post(url, data)
        self.assertRedirects(response, url)  # Back to the form to name the new dishes

        new = list(self.visit.dishes.all())[2:]
        self.assertEqual([d.name for d in new], ["Plat 3", "Plat 4", "Plat 5"])
        self.assertEqual([d.order for d in new], [3, 4, 5])
        # Taken-at order, undated last; images resized like any dish photo
        sizes, colours = [], []
        for d in new:
            with Image.open(d.image.path) as img:
                sizes.append(img.size)
                pixel = img.getpixel((10, 10))
                colours.append(('red', 'green', 'blue')[pixel.index(max(pixel))])
        self.assertEqual(colours, ['red', 'green', 'blue'])
        self.assertEqual(sizes, [(800, 600)] * 3)

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


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SiteFormTests(TestCase):
    """Staff pages for creating and editing menus and restaurant visits."""
    def setUp(self):
        self.recipe = Recipe.objects.create(name="Canelons")
        self.visit = RestaurantVisit.objects.create(name="Can Jubany", date=datetime.date(2026, 11, 6))
        self.dish = Dish.objects.create(visit=self.visit, name="Plat 1", order=1, image=make_image())

    def login(self):
        self.client.force_login(User.objects.create_superuser("admin", "a@a.a", "pass"))

    def dish_data(self, **changes):
        data = {
            'dishes-TOTAL_FORMS': 2, 'dishes-INITIAL_FORMS': 1, 'dishes-MIN_NUM_FORMS': 0, 'dishes-MAX_NUM_FORMS': 1000,
            'dishes-0-id': self.dish.pk, 'dishes-0-visit': self.visit.pk, 'dishes-0-order': 1,
            'dishes-0-name': "Plat 1", 'dishes-0-notes': '',
            'dishes-1-visit': self.visit.pk, 'dishes-1-order': 2, 'dishes-1-name': '', 'dishes-1-notes': '',
        }
        data.update(changes)
        return data

    def visit_data(self, **changes):
        data = {'name': "Can Jubany", 'slug': self.visit.slug, 'date': '2026-11-06', 'city': "Calldetenes"}
        data.update(changes)
        return data

    def test_pages_require_staff(self):
        for url in (reverse('menu_create'), reverse('visit_create'), reverse('visit_edit', args=[self.visit.slug])):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.assertNotContains(self.client.get(reverse('visit_list')), reverse('visit_create'))

    def test_nav_offers_create_for_the_section(self):
        self.login()
        menus = self.client.get(reverse('menu_list'))
        self.assertContains(menus, reverse('menu_create'))
        self.assertContains(menus, reverse('recipe_create'))
        self.assertNotContains(menus, reverse('visit_create'))
        self.assertContains(self.client.get(self.visit.get_absolute_url()), reverse('visit_create'))
        self.assertNotContains(self.client.get(reverse('recipe_list')), reverse('menu_create'))

    def test_create_and_edit_menu(self):
        self.login()
        response = self.client.post(reverse('menu_create'), {
            'name': "Sopar de Nadal", 'date': '2026-12-24', 'recipes': [self.recipe.pk]})
        menu = Menu.objects.get(slug="sopar-de-nadal")
        self.assertRedirects(response, menu.get_absolute_url())
        self.assertEqual(list(menu.recipes.all()), [self.recipe])
        self.assertContains(self.client.get(menu.get_absolute_url()), reverse('menu_edit', args=[menu.slug]))

        url = reverse('menu_edit', args=[menu.slug])
        self.assertContains(self.client.get(url), 'value="2026-12-24"')
        self.client.post(url, {'name': "Sopar de Nadal", 'slug': menu.slug, 'date': '2026-12-25', 'recipes': []})
        menu.refresh_from_db()
        self.assertEqual((menu.date, menu.recipes.count()), (datetime.date(2026, 12, 25), 0))

    def test_reserved_slug(self):
        self.login()
        response = self.client.post(reverse('menu_create'), {'name': "Nou", 'slug': 'nou', 'date': '2026-12-24'})
        self.assertContains(response, "reservat")
        # Left empty, the slug is generated around the reserved word
        self.assertEqual(Menu.objects.create(name="Nou", date=datetime.date(2026, 1, 1)).slug, "nou-2")

    def test_create_visit_with_photos_goes_to_naming(self):
        self.login()
        response = self.client.post(reverse('visit_create'), {
            'name': "Disfrutar", 'date': '2026-10-04', 'dish_photos': [make_image(), make_image()]})
        visit = RestaurantVisit.objects.get(slug="disfrutar")
        self.assertRedirects(response, reverse('visit_edit', args=[visit.slug]), fetch_redirect_response=False)
        self.assertEqual([d.name for d in visit.dishes.all()], ["Plat 1", "Plat 2"])
        self.assertContains(self.client.get(reverse('visit_edit', args=[visit.slug])), "S&#x27;han afegit 2 plats")

    def test_create_visit_without_photos_shows_it(self):
        self.login()
        response = self.client.post(reverse('visit_create'), {'name': "Disfrutar", 'date': '2026-10-04'})
        self.assertRedirects(response, RestaurantVisit.objects.get(slug="disfrutar").get_absolute_url())

    def test_edit_visit_renames_adds_and_deletes_dishes(self):
        self.login()
        url = reverse('visit_edit', args=[self.visit.slug])
        page = self.client.get(url)
        self.assertContains(page, 'value="Plat 1"')
        self.assertContains(page, 'name="dishes-1-order" value="2"')  # Blank row goes after the last dish

        # Saving without touching the blank row doesn't add a dish
        self.assertRedirects(self.client.post(url, self.visit_data(**self.dish_data())), self.visit.get_absolute_url())
        self.assertEqual(self.visit.dishes.count(), 1)

        response = self.client.post(url, self.visit_data(**self.dish_data(**{
            'dishes-0-name': "Olives", 'dishes-1-name': "Pa i oli", 'dishes-1-order': 2})))
        self.assertRedirects(response, self.visit.get_absolute_url())
        self.assertEqual([d.name for d in self.visit.dishes.all()], ["Olives", "Pa i oli"])
        self.assertTrue(os.path.exists(self.dish.image.path))  # Renaming keeps the photo

        path = self.dish.image.path
        pa = self.visit.dishes.get(name="Pa i oli")
        data = self.visit_data(**self.dish_data(**{
            'dishes-TOTAL_FORMS': 2, 'dishes-INITIAL_FORMS': 2, 'dishes-0-name': "Olives", 'dishes-0-DELETE': 'on',
            'dishes-1-id': pa.pk, 'dishes-1-name': "Pa i oli", 'dishes-1-order': 2}))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, data)
        self.assertEqual([d.name for d in self.visit.dishes.all()], ["Pa i oli"])
        self.assertFalse(os.path.exists(path))

    def test_edit_visit_shows_dish_errors(self):
        self.login()
        response = self.client.post(reverse('visit_edit', args=[self.visit.slug]),
                                    self.visit_data(**self.dish_data(**{'dishes-0-name': ''})))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revisa els camps marcats")
        self.assertEqual(self.visit.dishes.get().name, "Plat 1")

