from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import DocumentSequence, Module


class ERPHistoryAdmin(SimpleHistoryAdmin):
    """Base admin for all SabSys models — includes history tab automatically."""
    history_list_display = ["history_user", "history_date", "history_change_reason"]


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ["organization", "doc_type", "prefix", "current_seq", "padding", "include_year", "updated_at"]
    list_filter = ["doc_type", "include_year"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "icon", "is_active"]
    list_editable = ["is_active"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "slug"]
