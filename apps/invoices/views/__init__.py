from .customers import (
    CustomerListView,
    CustomerDetailView,
    CustomerUpdateView,
    CustomerDeleteView,
    CustomerDepartmentCreateView,
    CustomerDepartmentUpdateView,
    CustomerDepartmentToggleView,
)
from .invoices import (
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
    NCFSequenceListView,
    NCFSequenceUpdateView,
    InvoiceItemRowView,
    RNCLookupView,
)
from .quotations import (
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
)
from .sale_orders import (
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
    CustomerDepartmentsView,
)
from .payments import (
    PaymentListView,
    PaymentCreateView,
    PaymentDetailView,
    PaymentDeleteView,
    OutstandingInvoicesView,
)
from .reports import (
    ReportIndexView,
    Report607View,
    Report608View,
    ReportAgingView,
    ReportStatementView,
    ReportSalesByPeriodView,
    ReportCollectionsView,
)
from .htmx import (
    CustomerDefaultsView,
    ItemCatalogView,
)
