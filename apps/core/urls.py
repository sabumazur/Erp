from django.urls import path

from .views_modules import (
    ModuleListView,
    ModuleDetailView,
    ModuleUpdateView,
    ModuleToggleView,
    ModuleDeleteView,
)

app_name = "core"

urlpatterns = [
    path("modules/",                  ModuleListView.as_view(),   name="module_list"),
    path("modules/<int:pk>/",         ModuleDetailView.as_view(), name="module_detail"),
    path("modules/<int:pk>/edit/",    ModuleUpdateView.as_view(), name="module_edit"),
    path("modules/<int:pk>/toggle/",  ModuleToggleView.as_view(), name="module_toggle"),
    path("modules/<int:pk>/delete/",  ModuleDeleteView.as_view(), name="module_delete"),
]
