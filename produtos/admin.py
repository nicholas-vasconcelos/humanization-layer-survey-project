from django.contrib import admin
from .models import Catalogue, Product, SessionResponse


@admin.register(Catalogue)
class CatalogueAdmin(admin.ModelAdmin):
    list_display  = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'catalogue', 'price', 'featured']
    list_filter   = ['catalogue', 'featured']
    search_fields = ['name']


@admin.register(SessionResponse)
class SessionResponseAdmin(admin.ModelAdmin):
    list_display  = ['session_id', 'interest_selected', 'preferred_overall', 'timestamp']
    list_filter   = ['preferred_overall', 'ai_familiarity', 'uses_ai_shopping']
    readonly_fields = [
        'session_id', 'interest_selected', 'products_selected',
        'robotic_output', 'humanized_output',
        'preferred_overall', 'preferred_trust',
        'preferred_purchase', 'preferred_understood',
        'uses_ai_shopping', 'ai_familiarity', 'timestamp',
    ]