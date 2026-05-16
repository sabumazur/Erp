from django.urls import path
from . import views

app_name = "expenses"

urlpatterns = [
    # Expense Categories
    path("categorias/", views.ExpenseCategoryListView.as_view(), name="category_list"),
    path("categorias/<uuid:pk>/edit/", views.ExpenseCategoryUpdateView.as_view(), name="category_edit"),
    path("categorias/<uuid:pk>/delete/", views.ExpenseCategoryDeleteView.as_view(), name="category_delete"),

    # Expenses
    path("", views.ExpenseListView.as_view(), name="expense_list"),
    path("<uuid:pk>/edit/", views.ExpenseUpdateView.as_view(), name="expense_edit"),
    path("<uuid:pk>/delete/", views.ExpenseDeleteView.as_view(), name="expense_delete"),
]
