from django.contrib import admin

from .models import Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "created_at"]
    list_filter = ["organization"]
    search_fields = ["name"]
    raw_id_fields = ["organization"]
    readonly_fields = ["id", "created_at", "updated_at", "deleted_at"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["category", "amount", "date", "status", "organization", "created_at"]
    list_filter = ["status", "organization", "category"]
    search_fields = ["description"]
    raw_id_fields = ["organization", "category", "approved_by"]
    readonly_fields = ["id", "created_at", "updated_at", "deleted_at"]
