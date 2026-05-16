from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display   = ["__str__", "rnc", "phone", "email", "status", "organization"]
    list_filter    = ["organization", "status"]
    search_fields  = ["name", "rnc", "email"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (_("General"), {
            "fields": ("organization", "name", "status"),
        }),
        (_("Contacto"), {
            "fields": ("rnc", "phone", "email"),
        }),
        (_("Auditoría"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
