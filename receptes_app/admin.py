from django.contrib import admin
from django.utils.html import format_html
from .models import Tag, Tool, Recipe, Menu, Make


# Register the Tag model
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Display the 'name' field in the admin list view
    search_fields = ('name',)  # Add a search bar for the 'name' field


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Display the 'name' field in the admin list view
    search_fields = ('name',)  # Add a search bar for the 'name' field


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

    def image_preview(self, obj):
        if obj.image:
            img = obj.image.url
        else:
            img = "https://via.placeholder.com/640x360"
        return format_html('<img src="{}" style="width: 100px; height: auto;" />', img)

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

    def image_preview(self, obj):
        if obj.image:
            img = obj.image.url
        elif obj.recipe.image:
            img = obj.recipe.image.url
        else:
            img = "https://via.placeholder.com/640x360"
        return format_html('<img src="{}" style="width: 100px; height: auto;" /><br><small>FROM RECIPE</small>', img)


    image_preview.short_description = "Image Preview"  # Admin column label