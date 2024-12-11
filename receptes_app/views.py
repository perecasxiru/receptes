from django.views.generic import ListView, DetailView
from .models import Tag, Recipe, Menu, Make, Tool
from django.shortcuts import render, redirect
from .services import get_all_rows, get_worksheet, imgur_upload, imgur_delete
from django.core.paginator import Paginator
from django.core.files.storage import default_storage
from datetime import datetime
from tqdm.auto import tqdm
from django.conf import settings
from django.http import HttpResponseForbidden
from .forms import RecipeForm


all_recipes, all_tags = None, None


def reset_all_recipes(request):
    global all_recipes
    global all_tags
    all_recipes = None
    all_tags = None

    return redirect('recipe_list')


def update_database(request):
    if not settings.DEBUG:
        return HttpResponseForbidden("Only in DEBUG mode")

    recipes_worksheet = get_worksheet('ReceptesApp', 'Receptes')
    _all_recipes = recipes_worksheet.get_all_records()

    tags_worksheet = get_worksheet('ReceptesApp', 'Tags')
    _all_tags = tags_worksheet.get_all_records()

    tools_worksheet = get_worksheet('ReceptesApp', 'Tools')
    _all_tools = tools_worksheet.get_all_records()

    for rec in _all_recipes:
        for _t in _all_tags:
            rec['tags'] = rec['tags'].replace(_t['name'], str(_t['pk']))
        try:
            rec['tags'] = list(map(int, rec['tags'].split('|')))
        except ValueError:
            rec['tags'] = []

        for _t in _all_tools:
            rec['tools'] = rec['tools'].replace(_t['name'], str(_t['pk']))
        try:
            rec['tools'] = list(map(int, rec['tools'].split('|')))
        except ValueError:
            rec['tools'] = []

        rec['imgur_image'] = rec['image']
        rec['image'] = ''
        rec['prep_time'] = int(rec['prep_time']) if rec['prep_time'] else None
        rec['prep_time'] = int(rec['prep_time']) if rec['prep_time'] else None
        rec['created_at'] = datetime.strptime(rec['created_at'], '%Y-%m-%d').date()
        rec['updated_at'] = datetime.strptime(rec['updated_at'], '%Y-%m-%d').date()

        pk = rec.pop('pk')
        tags_pks = rec.pop('tags', [])
        tools_pks = rec.pop('tools', [])

        try:
            created = Recipe.objects.get(pk=pk)  # Fetch existing object
            for key, value in rec.items():
                setattr(created, key, value)  # Update fields
        except Recipe.DoesNotExist:
            created = Recipe(pk=pk, **rec)  # Create new object with the given pk
        created.save(skip_action=True)

        if tags_pks:
            created.tags.set(tags_pks)  # Update Many-to-Many relationships
        else:
            created.tags.clear()  # Clear all tags if no tags are provided

        if tools_pks:
            created.tools.set(tools_pks)
        else:
            created.tools.clear()
    return redirect('recipe_list')



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
            recipe['get_absolute_url'] = f'/recepta/{recipe["slug"]}-{recipe["pk"]}/'
            all_tags.update(recipe['tags'])
        if '' in all_tags:
            all_tags.remove('')

    return all_recipes, sorted(list(all_tags))


def get_recipe_list(request):
    all_recipes, all_tags = get_all_recipes()

    filtered_recipes = [rec for rec in all_recipes if request.GET.get('tag') in rec['tags']] if request.GET.get('tag') is not None else all_recipes
    filtered_recipes = [rec for rec in filtered_recipes if request.GET.get('search').lower() in rec['name'].lower()] if request.GET.get('search') is not None else filtered_recipes

    # print(filtered_recipes)

    paginator = Paginator(filtered_recipes, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'selected_tag': request.GET.get('tag'),
        'search_query': request.GET.get('search') or '',
        'tags': all_tags,
        'is_debug': settings.DEBUG,
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


def create_recipe(request):
    if request.method == "POST":
        form = RecipeForm(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data['name']
            slug = form.cleaned_data['slug']
            link = form.cleaned_data['link']
            ingredients = form.cleaned_data['ingredients']
            preparation = form.cleaned_data['preparation']
            prep_time = form.cleaned_data['prep_time']
            image = form.cleaned_data.get('image')
            tags = form.cleaned_data['tags']
            tools = form.cleaned_data['tools']

            # Save to the database
            recipe = Recipe(
                name=name,
                slug=slug,
                link=link,
                ingredients=ingredients,
                preparation=preparation,
                prep_time=prep_time,
                image=image,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            recipe.save(to_db=False, cust_tags=tags, cust_tools=tools)

            return redirect('recipe_list')
    else:
        form = RecipeForm()
    return render(request, 'recipes/recipe_create.html', {'form': form})


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