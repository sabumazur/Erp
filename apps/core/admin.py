from django.contrib import admin
from .models import Module


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "icon", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]
