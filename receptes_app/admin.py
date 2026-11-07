from django.contrib import admin, messages
from django.db.models import Max
from django.shortcuts import redirect
from django.utils.html import format_html
from .forms import RestaurantVisitAdminForm
from .models import Tag, Tool, Recipe, Menu, Make, RestaurantVisit, Dish

# Register the Tag model
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Display the 'name' field in the admin list view
    search_fields = ('name',)  # Add a search bar for the 'name' field


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Display the 'name' field in the admin list view
    search_fields = ('name',)  # Add a search bar for the 'name' field


@admin.action(description="Delete selected")
def custom_delete_model(modeladmin, request, queryset):
    for obj in queryset:
        obj.delete()

# Register the Recipe model
@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'name', 'tags_preview')  # Display key fields
    prepopulated_fields = {"slug": ("name",)}
    list_display_links = ('image_preview', 'name')
    readonly_fields = ('image_preview',)
    list_filter = ('tags', 'tools', 'created_at')  # Add filters for tags and creation date
    search_fields = ('name', 'ingredients', 'preparation')  # Enable search by these fields
    autocomplete_fields = ('tags', 'tools')  # Enable tag autocomplete in the admin form
    actions = [custom_delete_model]  # Only include the custom action

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']  # Remove default delete
        return actions

    def image_preview(self, obj):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" style="width: 100px; height: auto;" />', obj.image.url)

    def tags_preview(self, obj):
        return ' | '.join([tag.name for tag in obj.tags.all()])
    tags_preview.short_description = "Tags"  # Admin column label

    image_preview.short_description = "Image Preview"  # Admin column label

# Register the Menu model
@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('name', 'date')  # Display key fields
    prepopulated_fields = {"slug": ("name",)}  # Automatically generate the slug from the name
    list_filter = ('date',)  # Add a filter for the date field
    search_fields = ('name', 'description')  # Enable search for name and description
    filter_horizontal = ('recipes',)  # Use a horizontal widget for selecting recipes


# Register the Make model
@admin.register(Make)
class MakeAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'recipe', 'date')  # Display key fields
    list_display_links = ('image_preview', 'recipe')
    readonly_fields = ('image_preview',)
    list_filter = ('date',)  # Add a filter for the date field
    search_fields = ('recipe__name', 'notes')  # Enable search for related recipe name and notes
    autocomplete_fields = ('recipe',)  # Enable recipe autocomplete in the admin form

    def response_add(self, request, obj, post_url_continue=None):
        # Plain "Save" goes back to the recipe page, where the cooking log is shown
        if '_continue' not in request.POST and '_addanother' not in request.POST:
            return redirect(obj.recipe)
        return super().response_add(request, obj, post_url_continue)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 100px; height: auto;" />', obj.image.url)
        if obj.recipe.image:
            return format_html('<img src="{}" style="width: 100px; height: auto;" /><br><small>FROM RECIPE</small>', obj.recipe.image.url)
        return "—"


    image_preview.short_description = "Image Preview"  # Admin column label


class DishInline(admin.TabularInline):
    model = Dish
    fields = ('order', 'name', 'notes', 'image', 'image_preview')
    readonly_fields = ('image_preview',)
    extra = 3

    def image_preview(self, obj):
        if not obj.image:
            return "—"
        return format_html('<img src="{}" style="width: 80px; height: auto;" />', obj.image.url)
    image_preview.short_description = "Preview"


@admin.register(RestaurantVisit)
class RestaurantVisitAdmin(admin.ModelAdmin):
    form = RestaurantVisitAdminForm
    list_display = ('name', 'city', 'date', 'menu_name')
    prepopulated_fields = {"slug": ("name",)}
    list_filter = ('date', 'city')
    search_fields = ('name', 'city', 'menu_name', 'notes', 'dishes__name')
    inlines = [DishInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Each bulk-uploaded photo becomes a dish, appended after the existing ones
        visit = form.instance
        photos = form.sorted_dish_photos()
        last_order = visit.dishes.aggregate(Max('order'))['order__max'] or 0
        count = visit.dishes.count()
        for i, photo in enumerate(photos, start=1):
            Dish.objects.create(visit=visit, name=f"Plat {count + i}", order=last_order + i, image=photo)
        request.bulk_dishes_added = len(photos)

    def _name_new_dishes(self, request, obj):
        added = getattr(request, 'bulk_dishes_added', 0)
        if not added:
            return None
        messages.success(request, f"S'han afegit {added} plat{'s' if added != 1 else ''}. Posa'ls nom i torna a desar.")
        return redirect('admin:receptes_app_restaurantvisit_change', obj.pk)

    def response_add(self, request, obj, post_url_continue=None):
        if response := self._name_new_dishes(request, obj):
            return response
        # Plain "Save" shows the new visit on the site
        if '_continue' not in request.POST and '_addanother' not in request.POST:
            return redirect(obj)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        return self._name_new_dishes(request, obj) or super().response_change(request, obj)
