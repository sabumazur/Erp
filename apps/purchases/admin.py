from django.contrib import admin

from .models import (
    Supplier,
    PurchaseDocument,
    PurchaseDocumentItem,
    SupplierPayment,
    SupplierPaymentAllocation,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "id_type", "rnc_cedula", "organization", "is_active"]
    list_filter = ["is_active", "id_type", "organization"]
    search_fields = ["name", "rnc_cedula"]


class PurchaseDocumentItemInline(admin.TabularInline):
    model = PurchaseDocumentItem
    extra = 0


@admin.register(PurchaseDocument)
class PurchaseDocumentAdmin(admin.ModelAdmin):
    list_display = ["number", "doc_type", "supplier", "status", "total", "organization"]
    list_filter = ["doc_type", "status", "organization"]
    search_fields = ["number", "supplier_ncf"]
    inlines = [PurchaseDocumentItemInline]


@admin.register(SupplierPayment)
class SupplierPaymentAdmin(admin.ModelAdmin):
    list_display = ["supplier", "amount", "date", "method", "organization"]
    list_filter = ["method", "organization"]


@admin.register(SupplierPaymentAllocation)
class SupplierPaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ["payment", "supplier_invoice", "amount"]
