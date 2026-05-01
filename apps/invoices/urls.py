from django.urls import path
from .views import (
    # Customers
    CustomerListView,
    CustomerUpdateView,
    CustomerDeleteView,
    # Invoices
    InvoiceListView,
    InvoiceCreateView,
    InvoiceDetailView,
    InvoiceUpdateView,
    InvoiceConfirmView,
    InvoiceSendView,
    InvoicePayView,
    InvoiceCancelView,
    InvoiceDeleteView,
    CreditNoteCreateView,
    InvoicePDFView,
    # HTMX
    InvoiceItemRowView,
    RNCLookupView,
    # NCF sequences
    NCFSequenceListView,
    NCFSequenceUpdateView,
    # Reports
    ReportIndexView,
    Report607View,
    Report608View,
)

app_name = "invoices"

urlpatterns = [
    # ── Customers ─────────────────────────────────────────────────────────────
    path("invoices/customers/", CustomerListView.as_view(), name="customer_list"),
    path("invoices/customers/<uuid:pk>/edit/", CustomerUpdateView.as_view(), name="customer_edit"),
    path("invoices/customers/<uuid:pk>/delete/", CustomerDeleteView.as_view(), name="customer_delete"),

    # ── Invoices ──────────────────────────────────────────────────────────────
    path("invoices/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/create/", InvoiceCreateView.as_view(), name="invoice_create"),
    path("invoices/<uuid:pk>/", InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<uuid:pk>/edit/", InvoiceUpdateView.as_view(), name="invoice_edit"),

    # Status transitions
    path("invoices/<uuid:pk>/confirm/", InvoiceConfirmView.as_view(), name="invoice_confirm"),
    path("invoices/<uuid:pk>/send/",    InvoiceSendView.as_view(),    name="invoice_send"),
    path("invoices/<uuid:pk>/pay/",     InvoicePayView.as_view(),     name="invoice_pay"),
    path("invoices/<uuid:pk>/cancel/",  InvoiceCancelView.as_view(),  name="invoice_cancel"),
    path("invoices/<uuid:pk>/delete/",  InvoiceDeleteView.as_view(),  name="invoice_delete"),

    # Credit / debit notes
    path("invoices/<uuid:pk>/credit-note/", CreditNoteCreateView.as_view(), name="credit_note_create"),

    # PDF
    path("invoices/<uuid:pk>/pdf/", InvoicePDFView.as_view(), name="invoice_pdf"),

    # ── HTMX helpers ──────────────────────────────────────────────────────────
    path("invoices/items/row/",  InvoiceItemRowView.as_view(), name="item_row"),
    path("invoices/rnc-lookup/", RNCLookupView.as_view(),      name="rnc_lookup"),

    # ── NCF sequences ─────────────────────────────────────────────────────────
    path("invoices/ncf/", NCFSequenceListView.as_view(), name="ncf_sequences"),
    path("invoices/ncf/<int:pk>/edit/", NCFSequenceUpdateView.as_view(), name="ncf_sequence_edit"),

    # ── DGII reports ──────────────────────────────────────────────────────────
    path("invoices/reports/", ReportIndexView.as_view(), name="reports"),
    path("invoices/reports/607/", Report607View.as_view(), name="report_607"),
    path("invoices/reports/608/", Report608View.as_view(), name="report_608"),
]
