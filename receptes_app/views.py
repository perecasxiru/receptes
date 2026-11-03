from django.views.generic import ListView, DetailView
from .models import Tag, Recipe, Menu, Make, Tool
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from django.conf import settings
from django.http import HttpResponseForbidden
from .forms import RecipeForm
from django.contrib.admin.views.decorators import staff_member_required



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


@staff_member_required
def create_recipe(request):
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            # Slug (if left empty) and image resizing are handled in Recipe.save()
            form.save()
            return redirect('recipe_list')
    else:
        form = RecipeForm()
    return render(request, 'recipes/recipe_create.html', {'form': form})
