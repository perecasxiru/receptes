from django.urls import path
from .views import (
    get_recipe_list, get_recipe_detail,
    #MenuListView, MenuDetailView,
)

urlpatterns = [
    # Recipes
    path('recipes/', get_recipe_list, name='recipe_list'),
    path('recipes/<slug:slug>-<int:pk>/', get_recipe_detail, name='recipe_detail'),

    # Menus
    #path('menus/', MenuListView.as_view(), name='menu_list'),
    #path('menus/<int:pk>/', MenuDetailView.as_view(), name='menu_detail'),
]