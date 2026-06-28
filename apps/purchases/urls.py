from django.urls import path
from .views import (
    # Suppliers
    SupplierListView,
    SupplierCreateView,
    SupplierDetailView,
    SupplierUpdateView,
    SupplierDeleteView,
    # Purchase Orders
    PurchaseOrderListView,
    PurchaseOrderCreateView,
    PurchaseOrderDetailView,
    PurchaseOrderUpdateView,
    PurchaseOrderConfirmView,
    PurchaseOrderReceiveView,
    PurchaseOrderCancelView,
    PurchaseOrderDeleteView,
    PurchaseOrderCloneView,
    PurchaseOrderPrintView,
    PurchaseOrderEmailView,
    # Supplier Invoices
    SupplierInvoiceListView,
    SupplierInvoiceCreateView,
    SupplierInvoiceDetailView,
    SupplierInvoiceUpdateView,
    SupplierInvoiceConfirmView,
    SupplierInvoiceCancelView,
    SupplierInvoiceReopenView,
    SupplierInvoiceDeleteView,
    SupplierInvoiceCloneView,
    # Payments
    SupplierPaymentListView,
    SupplierPaymentCreateView,
    SupplierPaymentDetailView,
    SupplierPaymentDeleteView,
    OutstandingSupplierInvoicesView,
    # HTMX
    PurchaseItemQuickCreateView,
    SupplierSearchView,
    SupplierQuickCreateView,
    PurchaseItemSearchView,
    # Reports
    Report606View,
    ReportPurchasesIndexView,
    ReportAPAgingView,
    ReportSupplierStatementView,
    ReportSpendByPeriodView,
    ReportPurchasesBySupplierView,
    ReportSupplierPaymentsView,
    ReportITBISCreditsView,
)

app_name = "purchases"

urlpatterns = [
    # ── Suppliers ──────────────────────────────────────────────────────────────
    path("purchases/suppliers/",                  SupplierListView.as_view(),   name="supplier_list"),
    path("purchases/suppliers/create/",           SupplierCreateView.as_view(), name="supplier_create"),
    path("purchases/suppliers/<uuid:pk>/",        SupplierDetailView.as_view(), name="supplier_detail"),
    path("purchases/suppliers/<uuid:pk>/edit/",   SupplierUpdateView.as_view(), name="supplier_edit"),
    path("purchases/suppliers/<uuid:pk>/delete/", SupplierDeleteView.as_view(), name="supplier_delete"),

    # ── Purchase Orders ────────────────────────────────────────────────────────
    path("purchases/purchase-orders/",                   PurchaseOrderListView.as_view(),    name="po_list"),
    path("purchases/purchase-orders/create/",            PurchaseOrderCreateView.as_view(),  name="po_create"),
    path("purchases/purchase-orders/<uuid:pk>/",         PurchaseOrderDetailView.as_view(),  name="po_detail"),
    path("purchases/purchase-orders/<uuid:pk>/edit/",    PurchaseOrderUpdateView.as_view(),  name="po_edit"),
    path("purchases/purchase-orders/<uuid:pk>/confirm/", PurchaseOrderConfirmView.as_view(), name="po_confirm"),
    path("purchases/purchase-orders/<uuid:pk>/receive/", PurchaseOrderReceiveView.as_view(), name="po_receive"),
    path("purchases/purchase-orders/<uuid:pk>/cancel/",  PurchaseOrderCancelView.as_view(),  name="po_cancel"),
    path("purchases/purchase-orders/<uuid:pk>/delete/",  PurchaseOrderDeleteView.as_view(),  name="po_delete"),
    path("purchases/purchase-orders/<uuid:pk>/clone/",   PurchaseOrderCloneView.as_view(),   name="po_clone"),
    path("purchases/purchase-orders/<uuid:pk>/print/",   PurchaseOrderPrintView.as_view(),   name="po_print"),
    path("purchases/purchase-orders/<uuid:pk>/email/",   PurchaseOrderEmailView.as_view(),   name="po_email"),

    # ── Supplier Invoices ──────────────────────────────────────────────────────
    path("purchases/supplier-invoices/",                     SupplierInvoiceListView.as_view(),    name="supplier_invoice_list"),
    path("purchases/supplier-invoices/create/",              SupplierInvoiceCreateView.as_view(),  name="supplier_invoice_create"),
    path("purchases/supplier-invoices/<uuid:pk>/",           SupplierInvoiceDetailView.as_view(),  name="supplier_invoice_detail"),
    path("purchases/supplier-invoices/<uuid:pk>/edit/",      SupplierInvoiceUpdateView.as_view(),  name="supplier_invoice_edit"),
    path("purchases/supplier-invoices/<uuid:pk>/confirm/",   SupplierInvoiceConfirmView.as_view(), name="supplier_invoice_confirm"),
    path("purchases/supplier-invoices/<uuid:pk>/cancel/",    SupplierInvoiceCancelView.as_view(),  name="supplier_invoice_cancel"),
    path("purchases/supplier-invoices/<uuid:pk>/reopen/",    SupplierInvoiceReopenView.as_view(),  name="supplier_invoice_reopen"),
    path("purchases/supplier-invoices/<uuid:pk>/delete/",    SupplierInvoiceDeleteView.as_view(),  name="supplier_invoice_delete"),
    path("purchases/supplier-invoices/<uuid:pk>/clone/",     SupplierInvoiceCloneView.as_view(),   name="supplier_invoice_clone"),

    # ── Supplier Payments ──────────────────────────────────────────────────────
    path("purchases/payments/",                    SupplierPaymentListView.as_view(),    name="supplier_payment_list"),
    path("purchases/payments/create/",             SupplierPaymentCreateView.as_view(),  name="supplier_payment_create"),
    path("purchases/payments/<uuid:pk>/",          SupplierPaymentDetailView.as_view(),  name="supplier_payment_detail"),
    path("purchases/payments/<uuid:pk>/delete/",   SupplierPaymentDeleteView.as_view(),  name="supplier_payment_delete"),
    path("purchases/payments/outstanding-invoices/", OutstandingSupplierInvoicesView.as_view(), name="outstanding_supplier_invoices"),

    # ── HTMX ──────────────────────────────────────────────────────────────────
    path("purchases/htmx/suppliers/search/",      SupplierSearchView.as_view(),      name="supplier_search"),
    path("purchases/htmx/suppliers/create/",      SupplierQuickCreateView.as_view(), name="supplier_quick_create"),
    path("purchases/htmx/items/search/",          PurchaseItemSearchView.as_view(),  name="purchase_item_search"),
    path("purchases/htmx/items/create/",          PurchaseItemQuickCreateView.as_view(), name="item_quick_create"),

    # ── Reports ────────────────────────────────────────────────────────────────
    path("purchases/reports/",                    ReportPurchasesIndexView.as_view(), name="reports"),
    path("purchases/reports/606/",                Report606View.as_view(),             name="report_606"),
    path("purchases/reports/aging/",              ReportAPAgingView.as_view(),         name="report_aging"),
    path("purchases/reports/statement/",          ReportSupplierStatementView.as_view(), name="report_statement"),
    path("purchases/reports/spend-period/",       ReportSpendByPeriodView.as_view(),   name="report_spend_period"),
    path("purchases/reports/by-supplier/",        ReportPurchasesBySupplierView.as_view(), name="report_by_supplier"),
    path("purchases/reports/payments/",           ReportSupplierPaymentsView.as_view(), name="report_payments"),
    path("purchases/reports/itbis/",              ReportITBISCreditsView.as_view(),    name="report_itbis"),
]
