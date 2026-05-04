from django.urls import path
from .views import (
    # Customers
    CustomerListView,
    CustomerDetailView,
    CustomerUpdateView,
    CustomerDeleteView,
    CustomerDepartmentCreateView,
    CustomerDepartmentUpdateView,
    CustomerDepartmentToggleView,
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
    InvoicePrintView,
    # Quotations
    QuotationListView,
    QuotationCreateView,
    QuotationDetailView,
    QuotationUpdateView,
    QuotationConfirmView,
    QuotationSendView,
    QuotationAcceptView,
    QuotationRejectView,
    QuotationConvertView,
    QuotationDeleteView,
    QuotationPrintView,
    # Sale Orders
    SaleOrderListView,
    SaleOrderCreateView,
    SaleOrderDetailView,
    SaleOrderUpdateView,
    SaleOrderConfirmView,
    SaleOrderDeliverView,
    SaleOrderCancelView,
    SaleOrderDeleteView,
    SaleOrderConsolidateView,
    SaleOrderCloneView,
    SaleOrderPrintView,
    # Payments
    PaymentListView,
    PaymentCreateView,
    PaymentDetailView,
    PaymentDeleteView,
    OutstandingInvoicesView,
    # HTMX
    InvoiceItemRowView,
    RNCLookupView,
    CustomerDepartmentsView,
    # NCF sequences
    NCFSequenceListView,
    NCFSequenceUpdateView,
    # Reports
    ReportIndexView,
    Report607View,
    Report608View,
    ReportAgingView,
    ReportStatementView,
    ReportSalesByPeriodView,
    ReportCollectionsView,
)

app_name = "invoices"

urlpatterns = [
    # ── Customers ─────────────────────────────────────────────────────────────
    path("invoices/customers/",                    CustomerListView.as_view(),   name="customer_list"),
    path("invoices/customers/<uuid:pk>/",          CustomerDetailView.as_view(), name="customer_detail"),
    path("invoices/customers/<uuid:pk>/edit/",     CustomerUpdateView.as_view(), name="customer_edit"),
    path("invoices/customers/<uuid:pk>/delete/",   CustomerDeleteView.as_view(), name="customer_delete"),

    # Customer departments
    path("invoices/customers/<uuid:customer_pk>/departments/create/",
         CustomerDepartmentCreateView.as_view(), name="department_create"),
    path("invoices/customers/<uuid:customer_pk>/departments/<uuid:pk>/edit/",
         CustomerDepartmentUpdateView.as_view(), name="department_edit"),
    path("invoices/customers/<uuid:customer_pk>/departments/<uuid:pk>/toggle/",
         CustomerDepartmentToggleView.as_view(), name="department_toggle"),

    # ── Invoices ──────────────────────────────────────────────────────────────
    path("invoices/",                              InvoiceListView.as_view(),    name="invoice_list"),
    path("invoices/create/",                       InvoiceCreateView.as_view(),  name="invoice_create"),
    path("invoices/<uuid:pk>/",                    InvoiceDetailView.as_view(),  name="invoice_detail"),
    path("invoices/<uuid:pk>/edit/",               InvoiceUpdateView.as_view(),  name="invoice_edit"),

    # Invoice status transitions
    path("invoices/<uuid:pk>/confirm/",            InvoiceConfirmView.as_view(), name="invoice_confirm"),
    path("invoices/<uuid:pk>/send/",               InvoiceSendView.as_view(),    name="invoice_send"),
    path("invoices/<uuid:pk>/pay/",                InvoicePayView.as_view(),     name="invoice_pay"),
    path("invoices/<uuid:pk>/cancel/",             InvoiceCancelView.as_view(),  name="invoice_cancel"),
    path("invoices/<uuid:pk>/delete/",             InvoiceDeleteView.as_view(),  name="invoice_delete"),

    # Credit / debit notes
    path("invoices/<uuid:pk>/credit-note/",        CreditNoteCreateView.as_view(), name="credit_note_create"),

    # PDF / Print
    path("invoices/<uuid:pk>/pdf/",                InvoicePDFView.as_view(),     name="invoice_pdf"),
    path("invoices/<uuid:pk>/print/",              InvoicePrintView.as_view(),   name="invoice_print"),

    # ── Quotations ────────────────────────────────────────────────────────────
    path("quotations/",                            QuotationListView.as_view(),   name="quotation_list"),
    path("quotations/create/",                     QuotationCreateView.as_view(), name="quotation_create"),
    path("quotations/<uuid:pk>/",                  QuotationDetailView.as_view(), name="quotation_detail"),
    path("quotations/<uuid:pk>/edit/",             QuotationUpdateView.as_view(), name="quotation_edit"),

    # Quotation transitions
    path("quotations/<uuid:pk>/confirm/",          QuotationConfirmView.as_view(), name="quotation_confirm"),
    path("quotations/<uuid:pk>/send/",             QuotationSendView.as_view(),    name="quotation_send"),
    path("quotations/<uuid:pk>/accept/",           QuotationAcceptView.as_view(),  name="quotation_accept"),
    path("quotations/<uuid:pk>/reject/",           QuotationRejectView.as_view(),  name="quotation_reject"),
    path("quotations/<uuid:pk>/convert/",          QuotationConvertView.as_view(), name="quotation_convert"),
    path("quotations/<uuid:pk>/delete/",           QuotationDeleteView.as_view(),  name="quotation_delete"),
    path("quotations/<uuid:pk>/print/",            QuotationPrintView.as_view(),   name="quotation_print"),

    # ── Sale Orders ───────────────────────────────────────────────────────────
    path("sale-orders/",                           SaleOrderListView.as_view(),    name="sale_order_list"),
    path("sale-orders/create/",                    SaleOrderCreateView.as_view(),  name="sale_order_create"),
    path("sale-orders/consolidate/",               SaleOrderConsolidateView.as_view(), name="sale_order_consolidate"),
    path("sale-orders/<uuid:pk>/",                 SaleOrderDetailView.as_view(),  name="sale_order_detail"),
    path("sale-orders/<uuid:pk>/edit/",            SaleOrderUpdateView.as_view(),  name="sale_order_edit"),

    # Sale Order transitions
    path("sale-orders/<uuid:pk>/confirm/",         SaleOrderConfirmView.as_view(), name="sale_order_confirm"),
    path("sale-orders/<uuid:pk>/deliver/",         SaleOrderDeliverView.as_view(), name="sale_order_deliver"),
    path("sale-orders/<uuid:pk>/cancel/",          SaleOrderCancelView.as_view(),  name="sale_order_cancel"),
    path("sale-orders/<uuid:pk>/delete/",          SaleOrderDeleteView.as_view(),  name="sale_order_delete"),
    path("sale-orders/<uuid:pk>/clone/",           SaleOrderCloneView.as_view(),   name="sale_order_clone"),
    path("sale-orders/<uuid:pk>/print/",           SaleOrderPrintView.as_view(),   name="sale_order_print"),

    # ── Payments ─────────────────────────────────────────────────────────────────
    path("payments/",                              PaymentListView.as_view(),      name="payment_list"),
    path("payments/create/",                       PaymentCreateView.as_view(),    name="payment_create"),
    path("payments/<uuid:pk>/",                    PaymentDetailView.as_view(),    name="payment_detail"),
    path("payments/<uuid:pk>/delete/",             PaymentDeleteView.as_view(),    name="payment_delete"),

    # ── HTMX helpers ──────────────────────────────────────────────────────────
    path("invoices/items/row/",                    InvoiceItemRowView.as_view(),   name="item_row"),
    path("invoices/rnc-lookup/",                   RNCLookupView.as_view(),        name="rnc_lookup"),
    path("invoices/customers/departments/",        CustomerDepartmentsView.as_view(), name="departments_for_customer"),
    path("payments/outstanding-invoices/",         OutstandingInvoicesView.as_view(), name="payment_outstanding_invoices"),

    # ── NCF sequences ─────────────────────────────────────────────────────────
    path("invoices/ncf/",                          NCFSequenceListView.as_view(),  name="ncf_sequences"),
    path("invoices/ncf/<int:pk>/edit/",            NCFSequenceUpdateView.as_view(), name="ncf_sequence_edit"),

    # ── DGII reports ──────────────────────────────────────────────────────────
    path("invoices/reports/",                      ReportIndexView.as_view(),           name="reports"),
    path("invoices/reports/607/",                  Report607View.as_view(),             name="report_607"),
    path("invoices/reports/608/",                  Report608View.as_view(),             name="report_608"),

    # ── Management reports ────────────────────────────────────────────────────
    path("invoices/reports/aging/",                ReportAgingView.as_view(),           name="report_aging"),
    path("invoices/reports/statement/",            ReportStatementView.as_view(),       name="report_statement"),
    path("invoices/reports/sales-by-period/",      ReportSalesByPeriodView.as_view(),   name="report_sales_period"),
    path("invoices/reports/collections/",          ReportCollectionsView.as_view(),     name="report_collections"),
]
