from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Module


class ERPHistoryAdmin(SimpleHistoryAdmin):
    """Base admin for all SabSys models — includes history tab automatically."""
    history_list_display = ["history_user", "history_date", "history_change_reason"]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "icon", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]
