from django.contrib import admin

from .models import PurchaseOrder, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "tax_id", "email", "phone", "created_at"]
    list_filter = ["organization"]
    search_fields = ["name", "tax_id", "email"]
    raw_id_fields = ["organization"]
    readonly_fields = ["id", "created_at", "updated_at", "deleted_at"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "organization",
        "supplier",
        "status",
        "issue_date",
        "expected_date",
        "created_at",
    ]
    list_filter = ["status", "organization"]
    search_fields = ["number", "supplier__name"]
    raw_id_fields = ["organization", "supplier"]
    readonly_fields = ["id", "number", "created_at", "updated_at", "deleted_at"]
