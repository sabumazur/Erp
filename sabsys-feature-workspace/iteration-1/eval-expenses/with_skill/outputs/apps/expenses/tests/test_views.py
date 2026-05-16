import pytest
from django.urls import reverse

from apps.expenses.models import Expense
from apps.expenses.tests.factories import ExpenseCategoryFactory, ExpenseFactory


def _login(client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_org_slug"] = membership.organization.slug
    session.save()


@pytest.mark.django_db
class TestExpenseCategoryViews:

    def test_list_requires_login(self, client):
        response = client.get(reverse("expenses:category_list"))
        assert response.status_code == 302

    def test_list_accessible_to_admin(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.get(reverse("expenses:category_list"))
        assert response.status_code == 200

    def test_create_category(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.post(
            reverse("expenses:category_list"),
            {"name": "Alimentos"},
        )
        assert response.status_code == 302
        from apps.expenses.models import ExpenseCategory
        assert ExpenseCategory.objects.filter(
            name="Alimentos", organization=admin_membership.organization
        ).exists()

    def test_delete_category_blocked_with_expenses(self, client, admin_membership):
        category = ExpenseCategoryFactory(organization=admin_membership.organization)
        ExpenseFactory(organization=admin_membership.organization, category=category)
        _login(client, admin_membership)
        response = client.post(reverse("expenses:category_delete", args=[category.pk]))
        # blocked — category still exists
        category.refresh_from_db()
        assert category.deleted_at is None

    def test_delete_category_succeeds_when_no_expenses(self, client, admin_membership):
        category = ExpenseCategoryFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        client.post(reverse("expenses:category_delete", args=[category.pk]))
        from apps.expenses.models import ExpenseCategory
        assert ExpenseCategory.all_objects.get(pk=category.pk).deleted_at is not None


@pytest.mark.django_db
class TestExpenseViews:

    def test_list_requires_login(self, client):
        response = client.get(reverse("expenses:expense_list"))
        assert response.status_code == 302

    def test_list_accessible_to_member(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("expenses:expense_list"))
        assert response.status_code == 200

    def test_delete_requires_admin(self, client, member_membership):
        expense = ExpenseFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(reverse("expenses:expense_delete", args=[expense.pk]))
        assert response.status_code == 403

    def test_delete_approved_expense_blocked(self, client, admin_membership):
        expense = ExpenseFactory(
            organization=admin_membership.organization,
            status=Expense.Status.APPROVED,
        )
        _login(client, admin_membership)
        client.post(reverse("expenses:expense_delete", args=[expense.pk]))
        expense.refresh_from_db()
        assert expense.deleted_at is None

    def test_delete_pending_expense_succeeds(self, client, admin_membership):
        expense = ExpenseFactory(
            organization=admin_membership.organization,
            status=Expense.Status.PENDING,
        )
        _login(client, admin_membership)
        response = client.post(reverse("expenses:expense_delete", args=[expense.pk]))
        assert response.status_code == 302
        expense.refresh_from_db()
        assert expense.deleted_at is not None

    def test_create_expense(self, client, admin_membership):
        category = ExpenseCategoryFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("expenses:expense_list"),
            {
                "category": str(category.pk),
                "amount": "150.00",
                "date": "2026-05-15",
                "description": "Lunch",
                "status": Expense.Status.PENDING,
            },
        )
        assert response.status_code == 302
        assert Expense.objects.filter(
            organization=admin_membership.organization,
            description="Lunch",
        ).exists()
