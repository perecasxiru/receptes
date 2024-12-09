from django.views.generic import ListView, DetailView
from .models import Tag, Recipe, Menu, Make
from django.shortcuts import render
from .services import get_all_rows, get_worksheet, imgur_upload, imgur_delete
from django.core.paginator import Paginator

all_recipes, all_tags = None, None

def get_all_recipes():
    global all_recipes
    global all_tags

    if all_recipes is None:
        worksheet = get_worksheet('ReceptesApp', 'Receptes')
        all_recipes = worksheet.get_all_records()

        all_tags = set()

        for recipe in all_recipes:
            recipe['tags'] = recipe['tags'].split('|')
            recipe['tools'] = recipe['tools'].split('|')
            recipe['get_absolute_url'] = f'/recipes/{recipe["slug"]}-{recipe["pk"]}/'
            all_tags.update(recipe['tags'])
        if '' in all_tags:
            all_tags.remove('')

    return all_recipes, all_tags


def get_recipe_list(request):
    all_recipes, all_tags = get_all_recipes()

    filtered_recipes = [rec for rec in all_recipes if request.GET.get('tag') in rec['tags']] if request.GET.get('tag') is not None else all_recipes
    filtered_recipes = [rec for rec in filtered_recipes if request.GET.get('search') in rec['name']] if request.GET.get('search') is not None else filtered_recipes

    # print(filtered_recipes)

    paginator = Paginator(filtered_recipes, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'selected_tag': request.GET.get('tag'),
        'search_query': request.GET.get('search') or '',
        'tags': all_tags,
    }
    return render(request, 'recipes/recipe_list.html', context=context)

    # worksheet = get_worksheet('ReceptesApp', 'Receptes')
    # rows = []
    # for rec in Recipe.objects.all():
    #     rows.append([rec.pk, rec.name, rec.slug, rec.link, rec.ingredients, rec.preparation, rec.prep_time,
    #                           rec.created_at.strftime("%Y-%m-%d"), rec.updated_at.strftime("%Y-%m-%d"),
    #                           rec.imgur_image if rec.imgur_image else None, "|".join([t.name for t in rec.tags.all()]), "|".join([t.name for t in rec.tools.all()])])
    # worksheet.append_rows(rows)


def get_recipe_detail(request, pk, slug):
    all_recipes, all_tags = get_all_recipes()
    recipe = [rec for rec in all_recipes if rec['pk'] == pk][0]
    context = {
        'recipe': recipe,
    }
    return render(request, 'recipes/recipe_detail.html', context)

# class RecipeDetailView(DetailView):
#     model = Recipe
#     template_name = 'recipes/recipe_detail.html'  # Replace with your template path
#     context_object_name = 'recipe'


# class MenuListView(ListView):
#     model = Menu
#     template_name = 'menus/menu_list.html'  # Replace with your template path
#     context_object_name = 'menus'


# class MenuDetailView(DetailView):
#     model = Menu
#     template_name = 'menus/menu_detail.html'  # Replace with your template path
#     context_object_name = 'menu'