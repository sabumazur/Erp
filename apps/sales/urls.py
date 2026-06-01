from django.urls import path
from .views import (
    # Customers
    CustomerListView,
    CustomerDetailView,
    CustomerCreateView,
    CustomerUpdateView,
    CustomerDeleteView,
    CustomerDepartmentCreateView,
    CustomerDepartmentTableView,
    CustomerDepartmentUpdateView,
    CustomerDepartmentToggleView,
    CustomerDepartmentDeleteView,
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
    QuotationEmailView,
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
    SaleOrderEmailView,
    SaleOrderConsolidateView,
    SaleOrderCloneView,
    SaleOrderPrintView,
    # Payments
    PaymentListView,
    PaymentCreateView,
    PaymentDetailView,
    PaymentDeleteView,
    OutstandingInvoicesView,
    # HTMX helpers
    InvoiceItemRowView,
    RNCLookupView,
    CustomerDepartmentsView,
    CustomerDefaultsView,
    ItemSearchView,
    ItemQuickCreateView,
    CustomerSearchView,
    CustomerQuickCreateView,
    # NCF sequences
    NCFSequenceListView,
    NCFSequenceUpdateView,
    NCFSequenceDeleteView,
    # Payment terms
    PaymentTermListView,
    PaymentTermUpdateView,
    PaymentTermDeleteView,
    # Reports
    ReportIndexView,
    Report607View,
    Report608View,
    ReportAgingView,
    ReportStatementView,
    ReportSalesByPeriodView,
    ReportCollectionsView,
    ReportInvoicesByCustomerView,
    ReportITBISView,
    ReportSalesByNCFTypeView,
)

app_name = "sales"

urlpatterns = [
    # ── Customers ─────────────────────────────────────────────────────────────
    path("sales/customers/",                    CustomerListView.as_view(),   name="customer_list"),
    path("sales/customers/create/",             CustomerCreateView.as_view(), name="customer_create"),
    path("sales/customers/<uuid:pk>/",          CustomerDetailView.as_view(), name="customer_detail"),
    path("sales/customers/<uuid:pk>/edit/",     CustomerUpdateView.as_view(), name="customer_edit"),
    path("sales/customers/<uuid:pk>/delete/",   CustomerDeleteView.as_view(), name="customer_delete"),

    # Customer departments
    path("sales/customers/<uuid:customer_pk>/departments/table/",
         CustomerDepartmentTableView.as_view(), name="department_table"),
    path("sales/customers/<uuid:customer_pk>/departments/create/",
         CustomerDepartmentCreateView.as_view(), name="department_create"),
    path("sales/customers/<uuid:customer_pk>/departments/<uuid:pk>/edit/",
         CustomerDepartmentUpdateView.as_view(), name="department_edit"),
    path("sales/customers/<uuid:customer_pk>/departments/<uuid:pk>/toggle/",
         CustomerDepartmentToggleView.as_view(), name="department_toggle"),
    path("sales/customers/<uuid:customer_pk>/departments/<uuid:pk>/delete/",
         CustomerDepartmentDeleteView.as_view(), name="department_delete"),

    # ── Invoices ──────────────────────────────────────────────────────────────
    path("sales/",                              InvoiceListView.as_view(),    name="invoice_list"),
    path("sales/create/",                       InvoiceCreateView.as_view(),  name="invoice_create"),
    path("sales/<uuid:pk>/",                    InvoiceDetailView.as_view(),  name="invoice_detail"),
    path("sales/<uuid:pk>/edit/",               InvoiceUpdateView.as_view(),  name="invoice_edit"),

    # Invoice status transitions
    path("sales/<uuid:pk>/confirm/",            InvoiceConfirmView.as_view(), name="invoice_confirm"),
    path("sales/<uuid:pk>/send/",               InvoiceSendView.as_view(),    name="invoice_send"),
    path("sales/<uuid:pk>/pay/",                InvoicePayView.as_view(),     name="invoice_pay"),
    path("sales/<uuid:pk>/cancel/",             InvoiceCancelView.as_view(),  name="invoice_cancel"),
    path("sales/<uuid:pk>/delete/",             InvoiceDeleteView.as_view(),  name="invoice_delete"),

    # Credit / debit notes
    path("sales/<uuid:pk>/credit-note/",        CreditNoteCreateView.as_view(), name="credit_note_create"),

    # PDF / Print
    path("sales/<uuid:pk>/pdf/",                InvoicePDFView.as_view(),     name="invoice_pdf"),
    path("sales/<uuid:pk>/print/",              InvoicePrintView.as_view(),   name="invoice_print"),

    # ── Quotations ────────────────────────────────────────────────────────────
    path("quotations/",                            QuotationListView.as_view(),   name="quotation_list"),
    path("quotations/create/",                     QuotationCreateView.as_view(), name="quotation_create"),
    path("quotations/<uuid:pk>/",                  QuotationDetailView.as_view(), name="quotation_detail"),
    path("quotations/<uuid:pk>/edit/",             QuotationUpdateView.as_view(), name="quotation_edit"),

    # Quotation transitions
    path("quotations/<uuid:pk>/confirm/",          QuotationConfirmView.as_view(), name="quotation_confirm"),
    path("quotations/<uuid:pk>/send/",             QuotationSendView.as_view(),    name="quotation_send"),
    path("quotations/<uuid:pk>/email/",            QuotationEmailView.as_view(),   name="quotation_email"),
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
    path("sale-orders/<uuid:pk>/email/",           SaleOrderEmailView.as_view(),   name="sale_order_email"),

    # ── Payments ─────────────────────────────────────────────────────────────────
    path("payments/",                              PaymentListView.as_view(),      name="payment_list"),
    path("payments/create/",                       PaymentCreateView.as_view(),    name="payment_create"),
    path("payments/<uuid:pk>/",                    PaymentDetailView.as_view(),    name="payment_detail"),
    path("payments/<uuid:pk>/delete/",             PaymentDeleteView.as_view(),    name="payment_delete"),

    # ── HTMX helpers ──────────────────────────────────────────────────────────
    path("sales/items/row/",                    InvoiceItemRowView.as_view(),      name="item_row"),
    path("sales/rnc-lookup/",                   RNCLookupView.as_view(),           name="rnc_lookup"),
    path("sales/customers/departments/",        CustomerDepartmentsView.as_view(), name="departments_for_customer"),
    path("payments/outstanding-invoices/",         OutstandingInvoicesView.as_view(), name="payment_outstanding_invoices"),
    path("sales/customer-defaults/",            CustomerDefaultsView.as_view(),    name="customer_defaults"),
    path("sales/items/search/",                  ItemSearchView.as_view(),          name="item_search"),
    path("sales/htmx/items/create/",            ItemQuickCreateView.as_view(),     name="item_quick_create"),
    path("sales/htmx/customers/search/",        CustomerSearchView.as_view(),      name="customer_search"),
    path("sales/htmx/customers/create/",        CustomerQuickCreateView.as_view(), name="customer_quick_create"),

    # ── Payment terms ────────────────────────────────────────────────────────
    path("sales/payment-terms/",                PaymentTermListView.as_view(),   name="payment_term_list"),
    path("sales/payment-terms/<int:pk>/edit/",  PaymentTermUpdateView.as_view(), name="payment_term_edit"),
    path("sales/payment-terms/<int:pk>/delete/",PaymentTermDeleteView.as_view(), name="payment_term_delete"),

    # ── NCF sequences ─────────────────────────────────────────────────────────
    path("sales/ncf/",                          NCFSequenceListView.as_view(),   name="ncf_sequences"),
    path("sales/ncf/<int:pk>/edit/",            NCFSequenceUpdateView.as_view(), name="ncf_sequence_edit"),
    path("sales/ncf/<int:pk>/delete/",          NCFSequenceDeleteView.as_view(), name="ncf_sequence_delete"),

    # ── DGII reports ──────────────────────────────────────────────────────────
    path("sales/reports/",                      ReportIndexView.as_view(),           name="reports"),
    path("sales/reports/607/",                  Report607View.as_view(),             name="report_607"),
    path("sales/reports/608/",                  Report608View.as_view(),             name="report_608"),

    # ── Management reports ────────────────────────────────────────────────────
    path("sales/reports/invoices-by-customer/", ReportInvoicesByCustomerView.as_view(), name="report_invoices_by_customer"),
    path("sales/reports/aging/",                ReportAgingView.as_view(),           name="report_aging"),
    path("sales/reports/statement/",            ReportStatementView.as_view(),       name="report_statement"),
    path("sales/reports/sales-by-period/",      ReportSalesByPeriodView.as_view(),   name="report_sales_period"),
    path("sales/reports/collections/",          ReportCollectionsView.as_view(),          name="report_collections"),
    path("sales/reports/itbis/",                ReportITBISView.as_view(),                name="report_itbis"),
    path("sales/reports/ncf-type/",             ReportSalesByNCFTypeView.as_view(),       name="report_ncf_type"),
]
