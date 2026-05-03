from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Item, ItemCodeSequence


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display   = ["__str__", "item_type", "unit", "unit_price", "cost_price",
                      "itbis_rate", "is_active", "organization"]
    list_filter    = ["organization", "item_type", "itbis_rate", "unit", "is_active"]
    search_fields  = ["name", "code"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("General"), {
            "fields": ("organization", "code", "name", "item_type"),
        }),
        (_("Precio y unidad"), {
            "fields": ("unit", "unit_price", "cost_price", "itbis_rate"),
        }),
        (_("Estado"), {
            "fields": ("is_active", "notes"),
        }),
        (_("Auditoría"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(ItemCodeSequence)
class ItemCodeSequenceAdmin(admin.ModelAdmin):
    list_display  = ["organization", "prefix", "current_seq", "next_code", "updated_at"]
    readonly_fields = ["current_seq", "updated_at", "next_code"]
    fields        = ["organization", "prefix", "current_seq", "next_code", "updated_at"]

    def next_code(self, obj):
        """Preview of the next code that would be generated."""
        return f"{obj.prefix}-{obj.current_seq + 1:04d}"
    next_code.short_description = _("próximo código")
