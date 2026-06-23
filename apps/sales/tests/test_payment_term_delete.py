"""
Tests for PaymentTermDeleteView.

Regression: delete view used term.customer_set (wrong) instead of
term.customers (the declared related_name), so the guard never fired
and term.delete() raised an unhandled ProtectedError.
"""
import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import (
    MembershipFactory,
    OrganizationFactory,
    UserFactory,
)
from apps.sales.models import Customer, PaymentTerm
from .factories import CustomerFactory


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


def _create_term(org, name="30 días", days_due=30):
    return PaymentTerm.objects.create(organization=org, name=name, days_due=days_due)


def _delete_url(pk):
    return reverse("sales:payment_term_delete", args=[pk])


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPaymentTermDeleteView:

    def test_deletes_term_with_no_customers(self, client):
        """Term not referenced by any customer is deleted successfully."""
        user, org = _make_admin()
        term = _create_term(org)
        _login(client, user, org)

        resp = client.post(_delete_url(term.pk))

        assert resp.status_code == 302
        assert not PaymentTerm.objects.filter(pk=term.pk).exists()

    def test_blocks_delete_when_customer_references_term(self, client):
        """Term referenced by a customer is blocked — guard uses term.customers."""
        user, org = _make_admin()
        term = _create_term(org)
        CustomerFactory(organization=org, payment_term=term)
        _login(client, user, org)

        resp = client.post(_delete_url(term.pk))

        # Redirected back to list with an error message — term must still exist
        assert resp.status_code == 302
        assert PaymentTerm.objects.filter(pk=term.pk).exists()

    def test_blocks_delete_htmx_returns_swal_trigger(self, client):
        """Blocked HTMX delete returns HX-Trigger with showSwal, not 500."""
        user, org = _make_admin()
        term = _create_term(org)
        CustomerFactory(organization=org, payment_term=term)
        _login(client, user, org)

        resp = client.post(
            _delete_url(term.pk),
            HTTP_HX_REQUEST="true",
        )

        assert resp.status_code == 200
        assert "showSwal" in resp.get("HX-Trigger", "")
        assert PaymentTerm.objects.filter(pk=term.pk).exists()

    def test_htmx_delete_success_returns_table_refresh(self, client):
        """Successful HTMX delete refreshes the datatable."""
        user, org = _make_admin()
        term = _create_term(org)
        _login(client, user, org)

        resp = client.post(
            _delete_url(term.pk),
            HTTP_HX_REQUEST="true",
        )

        assert resp.status_code == 200
        assert "showToast" in resp.get("HX-Trigger", "")
        assert not PaymentTerm.objects.filter(pk=term.pk).exists()

    def test_requires_admin_role(self, client):
        """Non-admin members cannot delete payment terms."""
        user, org = _make_member()
        term = _create_term(org)
        _login(client, user, org)

        resp = client.post(_delete_url(term.pk))

        assert resp.status_code in (302, 403)
        assert PaymentTerm.objects.filter(pk=term.pk).exists()

    def test_requires_login(self, client):
        """Unauthenticated requests are redirected to login."""
        user, org = _make_admin()
        term = _create_term(org)

        resp = client.post(_delete_url(term.pk))

        assert resp.status_code in (302, 403)

    def test_org_isolation(self, client):
        """Term belonging to another org returns 404."""
        user, org = _make_admin()
        other_org = OrganizationFactory()
        term = _create_term(other_org)
        _login(client, user, org)

        resp = client.post(_delete_url(term.pk))

        assert resp.status_code == 404
        assert PaymentTerm.objects.filter(pk=term.pk).exists()
