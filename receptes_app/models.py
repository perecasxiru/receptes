from django.db import models
from django.urls import reverse
from django_ckeditor_5.fields import CKEditor5Field
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

# -------------------------------
# Abstract Base for Resizeable Image
# -------------------------------

class ResizableImageMixin:
    def resize_image_field(self, field_name):
        image_field = getattr(self, field_name)
        # Only process freshly uploaded files; already stored images are left untouched
        if image_field and not image_field._committed:
            resized = resize_image(image_field)
            name = os.path.splitext(image_field.name)[0] + '.jpg'
            image_field.save(name, resized, save=False)

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
    ingredients = CKEditor5Field(null=True, blank=True)
    preparation = CKEditor5Field(null=True, blank=True)
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

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, Recipe)
        if self.image:
            self.resize_image_field('image')
        super().save(*args, **kwargs)


class Menu(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    date = models.DateField()
    description = CKEditor5Field(null=True, blank=True)
    recipes = models.ManyToManyField(Recipe)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, Menu)
        super().save(*args, **kwargs)


class Make(models.Model, ResizableImageMixin):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="makes")
    date = models.DateField()
    notes = CKEditor5Field(blank=True)
    image = models.ImageField(upload_to=random_file_name, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Make of {self.recipe.name} on {self.date}"

    def save(self, *args, **kwargs):
        if self.image:
            self.resize_image_field('image')
        super().save(*args, **kwargs)
