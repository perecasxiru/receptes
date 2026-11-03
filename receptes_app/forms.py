from django import forms
from .models import Recipe, Tag, Tool


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
        help_text="Un per línia. Acaba una línia amb «:» per fer un subtítol.",
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 12,
            'placeholder': "300g d'espinacs\n1 ceba\nPer a la beixamel:\n30g de farina\n75g de llet",
        }),
        required=False
    )
    preparation = forms.CharField(
        label="Preparació",
        help_text="Un pas per línia; es numeren sols.",
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 12,
            'placeholder': "Bullir els espinacs 2 minuts.\nSofregir la ceba tallada petita.",
        }),
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
