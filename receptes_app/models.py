from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.text import slugify
from django.core.files.base import ContentFile

from PIL import Image, ImageOps
from io import BytesIO
import os
import uuid

# -------------------------------
# Utilities
# -------------------------------

def random_file_name(instance, filename):
    ext = os.path.splitext(filename)[-1]
    return f"uploads/{uuid.uuid4().hex}{ext}"

def resize_image(image_file, max_size=(800, 800)):
    img = Image.open(image_file)
    img = ImageOps.exif_transpose(img)  # Respect phone camera orientation
    if img.mode != 'RGB':
        img = img.convert('RGB')
    img.thumbnail(max_size)

    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=85)
    return ContentFile(buffer.getvalue())

def generate_unique_slug(instance, model_class, field_name='slug'):
    """
    Generates a unique slug for the given instance.
    """
    max_length = model_class._meta.get_field(field_name).max_length
    base_slug = slugify(getattr(instance, 'name', ''))[:max_length - 4] or 'item'
    slug = base_slug
    counter = 2
    while model_class.objects.filter(**{field_name: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

def delete_file_on_commit(field_file, name):
    """Remove a stored file once the current transaction succeeds."""
    if name:
        storage = field_file.storage
        transaction.on_commit(lambda: storage.delete(name))

# -------------------------------
# Abstract Base for Resizeable Image
# -------------------------------

class ResizableImageMixin:
    # Image fields to resize, with their maximum size; override per model
    image_fields = {'image': (800, 800)}

    def resize_image_field(self, field_name, max_size=(800, 800)):
        image_field = getattr(self, field_name)
        # Only process freshly uploaded files; already stored images are left untouched
        if image_field and not image_field._committed:
            resized = resize_image(image_field, max_size)
            name = os.path.splitext(image_field.name)[0] + '.jpg'
            image_field.save(name, resized, save=False)

    def save_with_image(self, *args, **kwargs):
        """Resize new images and delete previous files that were replaced or cleared."""
        fields = list(self.image_fields)
        old_names = {}
        if self.pk:
            old_names = type(self).objects.filter(pk=self.pk).values(*fields).first() or {}
        for field, max_size in self.image_fields.items():
            self.resize_image_field(field, max_size)
        models.Model.save(self, *args, **kwargs)  # Mixin is listed after Model, so super() would skip it
        for field in fields:
            old_name, current = old_names.get(field), getattr(self, field)
            if old_name and old_name != current.name:
                delete_file_on_commit(current, old_name)

# -------------------------------
# Core Models
# -------------------------------

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Recipe(models.Model, ResizableImageMixin):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    link = models.URLField(null=True, blank=True)
    ingredients = models.TextField(
        blank=True, default='',
        help_text="Un ingredient per línia. Una línia acabada en «:» és un subtítol (p. ex. «Per a la salsa:»).")
    preparation = models.TextField(
        blank=True, default='',
        help_text="Un pas per línia. Una línia acabada en «:» és un subtítol.")
    prep_time = models.IntegerField(null=True, blank=True, help_text="Preparation time in minutes")
    image = models.ImageField(upload_to=random_file_name, null=True, blank=True)

    tags = models.ManyToManyField(Tag, blank=True, related_name="recipes")
    tools = models.ManyToManyField(Tool, blank=True, related_name="recipes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('recipe_detail', args=[self.slug])

    @property
    def display_image(self):
        """The recipe's own photo, or else the most recent photo from its cooking log."""
        if self.image:
            return self.image
        for make in self.makes.all():  # Ordered by -date; prefetch 'makes' in list views
            if make.image:
                return make.image
        return None

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, Recipe)
        self.ingredients = (self.ingredients or '').strip()
        self.preparation = (self.preparation or '').strip()
        self.save_with_image(*args, **kwargs)


class Menu(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    date = models.DateField()
    description = models.TextField(blank=True, default='')
    recipes = models.ManyToManyField(Recipe)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('menu_detail', args=[self.slug])

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, Menu)
        self.description = (self.description or '').strip()
        super().save(*args, **kwargs)


class Make(models.Model, ResizableImageMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="makes")
    date = models.DateField()
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to=random_file_name, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Make of {self.recipe.name} on {self.date}"

    def save(self, *args, **kwargs):
        self.notes = (self.notes or '').strip()
        self.save_with_image(*args, **kwargs)


class RestaurantVisit(models.Model, ResizableImageMixin):
    """A meal out: a tasting menu (many dishes) or a single memorable plate."""
    name = models.CharField("restaurant", max_length=100)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    city = models.CharField("ciutat", max_length=100, blank=True, default='')
    date = models.DateField("data")
    menu_name = models.CharField(
        "menú", max_length=150, blank=True, default='',
        help_text="Opcional, p. ex. «Menú degustació de tardor».")
    notes = models.TextField("notes", blank=True, default='')
    link = models.URLField("enllaç", null=True, blank=True)
    image = models.ImageField(
        "foto de portada", upload_to=random_file_name, null=True, blank=True,
        help_text="Opcional: si no n'hi ha, es fan servir les fotos dels plats.")
    menu_photo = models.ImageField(
        "foto de la carta", upload_to=random_file_name, null=True, blank=True,
        help_text="Opcional: una foto del menú imprès. Es guarda a més resolució perquè es pugui llegir.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Menus are mostly small print, so keep them large enough to read
    image_fields = {'image': (800, 800), 'menu_photo': (2000, 2000)}

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "visita a restaurant"
        verbose_name_plural = "visites a restaurants"

    def __str__(self):
        return f"{self.name} ({self.date:%d/%m/%Y})" if self.date else self.name

    def get_absolute_url(self):
        return reverse('visit_detail', args=[self.slug])

    @property
    def photos(self):
        """Cover photo first, then dish photos; prefetch 'dishes' in list views."""
        photos = [self.image] if self.image else []
        return photos + [dish.image for dish in self.dishes.all() if dish.image]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, RestaurantVisit)
        self.notes = (self.notes or '').strip()
        self.save_with_image(*args, **kwargs)


class Dish(models.Model, ResizableImageMixin):
    visit = models.ForeignKey(RestaurantVisit, on_delete=models.CASCADE, related_name="dishes")
    name = models.CharField("plat", max_length=150)
    notes = models.TextField("notes", blank=True, default='')
    image = models.ImageField("foto", upload_to=random_file_name, null=True, blank=True)
    # Sharper copy for the full-screen viewer, made from each new upload; the grid keeps the small one
    image_large = models.ImageField(upload_to=random_file_name, null=True, blank=True, editable=False)
    order = models.PositiveSmallIntegerField("ordre", default=0)

    image_fields = {'image': (800, 800), 'image_large': (1800, 1800)}

    class Meta:
        ordering = ['order', 'pk']
        verbose_name = "plat"
        verbose_name_plural = "plats"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.notes = (self.notes or '').strip()
        if self.image and not self.image._committed:
            self.image.open()
            data = self.image.read()
            self.image.seek(0)
            self.image_large = ContentFile(data, name=os.path.basename(self.image.name))
        elif not self.image:
            self.image_large = None
        self.save_with_image(*args, **kwargs)


@receiver(post_delete, sender=Recipe)
@receiver(post_delete, sender=Make)
@receiver(post_delete, sender=RestaurantVisit)
@receiver(post_delete, sender=Dish)
def delete_image_file(sender, instance, **kwargs):
    for field in instance.image_fields:
        file = getattr(instance, field)
        if file:
            delete_file_on_commit(file, file.name)
