from django import forms
from PIL import Image

from .models import Recipe, RestaurantVisit, Tag, Tool


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
        help_text="Un per línia. Acaba una línia amb «:» per fer un subtítol. "
                  "Comença amb «Per a 4 persones:» per poder ajustar les quantitats.",
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 12,
            'placeholder': "Per a 4 persones:\n300g d'espinacs\n1 ceba\nPer a la beixamel:\n30g de farina\n75g de llet",
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


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """An image field that accepts several files and returns them as a list."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleImageInput(attrs={'accept': 'image/*'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super(MultipleImageField, self).clean(file, initial) for file in data]
        return [super().clean(data, initial)] if data else []


def taken_at(file):
    """When the photo was taken, from its EXIF data ('YYYY:MM:DD HH:MM:SS'), or None."""
    try:
        exif = Image.open(file).getexif()
        return exif.get_ifd(0x8769).get(36867) or exif.get(306)  # DateTimeOriginal, else DateTime
    except Exception:
        return None
    finally:
        file.seek(0)


class RestaurantVisitAdminForm(forms.ModelForm):
    dish_photos = MultipleImageField(
        label="Pujar fotos de plats", required=False,
        help_text="Pots triar-ne moltes alhora: cada foto es converteix en un plat, ordenats per "
                  "l'hora en què es van fer. Després de desar podràs posar-los nom.")

    class Meta:
        model = RestaurantVisit
        fields = '__all__'

    def sorted_dish_photos(self):
        photos = self.cleaned_data.get('dish_photos') or []
        # Photos without a date keep their upload order, after the dated ones
        keyed = [(taken_at(photo), i, photo) for i, photo in enumerate(photos)]
        return [photo for date, i, photo in sorted(keyed, key=lambda k: (k[0] is None, k[0] or '', k[1]))]
