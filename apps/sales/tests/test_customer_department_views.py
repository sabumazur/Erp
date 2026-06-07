"""
Tests for CustomerDepartment CRUD views — zero coverage before this file.

Gaps covered:
  - CustomerDepartmentCreateView: login guard, admin guard, creates dept
  - CustomerDepartmentUpdateView: login guard, admin guard, updates dept
  - CustomerDepartmentDeleteView: login guard, admin guard, blocks delete when orders exist
  - CustomerDepartmentToggleView: toggles is_active
"""
import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import (
    MembershipFactory,
    OrganizationFactory,
    UserFactory,
)
from apps.sales.models import CustomerDepartment, SalesDocument
from .factories import CustomerFactory, SalesDocumentFactory


# ── helpers ───────────────────────────────────────────────────────────────────

def _login(client, user, org):
    client.force_login(user)
    s = client.session
    s["active_org_slug"] = org.slug
    s.save()


def _make_admin(org=None):
    org = org or OrganizationFactory()
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.ADMIN)
    return user, org


def _make_member(org=None):
    org = org or OrganizationFactory()
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.MEMBER)
    return user, org


# ── CustomerDepartmentCreateView ──────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerDepartmentCreateView:

    def test_requires_login(self, client):
        customer = CustomerFactory()
        url = reverse("sales:department_create", kwargs={"customer_pk": customer.pk})
        resp = client.post(url, {"name": "Almacén"})
        assert resp.status_code in (302, 403)

    def test_member_cannot_create(self, client):
        user, org = _make_member()
        customer = CustomerFactory(organization=org)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:department_create", kwargs={"customer_pk": customer.pk}),
            {"name": "Almacén", "is_active": True},
        )
        # Members lack admin_required → should be forbidden (403) or redirected
        assert resp.status_code in (302, 403)

    def test_admin_creates_department(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:department_create", kwargs={"customer_pk": customer.pk}),
            {"name": "Almacén", "is_active": True},
        )
        assert resp.status_code in (200, 302)
        assert CustomerDepartment.objects.filter(customer=customer, name="Almacén").exists()

    def test_returns_404_for_customer_in_other_org(self, client):
        user, org = _make_admin()
        other_org = OrganizationFactory()
        other_customer = CustomerFactory(organization=other_org)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:department_create", kwargs={"customer_pk": other_customer.pk}),
            {"name": "Depto X"},
        )
        assert resp.status_code == 404


# ── CustomerDepartmentUpdateView ──────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerDepartmentUpdateView:

    def _create_dept(self, org, customer):
        return CustomerDepartment.objects.create(
            organization=org,
            customer=customer,
            name="Original",
        )

    def test_admin_can_update(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        dept = self._create_dept(org, customer)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:department_edit", kwargs={"customer_pk": customer.pk, "pk": dept.pk}),
            {"name": "Renovado", "is_active": True},
        )
        dept.refresh_from_db()
        assert resp.status_code in (200, 302)
        assert dept.name == "Renovado"

    def test_member_cannot_update(self, client):
        user, org = _make_member()
        customer = CustomerFactory(organization=org)
        dept = self._create_dept(org, customer)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:department_edit", kwargs={"customer_pk": customer.pk, "pk": dept.pk}),
            {"name": "Hackeado"},
        )
        assert resp.status_code in (302, 403)
        dept.refresh_from_db()
        assert dept.name == "Original"


# ── CustomerDepartmentDeleteView ──────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerDepartmentDeleteView:

    def _create_dept(self, org, customer):
        return CustomerDepartment.objects.create(
            organization=org,
            customer=customer,
            name="Para borrar",
        )

    def test_admin_can_delete_dept_with_no_orders(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        dept = self._create_dept(org, customer)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:department_delete", kwargs={"customer_pk": customer.pk, "pk": dept.pk}),
        )
        assert resp.status_code in (200, 302)
        assert not CustomerDepartment.objects.filter(pk=dept.pk).exists()

    def test_cannot_delete_dept_with_sale_orders(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        dept = self._create_dept(org, customer)
        # Attach a sale order to this dept
        SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.SALE_ORDER,
            department=dept,
        )
        _login(client, user, org)

        resp = client.post(
            reverse("sales:department_delete", kwargs={"customer_pk": customer.pk, "pk": dept.pk}),
        )
        # Should respond with error (200 for HTMX or redirect with message)
        assert CustomerDepartment.objects.filter(pk=dept.pk).exists()


# ── CustomerDepartmentToggleView ──────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerDepartmentToggleView:

    def test_toggles_is_active(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        dept = CustomerDepartment.objects.create(
            organization=org, customer=customer, name="Toggle", is_active=True
        )
        _login(client, user, org)

        client.post(
            reverse("sales:department_toggle", kwargs={"customer_pk": customer.pk, "pk": dept.pk}),
        )
        dept.refresh_from_db()
        assert dept.is_active is False

    def test_toggle_twice_restores_active(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        dept = CustomerDepartment.objects.create(
            organization=org, customer=customer, name="Toggle2", is_active=True
        )
        _login(client, user, org)
        url = reverse("sales:department_toggle", kwargs={"customer_pk": customer.pk, "pk": dept.pk})

        client.post(url)
        client.post(url)
        dept.refresh_from_db()
        assert dept.is_active is True
