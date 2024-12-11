from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from .services import get_worksheet


def get_choices(t='Tags'):
    _worksheet = get_worksheet('ReceptesApp', t)
    _all = _worksheet.get_all_records()
    return sorted([(str(_['name']), _['name']) for _ in _all])


class RecipeForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    slug = forms.SlugField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    link = forms.URLField(required=False, widget=forms.URLInput(attrs={'class': 'form-control'}))
    ingredients = forms.CharField(widget=CKEditor5Widget(), required=False)
    preparation = forms.CharField(widget=CKEditor5Widget(), required=False)
    prep_time = forms.IntegerField(help_text="Preparation time in minutes",
                                   required=False,
                                   widget=forms.NumberInput(attrs={'class': 'form-control'}))
    image = forms.ImageField(required=False, widget=forms.FileInput(attrs={'class': 'form-control'}))
    tags = forms.MultipleChoiceField(choices=get_choices('Tags'),
                                     widget=forms.CheckboxSelectMultiple, required=False)
    tools = forms.MultipleChoiceField(choices=get_choices('Tools'),
                                     widget=forms.CheckboxSelectMultiple, required=False)