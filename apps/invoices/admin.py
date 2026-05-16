from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.core.admin import ERPHistoryAdmin
from .models import (
    Customer, CustomerDepartment, DocumentSequence, Invoice, InvoiceItem,
    NCFSequence, Payment, PaymentAllocation, PaymentTerm,
)


class CustomerDepartmentInline(admin.TabularInline):
    model   = CustomerDepartment
    extra   = 0
    fields  = ["name", "contact_name", "phone", "address", "is_active"]
    ordering = ["name"]


@admin.register(Customer)
class CustomerAdmin(ERPHistoryAdmin):
    list_display   = ["name", "id_type", "rnc_cedula", "email", "organization", "default_ncf_type"]
    list_filter    = ["organization", "id_type", "default_ncf_type"]
    search_fields  = ["name", "rnc_cedula", "email"]
    readonly_fields = ["created_at", "updated_at"]
    inlines        = [CustomerDepartmentInline]


@admin.register(CustomerDepartment)
class CustomerDepartmentAdmin(ERPHistoryAdmin):
    list_display  = ["name", "customer", "contact_name", "phone", "is_active", "organization"]
    list_filter   = ["organization", "is_active"]
    search_fields = ["name", "customer__name", "contact_name"]
    readonly_fields = ["created_at", "updated_at"]


class InvoiceItemInline(admin.TabularInline):
    model  = InvoiceItem
    extra  = 0
    fields = ["item", "description", "quantity", "unit_price", "itbis_rate",
              "line_total", "itbis_amount", "line_total_with_itbis"]
    readonly_fields = ["line_total", "itbis_amount", "line_total_with_itbis"]


@admin.register(Invoice)
class InvoiceAdmin(ERPHistoryAdmin):
    list_display   = ["display_number", "doc_type", "customer", "issue_date", "total", "status", "organization"]
    list_filter    = ["doc_type", "status", "ncf_type", "organization"]
    search_fields  = ["encf", "doc_number", "customer__name", "customer__rnc_cedula"]
    readonly_fields = [
        "encf", "doc_number", "created_at", "updated_at",
        "subtotal", "itbis_18", "itbis_16", "total",
        "dgii_status", "dgii_track_id", "xml_content",
    ]
    inlines = [InvoiceItemInline]
    fieldsets = (
        (_("Tipo"), {
            "fields": ("doc_type", "organization", "customer", "status"),
        }),
        (_("Comprobante fiscal (Factura)"), {
            "fields": ("encf", "ncf_type", "encf_modified"),
            "classes": ("collapse",),
        }),
        (_("Documento no fiscal (Cotización / Orden)"), {
            "fields": ("doc_number", "valid_until", "delivery_date", "signed_by", "consolidated_into"),
            "classes": ("collapse",),
        }),
        (_("Fechas y condiciones"), {
            "fields": ("issue_date", "due_date", "payment_condition", "currency", "exchange_rate"),
        }),
        (_("Totales"), {
            "fields": ("subtotal", "itbis_18", "itbis_16", "total"),
            "classes": ("collapse",),
        }),
        (_("Notas"), {
            "fields": ("notes", "terms"),
            "classes": ("collapse",),
        }),
        (_("DGII (Fase 2)"), {
            "fields": ("dgii_status", "dgii_track_id", "xml_content"),
            "classes": ("collapse",),
        }),
        (_("Auditoría"), {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display   = ["organization", "doc_type", "current_seq", "updated_at"]
    list_filter    = ["organization", "doc_type"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(NCFSequence)
class NCFSequenceAdmin(admin.ModelAdmin):
    list_display   = ["organization", "ncf_type", "series", "current_seq", "max_seq", "is_active"]
    list_filter    = ["organization", "ncf_type", "is_active"]
    readonly_fields = ["created_at", "updated_at"]


class PaymentAllocationInline(admin.TabularInline):
    model   = PaymentAllocation
    extra   = 0
    fields  = ["invoice", "amount"]
    readonly_fields = ["created_at"]
    autocomplete_fields = ["invoice"]


@admin.register(Payment)
class PaymentAdmin(ERPHistoryAdmin):
    list_display    = ["customer", "amount", "date", "method", "reference", "organization"]
    list_filter     = ["method", "organization", "date"]
    search_fields   = ["customer__name", "reference"]
    readonly_fields = ["created_at", "updated_at"]
    inlines         = [PaymentAllocationInline]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display  = ["payment", "invoice", "amount", "created_at"]
    search_fields = ["payment__reference", "invoice__encf", "invoice__doc_number"]
    readonly_fields = ["created_at"]


@admin.register(PaymentTerm)
class PaymentTermAdmin(admin.ModelAdmin):
    list_display   = ["name", "days_due", "description"]
    search_fields  = ["name"]
    ordering       = ["days_due"]
