from django.contrib import admin
from .models import Category, Item, ItemImage, ItemSuggestion

class ItemImageInline(admin.TabularInline):
    model = ItemImage
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'steward', 'status', 'condition', 'created_at')
    list_filter = ('status', 'condition', 'category')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ItemImageInline]
    readonly_fields = ('total_bookings',)

@admin.register(ItemSuggestion)
class ItemSuggestionAdmin(admin.ModelAdmin):
    list_display = ('name', 'suggested_by', 'votes', 'status', 'created_at')
    list_filter = ('status', 'category')
    search_fields = ('name', 'description')