from django.contrib import admin
from .models import Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "rnc", "phone", "email", "status", "created_at"]
    list_filter = ["status", "organization"]
    search_fields = ["name", "rnc", "email"]
    raw_id_fields = ["organization"]
    readonly_fields = ["id", "created_at", "updated_at", "deleted_at"]
