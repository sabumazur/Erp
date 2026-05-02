from django.urls import path
from . import views

app_name = "items"

urlpatterns = [
    path("",                     views.ItemListView.as_view(),   name="item_list"),
    path("search/",              views.ItemSearchView.as_view(), name="item_search"),
    path("<uuid:pk>/",           views.ItemDetailView.as_view(), name="item_detail"),
    path("<uuid:pk>/edit/",      views.ItemUpdateView.as_view(), name="item_edit"),
    path("<uuid:pk>/toggle/",    views.ItemToggleView.as_view(), name="item_toggle"),
]
