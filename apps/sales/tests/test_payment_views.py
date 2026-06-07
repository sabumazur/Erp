"""
Tests for PaymentCreateView, PaymentListView, PaymentDeleteView.

Gaps covered:
  - PaymentListView requires login, is org-scoped
  - PaymentCreateView requires login
  - PaymentCreateView GET renders form
  - PaymentDeleteView requires admin
  - PaymentDeleteView deletes payment and reopens invoice
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
from apps.sales.models import Payment, SalesDocument
from apps.sales.services import NCFService, PaymentService
from .factories import (
    CustomerFactory,
    NCFSequenceFactory,
    PaymentFactory,
    SalesDocumentFactory,
    SalesDocumentItemFactory,
)


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


def _make_confirmed_invoice(org, customer, total=Decimal("1000.00")):
    NCFSequenceFactory(organization=org, ncf_type=31)
    inv = SalesDocumentFactory(
        organization=org,
        customer=customer,
        ncf_type=31,
        status=SalesDocument.Status.DRAFT,
    )
    SalesDocumentItemFactory(
        document=inv,
        quantity=Decimal("1"),
        unit_price=(total / Decimal("1.18")).quantize(Decimal("0.01")),
    )
    inv.recompute_totals()
    inv.refresh_from_db()
    NCFService.confirm(inv)
    inv.refresh_from_db()
    return inv


# ── PaymentListView ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPaymentListView:

    def test_requires_login(self, client):
        resp = client.get(reverse("sales:payment_list"))
        assert resp.status_code in (302, 403)

    def test_returns_200_for_authenticated_member(self, client):
        user, org = _make_member()
        _login(client, user, org)

        resp = client.get(reverse("sales:payment_list"))
        assert resp.status_code == 200

    def test_only_shows_org_payments(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        payment = PaymentFactory(organization=org, customer=customer)

        other_org = OrganizationFactory()
        other_customer = CustomerFactory(organization=other_org)
        other_payment = PaymentFactory(organization=other_org, customer=other_customer)

        _login(client, user, org)
        resp = client.get(reverse("sales:payment_list"))
        assert resp.status_code == 200
        # The response rows should contain our payment, not the other org's
        # We test context rather than HTML to avoid rendering dependency
        ctx_payments = list(resp.context["object_list"])
        pks = [p.pk for p in ctx_payments]
        assert payment.pk in pks
        assert other_payment.pk not in pks


# ── PaymentCreateView ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPaymentCreateView:

    def test_requires_login(self, client):
        resp = client.get(reverse("sales:payment_create"))
        assert resp.status_code in (302, 403)

    def test_get_renders_form(self, client):
        user, org = _make_admin()
        _login(client, user, org)

        resp = client.get(reverse("sales:payment_create"))
        assert resp.status_code == 200
        assert "form" in resp.context

    def test_post_no_allocations_returns_form_error(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:payment_create"),
            {
                "customer": str(customer.pk),
                "date": "2026-01-15",
                "method": "TRANSFER",
                "reference": "REF-001",
                "notes": "",
                # No alloc_invoices / alloc_amounts → triggers "at least one invoice" error
            },
        )
        assert resp.status_code == 200  # form re-rendered with errors
        assert Payment.objects.filter(organization=org).count() == 0


# ── PaymentDeleteView ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPaymentDeleteView:

    def test_requires_login(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        payment = PaymentFactory(organization=org, customer=customer)
        resp = client.post(reverse("sales:payment_delete", kwargs={"pk": payment.pk}))
        assert resp.status_code in (302, 403)

    def test_member_cannot_delete(self, client):
        user, org = _make_member()
        customer = CustomerFactory(organization=org)
        payment = PaymentFactory(organization=org, customer=customer)
        _login(client, user, org)

        resp = client.post(reverse("sales:payment_delete", kwargs={"pk": payment.pk}))
        assert resp.status_code in (302, 403)
        assert Payment.objects.filter(pk=payment.pk).exists()

    def test_admin_deletes_payment(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        inv = _make_confirmed_invoice(org, customer)

        payment = PaymentService.register(
            organization=org,
            customer=customer,
            payment_date=inv.issue_date,
            method=Payment.Method.TRANSFER,
            reference="",
            notes="",
            allocations=[{"invoice": inv, "amount": inv.total}],
        )
        _login(client, user, org)

        resp = client.post(reverse("sales:payment_delete", kwargs={"pk": payment.pk}))
        assert resp.status_code == 302
        assert not Payment.objects.filter(pk=payment.pk).exists()

    def test_deleting_payment_reopens_paid_invoice(self, client):
        user, org = _make_admin()
        customer = CustomerFactory(organization=org)
        inv = _make_confirmed_invoice(org, customer)

        payment = PaymentService.register(
            organization=org,
            customer=customer,
            payment_date=inv.issue_date,
            method=Payment.Method.TRANSFER,
            reference="",
            notes="",
            allocations=[{"invoice": inv, "amount": inv.total}],
        )
        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.PAID

        _login(client, user, org)
        client.post(reverse("sales:payment_delete", kwargs={"pk": payment.pk}))

        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.SENT

    def test_returns_404_for_payment_in_other_org(self, client):
        user, org = _make_admin()
        other_org = OrganizationFactory()
        other_customer = CustomerFactory(organization=other_org)
        other_payment = PaymentFactory(organization=other_org, customer=other_customer)
        _login(client, user, org)

        resp = client.post(reverse("sales:payment_delete", kwargs={"pk": other_payment.pk}))
        assert resp.status_code == 404
