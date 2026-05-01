from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Customer, Invoice, InvoiceItem, NCFSequence, Payment


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display  = ["name", "id_type", "rnc_cedula", "email", "organization", "default_ncf_type"]
    list_filter   = ["organization", "id_type", "default_ncf_type"]
    search_fields = ["name", "rnc_cedula", "email"]
    readonly_fields = ["created_at", "updated_at"]


class InvoiceItemInline(admin.TabularInline):
    model  = InvoiceItem
    extra  = 0
    fields = ["description", "quantity", "unit_price", "itbis_rate",
              "line_total", "itbis_amount", "line_total_with_itbis"]
    readonly_fields = ["line_total", "itbis_amount", "line_total_with_itbis"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display   = ["encf", "customer", "ncf_type", "issue_date", "total", "status", "organization"]
    list_filter    = ["status", "ncf_type", "organization", "currency"]
    search_fields  = ["encf", "customer__name", "customer__rnc_cedula"]
    readonly_fields = [
        "encf", "created_at", "updated_at",
        "subtotal", "itbis_18", "itbis_16", "total",
        "dgii_status", "dgii_track_id", "xml_content",
    ]
    inlines = [InvoiceItemInline]
    fieldsets = (
        (_("Comprobante"), {
            "fields": ("organization", "customer", "encf", "ncf_type", "encf_modified", "status"),
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


@admin.register(NCFSequence)
class NCFSequenceAdmin(admin.ModelAdmin):
    list_display  = ["organization", "ncf_type", "series", "current_seq", "max_seq", "is_active"]
    list_filter   = ["organization", "ncf_type", "is_active"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display  = ["invoice", "amount", "date", "method", "reference", "organization"]
    list_filter   = ["method", "organization"]
    search_fields = ["invoice__encf", "reference"]
    readonly_fields = ["created_at", "updated_at"]
