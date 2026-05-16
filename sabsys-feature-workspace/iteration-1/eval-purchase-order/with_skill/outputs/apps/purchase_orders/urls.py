from django.urls import path

from . import views

app_name = "purchase_orders"

urlpatterns = [
    # ── Suppliers ──────────────────────────────────────────────────────────────
    path(
        "proveedores/",
        views.SupplierListView.as_view(),
        name="supplier_list",
    ),
    path(
        "proveedores/<uuid:pk>/editar/",
        views.SupplierUpdateView.as_view(),
        name="supplier_edit",
    ),
    path(
        "proveedores/<uuid:pk>/eliminar/",
        views.SupplierDeleteView.as_view(),
        name="supplier_delete",
    ),
    # ── Purchase Orders ────────────────────────────────────────────────────────
    path(
        "",
        views.PurchaseOrderListView.as_view(),
        name="purchase_order_list",
    ),
    path(
        "nueva/",
        views.PurchaseOrderCreateView.as_view(),
        name="purchase_order_create",
    ),
    path(
        "<uuid:pk>/",
        views.PurchaseOrderDetailView.as_view(),
        name="purchase_order_detail",
    ),
    path(
        "<uuid:pk>/editar/",
        views.PurchaseOrderUpdateView.as_view(),
        name="purchase_order_edit",
    ),
    path(
        "<uuid:pk>/eliminar/",
        views.PurchaseOrderDeleteView.as_view(),
        name="purchase_order_delete",
    ),
    # ── Status transitions ─────────────────────────────────────────────────────
    path(
        "<uuid:pk>/confirmar/",
        views.PurchaseOrderConfirmView.as_view(),
        name="purchase_order_confirm",
    ),
    path(
        "<uuid:pk>/recibir/",
        views.PurchaseOrderReceiveView.as_view(),
        name="purchase_order_receive",
    ),
    path(
        "<uuid:pk>/anular/",
        views.PurchaseOrderCancelView.as_view(),
        name="purchase_order_cancel",
    ),
]
