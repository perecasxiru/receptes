from django import forms
from .models import Recipe, Tag, Tool
from django_ckeditor_5.widgets import CKEditor5Widget
from django.utils.text import slugify


class RecipeForm(forms.ModelForm):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    slug = forms.SlugField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    link = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control'})
    )
    ingredients = forms.CharField(
        widget=CKEditor5Widget(),
        required=False
    )
    preparation = forms.CharField(
        widget=CKEditor5Widget(),
        required=False
    )
    prep_time = forms.IntegerField(
        help_text="Preparation time in minutes",
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    tools = forms.ModelMultipleChoiceField(
        queryset=Tool.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Recipe
        fields = ['name', 'slug', 'link', 'ingredients', 'preparation', 'prep_time', 'image', 'tags', 'tools']

    def save(self, commit=True):
        recipe = super().save(commit=False)

        # Optionally handle the slug if it's not set
        if not recipe.slug:
            recipe.slug = slugify(recipe.name)

        if commit:
            recipe.save()
            # Set M2M relations manually after saving the object
            self.cleaned_data['tags'] and recipe.tags.set(self.cleaned_data['tags'])
            self.cleaned_data['tools'] and recipe.tools.set(self.cleaned_data['tools'])

        return recipe
