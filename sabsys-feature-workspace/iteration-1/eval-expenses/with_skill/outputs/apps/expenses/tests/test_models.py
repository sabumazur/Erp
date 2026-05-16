import pytest
from apps.expenses.models import Expense, ExpenseCategory
from apps.expenses.tests.factories import ExpenseCategoryFactory, ExpenseFactory


@pytest.mark.django_db
class TestExpenseCategoryModel:

    def test_str(self):
        category = ExpenseCategoryFactory(name="Viáticos")
        assert str(category) == "Viáticos"

    def test_soft_delete(self):
        category = ExpenseCategoryFactory()
        pk = category.pk
        category.delete()
        assert ExpenseCategory.objects.filter(pk=pk).count() == 0
        assert ExpenseCategory.all_objects.filter(pk=pk).count() == 1


@pytest.mark.django_db
class TestExpenseModel:

    def test_str(self):
        expense = ExpenseFactory()
        assert str(expense) != ""

    def test_default_status_is_pending(self):
        expense = ExpenseFactory()
        assert expense.status == Expense.Status.PENDING

    def test_soft_delete(self):
        expense = ExpenseFactory()
        pk = expense.pk
        expense.delete()
        assert Expense.objects.filter(pk=pk).count() == 0
        assert Expense.all_objects.filter(pk=pk).count() == 1
