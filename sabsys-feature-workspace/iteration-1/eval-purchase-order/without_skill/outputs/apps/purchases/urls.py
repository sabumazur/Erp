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
)

app_name = "purchases"

urlpatterns = [
    # ── Suppliers ─────────────────────────────────────────────────────────────
    path("purchases/suppliers/",                   SupplierListView.as_view(),   name="supplier_list"),
    path("purchases/suppliers/create/",            SupplierCreateView.as_view(), name="supplier_create"),
    path("purchases/suppliers/<uuid:pk>/",         SupplierDetailView.as_view(), name="supplier_detail"),
    path("purchases/suppliers/<uuid:pk>/edit/",    SupplierUpdateView.as_view(), name="supplier_edit"),
    path("purchases/suppliers/<uuid:pk>/delete/",  SupplierDeleteView.as_view(), name="supplier_delete"),

    # ── Purchase Orders ───────────────────────────────────────────────────────
    path("purchases/orders/",                      PurchaseOrderListView.as_view(),   name="purchase_order_list"),
    path("purchases/orders/create/",               PurchaseOrderCreateView.as_view(), name="purchase_order_create"),
    path("purchases/orders/<uuid:pk>/",            PurchaseOrderDetailView.as_view(), name="purchase_order_detail"),
    path("purchases/orders/<uuid:pk>/edit/",       PurchaseOrderUpdateView.as_view(), name="purchase_order_edit"),

    # Purchase Order transitions
    path("purchases/orders/<uuid:pk>/confirm/",    PurchaseOrderConfirmView.as_view(), name="purchase_order_confirm"),
    path("purchases/orders/<uuid:pk>/receive/",    PurchaseOrderReceiveView.as_view(), name="purchase_order_receive"),
    path("purchases/orders/<uuid:pk>/cancel/",     PurchaseOrderCancelView.as_view(),  name="purchase_order_cancel"),
    path("purchases/orders/<uuid:pk>/delete/",     PurchaseOrderDeleteView.as_view(),  name="purchase_order_delete"),
]
