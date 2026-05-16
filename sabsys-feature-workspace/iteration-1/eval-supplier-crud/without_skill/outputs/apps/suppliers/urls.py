from django.urls import path
from . import views

app_name = "suppliers"

urlpatterns = [
    path("",                   views.SupplierListView.as_view(),   name="supplier_list"),
    path("<uuid:pk>/",         views.SupplierDetailView.as_view(), name="supplier_detail"),
    path("<uuid:pk>/edit/",    views.SupplierUpdateView.as_view(), name="supplier_edit"),
    path("<uuid:pk>/delete/",  views.SupplierDeleteView.as_view(), name="supplier_delete"),
]
