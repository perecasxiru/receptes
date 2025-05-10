from django.views.generic import ListView, DetailView
from .models import Tag, Recipe, Menu, Make, Tool
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from datetime import datetime
from django.conf import settings
from django.http import HttpResponseForbidden
from .forms import RecipeForm
from django.utils.text import slugify
import time


def get_recipe_list(request):
    tag_filter = request.GET.get('tag')
    search_query = request.GET.get('search', '').strip()

    # Start with all recipes
    recipes = Recipe.objects.prefetch_related('tags', 'tools')

    # Filter by tag if provided
    if tag_filter:
        recipes = recipes.filter(tags__name=tag_filter)

    # Filter by search query in name
    if search_query:
        recipes = recipes.filter(name__icontains=search_query)

    # Pagination
    paginator = Paginator(recipes, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'selected_tag': tag_filter,
        'search_query': search_query,
        'tags': Tag.objects.all(),
        'is_debug': settings.DEBUG,
    }
    return render(request, 'recipes/recipe_list.html', context)


def get_recipe_detail(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    context = {
        'recipe': recipe,
    }
    return render(request, 'recipes/recipe_detail.html', context)


def create_recipe(request):
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            recipe = form.save(commit=False)

            # Auto-generate unique slug if not provided
            if not recipe.slug:
                base_slug = slugify(recipe.name)
                unique_slug = base_slug
                counter = 2
                while Recipe.objects.filter(slug=unique_slug).exists():
                    unique_slug = f"{base_slug}-{counter}"
                    counter += 1
                recipe.slug = unique_slug

            recipe.created_at = datetime.now()
            recipe.updated_at = datetime.now()
            recipe.save()

            # Add M2M relations after saving the object
            form.cleaned_data['tags'] and recipe.tags.set(form.cleaned_data['tags'])
            form.cleaned_data['tools'] and recipe.tools.set(form.cleaned_data['tools'])

            return redirect('recipe_list')
    else:
        form = RecipeForm()
    return render(request, 'recipes/recipe_create.html', {'form': form})
