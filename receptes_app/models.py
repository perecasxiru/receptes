from django.db import models

# Create your models here.

import os
import re
import uuid
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image
import io
from django.urls import reverse
from django_ckeditor_5.fields import CKEditor5Field


def random_file_name(instance, filename):
    """
    Generates a random file name for uploaded images.
    Retains the original file extension.
    """
    ext = os.path.splitext(filename)[-1]  # Get the file extension
    random_name = uuid.uuid4().hex  # Generate a random UUID
    return f"uploads/{random_name}{ext}"  # Store in 'uploads' folder with a random name


def resize_image(image, max_size=(800, 800)):
    """
    Resize the image to a specified max size while maintaining aspect ratio.
    """
    img = Image.open(image)
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        img = img.convert('RGB')

    img.thumbnail(max_size)  # Resize image

    # Save the resized image to a bytes buffer
    output = io.BytesIO()
    img.save(output, format='JPEG', quality=85)  # You can adjust the quality here
    output.seek(0)

    # Create a new InMemoryUploadedFile object with the resized image
    return InMemoryUploadedFile(output, 'ImageField', image.name, 'image/jpeg', output.tell(), None)


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(null=True)
    link = models.URLField(null=True, blank=True)
    ingredients = CKEditor5Field(null=True, blank=True)
    preparation = CKEditor5Field(null=True, blank=True)
    prep_time = models.IntegerField(help_text="Preparation time in minutes", null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    image = models.ImageField(upload_to=random_file_name, null=True, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="recipes")
    tools = models.ManyToManyField(Tool, blank=True, related_name="recipes")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Check if the image has been uploaded and resize it
        if self.image:
            self.image = resize_image(self.image)
        self.preparation = self._process_description_links(self.preparation)
        self.ingredients = self._process_description_links(self.ingredients)

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('recipe_detail', kwargs={'pk': self.pk, 'slug': self.slug})

    def _process_description_links(self, text):
        """
        Replaces placeholders like [[Recipe Name]] with HTML links to the corresponding recipe.
        """

        def replace_match(match):
            my_slug = match.group(1)
            try:
                # Look up the recipe by name
                linked_recipe = Recipe.objects.get(slug=my_slug)
                # Create a link to the recipe
                return f'<a href="{linked_recipe.get_absolute_url()}">{linked_recipe.name}</a>'
            except Recipe.DoesNotExist:
                # If no recipe is found, leave the text as it is
                return match.group(0)

        # Use a regular expression to find all [[Recipe Name]] patterns
        return re.sub(r'\[\[(.*?)\]\]', replace_match, text)


class Menu(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(null=True)
    date = models.DateField()
    description = CKEditor5Field(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    recipes = models.ManyToManyField(Recipe)

    def __str__(self):
        return self.name


class Make(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="makes")
    date = models.DateField()
    notes = CKEditor5Field(blank=True, help_text="Optional notes about this make")
    image = models.ImageField(upload_to=random_file_name, null=True, blank=True)

    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return f"Make of {self.recipe.name} on {self.date}"

    def save(self, *args, **kwargs):
        # Check if the image has been uploaded and resize it
        if self.image:
            self.image = resize_image(self.image)
        super().save(*args, **kwargs)