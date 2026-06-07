"""
Tests for CustomerDetailView — balance/aging display and org isolation.

Gaps covered:
  - CustomerDetailView requires login
  - CustomerDetailView is org-scoped (returns 404 for cross-org customer PKs)
  - CustomerDetailView returns 200 for valid customer
  - Balance summary is present in context
  - Aging breakdown is present in context
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import (
    MembershipFactory,
    OrganizationFactory,
    UserFactory,
)
from apps.sales.models import SalesDocument
from .factories import CustomerFactory, SalesDocumentFactory, SalesDocumentItemFactory


# ── helpers ───────────────────────────────────────────────────────────────────

def _login(client, user, org):
    client.force_login(user)
    s = client.session
    s["active_org_slug"] = org.slug
    s.save()


def _make_admin(org=None):
    org = org or OrganizationFactory()
    user = UserFactory()
    m = MembershipFactory(user=user, organization=org, role=Membership.Role.ADMIN)
    return user, org, m


# ── CustomerDetailView ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerDetailView:

    def test_requires_login(self, client):
        customer = CustomerFactory()
        url = reverse("sales:customer_detail", kwargs={"pk": customer.pk})
        resp = client.get(url)
        assert resp.status_code in (302, 403)

    def test_returns_200_for_valid_customer(self, client):
        user, org, _ = _make_admin()
        customer = CustomerFactory(organization=org)
        _login(client, user, org)

        resp = client.get(reverse("sales:customer_detail", kwargs={"pk": customer.pk}))
        assert resp.status_code == 200

    def test_returns_404_for_customer_in_other_org(self, client):
        user, org, _ = _make_admin()
        other_org = OrganizationFactory()
        other_customer = CustomerFactory(organization=other_org)
        _login(client, user, org)

        resp = client.get(reverse("sales:customer_detail", kwargs={"pk": other_customer.pk}))
        assert resp.status_code == 404

    def test_context_contains_balance_summary(self, client):
        user, org, _ = _make_admin()
        customer = CustomerFactory(organization=org)
        _login(client, user, org)

        resp = client.get(reverse("sales:customer_detail", kwargs={"pk": customer.pk}))
        assert "total_invoiced" in resp.context
        assert "total_paid" in resp.context
        assert "balance" in resp.context

    def test_context_contains_aging_breakdown(self, client):
        user, org, _ = _make_admin()
        customer = CustomerFactory(organization=org)
        _login(client, user, org)

        resp = client.get(reverse("sales:customer_detail", kwargs={"pk": customer.pk}))
        assert "aging_breakdown" in resp.context
        assert isinstance(resp.context["aging_breakdown"], list)

    def test_balance_reflects_confirmed_invoices(self, client):
        user, org, _ = _make_admin()
        customer = CustomerFactory(organization=org)
        inv = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.INVOICE,
            status=SalesDocument.Status.CONFIRMED,
            encf="E310000000001",
        )
        SalesDocumentItemFactory(
            document=inv,
            quantity=Decimal("1"),
            unit_price=Decimal("1000.00"),
        )
        inv.recompute_totals()
        _login(client, user, org)

        resp = client.get(reverse("sales:customer_detail", kwargs={"pk": customer.pk}))
        assert resp.context["total_invoiced"] > Decimal("0")

    def test_draft_invoices_excluded_from_balance(self, client):
        user, org, _ = _make_admin()
        customer = CustomerFactory(organization=org)
        draft = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.INVOICE,
            status=SalesDocument.Status.DRAFT,
        )
        SalesDocumentItemFactory(document=draft, unit_price=Decimal("5000.00"))
        draft.recompute_totals()
        _login(client, user, org)

        resp = client.get(reverse("sales:customer_detail", kwargs={"pk": customer.pk}))
        # Draft invoices are excluded — balance should be zero
        assert resp.context["total_invoiced"] == Decimal("0")

    def test_member_role_can_view(self, client):
        org = OrganizationFactory()
        user = UserFactory()
        MembershipFactory(user=user, organization=org, role=Membership.Role.MEMBER)
        customer = CustomerFactory(organization=org)
        _login(client, user, org)

        resp = client.get(reverse("sales:customer_detail", kwargs={"pk": customer.pk}))
        assert resp.status_code == 200
