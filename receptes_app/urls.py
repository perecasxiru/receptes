from django.urls import path
from .views import (
    get_recipe_list, get_recipe_detail, create_recipe, edit_recipe,
    get_menu_list, get_menu_detail,
)

urlpatterns = [
    # Recipes
    path('', get_recipe_list, name='recipe_list'),
    path('recepta/<slug:slug>/', get_recipe_detail, name='recipe_detail'),
    path('recepta/<slug:slug>/editar/', edit_recipe, name='recipe_edit'),
    path('create/', create_recipe, name='recipe_create'),

    # Menus
    path('menus/', get_menu_list, name='menu_list'),
    path('menus/<slug:slug>/', get_menu_detail, name='menu_detail'),
]
