from django.urls import path
from .views import (
    get_recipe_list, get_recipe_detail, create_recipe
)

urlpatterns = [
    # Recipes
    path('', get_recipe_list, name='recipe_list'),
    # path('reset/', reset_all_recipes, name='reset_all_recipes'),
    path('recepta/<slug:slug>/', get_recipe_detail, name='recipe_detail'),
    path('create/', create_recipe, name='recipe_create'),

    # Menus
    #path('menus/', MenuListView.as_view(), name='menu_list'),
    #path('menus/<int:pk>/', MenuDetailView.as_view(), name='menu_detail'),
]