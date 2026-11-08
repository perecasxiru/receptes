from .models import Tag, Recipe, Menu, RestaurantVisit
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.contrib import messages
from django.db import transaction
from .forms import DishFormSet, MenuForm, RecipeForm, VisitForm
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


@staff_member_required
def edit_menu(request, slug=None):
    menu = get_object_or_404(Menu, slug=slug) if slug else None
    form = MenuForm(request.POST or None, instance=menu)
    if request.method == "POST" and form.is_valid():
        return redirect(form.save())
    return render(request, 'menus/menu_form.html', {'form': form, 'menu': menu})


def get_menu_detail(request, slug):
    menu = get_object_or_404(Menu, slug=slug)
    recipes = menu.recipes.prefetch_related('tags', 'makes')
    return render(request, 'menus/menu_detail.html', {'menu': menu, 'recipes': recipes})


def get_visit_list(request):
    visits = RestaurantVisit.objects.prefetch_related('dishes')
    paginator = Paginator(visits, 24)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'restaurants/visit_list.html', {'page_obj': page_obj})


def get_visit_detail(request, slug):
    visit = get_object_or_404(RestaurantVisit, slug=slug)
    return render(request, 'restaurants/visit_detail.html', {'visit': visit, 'dishes': visit.dishes.all()})


@staff_member_required
def edit_visit(request, slug=None):
    visit = get_object_or_404(RestaurantVisit, slug=slug) if slug else None
    post = (request.POST, request.FILES) if request.method == "POST" else ()
    form = VisitForm(*post, instance=visit)
    # Dishes are edited once the visit exists; a new visit starts from its photos
    formset = None
    if visit:
        # The blank row for a dish without a photo goes after the last one
        next_order = (visit.dishes.aggregate(Max('order'))['order__max'] or 0) + 1
        formset = DishFormSet(*post, instance=visit, prefix='dishes', initial=[{'order': next_order}])
    if post and form.is_valid() and (formset is None or formset.is_valid()):
        with transaction.atomic():
            visit = form.save()
            if formset is not None:
                formset.save()
            added = visit.add_dish_photos(form.sorted_dish_photos())
        if added:
            # Back to the form so the new "Plat N" dishes can be named
            messages.success(request, f"S'han afegit {added} plat{'s' if added != 1 else ''}. Posa'ls nom i desa.")
            return redirect('visit_edit', visit.slug)
        return redirect(visit)
    return render(request, 'restaurants/visit_form.html', {'form': form, 'formset': formset, 'visit': visit})
