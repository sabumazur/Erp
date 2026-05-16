from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderSequence, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "rnc", "email", "is_active", "created_at"]
    list_filter = ["is_active", "organization"]
    search_fields = ["name", "rnc", "email"]
    raw_id_fields = ["organization"]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "supplier", "organization", "status", "issue_date", "expected_date"]
    list_filter = ["status", "organization"]
    search_fields = ["number", "supplier__name"]
    raw_id_fields = ["organization", "supplier"]
    readonly_fields = ["number", "created_at", "updated_at"]


@admin.register(PurchaseOrderSequence)
class PurchaseOrderSequenceAdmin(admin.ModelAdmin):
    list_display = ["organization", "current_seq", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]
