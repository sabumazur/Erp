"""
Report view tests for the purchases app.

Each report follows the 4-test pattern:
  1. login-required → 302
  2. MEMBER role → 403
  3. ADMIN role → 200
  4. Empty state → 200, not 500
  5. Org isolation → no data leakage from org B

Reports covered:
  - Report 606      (purchases:report_606)
  - AP Aging        (purchases:report_aging)
  - Supplier Statement (purchases:report_statement)
  - Spend by Period  (purchases:report_spend_period)
  - By Supplier      (purchases:report_by_supplier)
  - Payments         (purchases:report_payments)
  - ITBIS Credits    (purchases:report_itbis)
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.purchases.models import PurchaseDocument
from apps.purchases.services import SupplierInvoiceService, SupplierPaymentService
from apps.purchases.tests.factories import (
    PurchaseDocumentFactory,
    PurchaseDocumentItemFactory,
    SupplierFactory,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_admin(org=None):
    org = org or OrganizationFactory()
    return MembershipFactory(user=UserFactory(), organization=org, role=Membership.Role.ADMIN)


def _make_member(org=None):
    org = org or OrganizationFactory()
    return MembershipFactory(user=UserFactory(), organization=org, role=Membership.Role.MEMBER)


def _login(client, ms):
    client.force_login(ms.user)
    s = client.session
    s["active_org_slug"] = ms.organization.slug
    s.save()


def _confirmed_si(org, supplier, ncf="B0100000001"):
    si = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
        status=PurchaseDocument.Status.DRAFT,
        supplier_ncf=ncf,
        supplier_ncf_type="B01",
    )
    PurchaseDocumentItemFactory(purchase_document=si, unit_price=Decimal("1000.00"))
    si.recompute_totals()
    SupplierInvoiceService.confirm(si)
    si.refresh_from_db()
    return si


# ── Report 606 ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReport606View:

    url = reverse("purchases:report_606")

    def test_requires_login(self, client):
        assert client.get(self.url).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(self.url).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(self.url).status_code == 200

    def test_empty_state_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(self.url)
        assert r.status_code == 200

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        si_b = _confirmed_si(org_b, supplier_b, ncf="B0100000099")

        _login(client, ms_a)
        r = client.get(self.url)
        assert r.status_code == 200
        assert si_b.supplier_ncf.encode() not in r.content


# ── AP Aging ──────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReportAPAgingView:

    url = reverse("purchases:report_aging")

    def test_requires_login(self, client):
        assert client.get(self.url).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(self.url).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(self.url).status_code == 200

    def test_empty_state_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(self.url)
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b, name="Supplier B Aging")
        _confirmed_si(org_b, supplier_b, ncf="B0100000099")

        _login(client, ms_a)
        r = client.get(self.url)
        assert r.status_code == 200
        assert r.context["rows"] == []


# ── Supplier Statement ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReportSupplierStatementView:

    url = reverse("purchases:report_statement")

    def test_requires_login(self, client):
        assert client.get(self.url).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(self.url).status_code == 403

    def test_admin_200_no_params(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(self.url).status_code == 200

    def test_empty_state_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(self.url)
        assert r.status_code == 200

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        _confirmed_si(org_b, supplier_b, ncf="B0100000099")

        _login(client, ms_a)
        r = client.get(self.url, {"supplier": str(supplier_b.pk),
                                   "date_from": "2024-01-01",
                                   "date_to": "2024-12-31"})
        # supplier_b belongs to org_b — get_object_or_404 should 404
        assert r.status_code == 404


# ── Spend by Period ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReportSpendByPeriodView:

    url = reverse("purchases:report_spend_period")

    def test_requires_login(self, client):
        assert client.get(self.url).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(self.url).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(self.url).status_code == 200

    def test_empty_state_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(self.url, {"year": "2025"})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        _confirmed_si(org_b, supplier_b, ncf="B0100000099")

        _login(client, ms_a)
        r = client.get(self.url, {"year": "2025"})
        assert r.status_code == 200
        assert r.context["rows"] == []


# ── Purchases by Supplier ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReportPurchasesBySupplierView:

    url = reverse("purchases:report_by_supplier")

    def test_requires_login(self, client):
        assert client.get(self.url).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(self.url).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(self.url).status_code == 200

    def test_empty_state_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(self.url, {"date_from": "2025-01-01", "date_to": "2025-12-31"})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b, name="Isolated Supplier B")
        _confirmed_si(org_b, supplier_b, ncf="B0100000099")

        _login(client, ms_a)
        r = client.get(self.url, {"date_from": "2000-01-01", "date_to": "2099-12-31"})
        assert r.status_code == 200
        # No org_b supplier should appear
        assert b"Isolated Supplier B" not in r.content


# ── Supplier Payments Report ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestReportSupplierPaymentsView:

    url = reverse("purchases:report_payments")

    def test_requires_login(self, client):
        assert client.get(self.url).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(self.url).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(self.url).status_code == 200

    def test_empty_state_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(self.url, {"date_from": "2025-01-01", "date_to": "2025-01-31"})
        assert r.status_code == 200
        assert r.context["payments"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        si_b = _confirmed_si(org_b, supplier_b, ncf="B0100000099")
        SupplierPaymentService.create_payment(
            supplier=supplier_b,
            org=org_b,
            payment_date=si_b.issue_date,
            method="TRANSFER",
            reference="ORG-B-PAYMENT",
            notes="",
            allocations=[{"invoice": si_b, "amount": si_b.total}],
        )

        _login(client, ms_a)
        r = client.get(self.url, {"date_from": "2000-01-01", "date_to": "2099-12-31"})
        assert r.status_code == 200
        assert b"ORG-B-PAYMENT" not in r.content


# ── ITBIS Credits Report ──────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReportITBISCreditsView:

    url = reverse("purchases:report_itbis")

    def test_requires_login(self, client):
        assert client.get(self.url).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(self.url).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(self.url).status_code == 200

    def test_empty_state_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(self.url, {"year": "2025"})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        _confirmed_si(org_b, supplier_b, ncf="B0100000099")

        _login(client, ms_a)
        r = client.get(self.url, {"year": "2025"})
        assert r.status_code == 200
        assert r.context["rows"] == []
