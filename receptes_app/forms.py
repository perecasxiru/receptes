from django import forms
from .models import Recipe, Tag, Tool
from django_ckeditor_5.widgets import CKEditor5Widget


class RecipeForm(forms.ModelForm):
    name = forms.CharField(
        label="Nom",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    slug = forms.SlugField(
        label="Slug (URL)",
        max_length=110,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    link = forms.URLField(
        label="Enllaç",
        required=False,
        widget=forms.URLInput(attrs={'class': 'form-control'})
    )
    ingredients = forms.CharField(
        label="Ingredients",
        widget=CKEditor5Widget(),
        required=False
    )
    preparation = forms.CharField(
        label="Preparació",
        widget=CKEditor5Widget(),
        required=False
    )
    prep_time = forms.IntegerField(
        label="Temps (minuts)",
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    image = forms.ImageField(
        label="Imatge",
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    tags = forms.ModelMultipleChoiceField(
        label="Etiquetes",
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    tools = forms.ModelMultipleChoiceField(
        label="Estris",
        queryset=Tool.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Recipe
        fields = ['name', 'slug', 'link', 'ingredients', 'preparation', 'prep_time', 'image', 'tags', 'tools']
