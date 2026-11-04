from .models import Tag, Recipe, Menu
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .forms import RecipeForm
from django.contrib.admin.views.decorators import staff_member_required



def get_recipe_list(request):
    tag_filter = request.GET.get('tag')
    search_query = request.GET.get('search', '').strip()

    # Start with all recipes
    recipes = Recipe.objects.prefetch_related('tags', 'tools', 'makes')

    # Filter by tag if provided
    if tag_filter:
        recipes = recipes.filter(tags__name=tag_filter)

    # Filter by search query in name or ingredients
    if search_query:
        recipes = recipes.filter(Q(name__icontains=search_query) | Q(ingredients__icontains=search_query))

    # Pagination
    paginator = Paginator(recipes, 36)  # Divisible by 2, 3 and 4 columns, so the last row is full
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'selected_tag': tag_filter,
        'search_query': search_query,
        'tags': Tag.objects.all(),
    }
    return render(request, 'recipes/recipe_list.html', context)


def get_recipe_detail(request, slug):
    recipe = get_object_or_404(Recipe.objects.prefetch_related('tags', 'tools', 'makes'), slug=slug)
    context = {
        'recipe': recipe,
        'makes': recipe.makes.all(),
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


@staff_member_required
def edit_recipe(request, slug):
    recipe = get_object_or_404(Recipe, slug=slug)
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
        if form.is_valid():
            recipe = form.save()
            return redirect(recipe)
    else:
        form = RecipeForm(instance=recipe)
    return render(request, 'recipes/recipe_create.html', {'form': form, 'recipe': recipe})


def get_menu_list(request):
    menus = Menu.objects.prefetch_related('recipes__makes')
    paginator = Paginator(menus, 24)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'menus/menu_list.html', {'page_obj': page_obj})


def get_menu_detail(request, slug):
    menu = get_object_or_404(Menu, slug=slug)
    recipes = menu.recipes.prefetch_related('tags', 'makes')
    return render(request, 'menus/menu_detail.html', {'menu': menu, 'recipes': recipes})
