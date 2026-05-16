from django.urls import path
from . import views

app_name = "suppliers"

urlpatterns = [
    path("",                    views.SupplierListView.as_view(),   name="supplier_list"),
    path("crear/",              views.SupplierCreateView.as_view(), name="supplier_create"),
    path("<uuid:pk>/",          views.SupplierDetailView.as_view(), name="supplier_detail"),
    path("<uuid:pk>/editar/",   views.SupplierUpdateView.as_view(), name="supplier_edit"),
    path("<uuid:pk>/eliminar/", views.SupplierDeleteView.as_view(), name="supplier_delete"),
]
