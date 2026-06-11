from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.purchases.models import PurchaseDocument
from apps.purchases.tests.factories import (
    PurchaseDocumentFactory,
    PurchaseDocumentItemFactory,
    SupplierFactory,
    SupplierPaymentFactory,
)

REPORT_URLS = [
    ("purchases:reports", {}),
    ("purchases:report_606", {}),
    ("purchases:report_aging", {}),
    ("purchases:report_statement", {}),
    ("purchases:report_spend_period", {"year": "2026"}),
    ("purchases:report_by_supplier", {"date_from": "2026-01-01", "date_to": "2026-12-31"}),
    ("purchases:report_payments", {"date_from": "2026-01-01", "date_to": "2026-12-31"}),
    ("purchases:report_itbis", {"year": "2026", "month": "6"}),
]


def login(client, user):
    client.force_login(user)


def make_member(role=Membership.Role.ADMIN):
    org = OrganizationFactory()
    user = UserFactory()
    membership = MembershipFactory(user=user, organization=org, role=role)
    return user, org, membership


def set_active_org(client, org):
    session = client.session
    session["active_org_slug"] = org.slug
    session.save()


def make_supplier_invoice(org, supplier=None, **kwargs):
    defaults = {
        "doc_type": PurchaseDocument.DocType.SUPPLIER_INVOICE,
        "status": PurchaseDocument.Status.CONFIRMED,
        "supplier_ncf": "B0100000001",
        "supplier_rnc": "131123456",
    }
    defaults.update(kwargs)
    invoice = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier or SupplierFactory(organization=org),
        **defaults,
    )
    PurchaseDocumentItemFactory(purchase_document=invoice, unit_price=Decimal("1000.00"))
    invoice.recompute_totals()
    invoice.refresh_from_db()
    return invoice


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestPurchaseReportAccess:

    @pytest.mark.parametrize("url_name,params", REPORT_URLS)
    def test_anonymous_is_redirected(self, client, url_name, params):
        resp = client.get(reverse(url_name), params)
        assert resp.status_code in (302, 403)

    @pytest.mark.parametrize("url_name,params", REPORT_URLS)
    def test_member_is_forbidden(self, client, url_name, params):
        user, org, _ = make_member(Membership.Role.MEMBER)
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse(url_name), params)
        assert resp.status_code == 403

    @pytest.mark.parametrize("url_name,params", REPORT_URLS)
    def test_admin_gets_200(self, client, url_name, params):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse(url_name), params)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestReport606Content:

    def test_csv_contains_confirmed_supplier_invoice(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        invoice = make_supplier_invoice(org)
        login(client, user)
        set_active_org(client, org)

        today = timezone.now().date()
        resp = client.get(
            reverse("purchases:report_606"),
            {"month": str(today.month), "year": str(today.year), "format": "csv"},
        )

        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/csv")
        content = resp.content.decode("utf-8")
        assert invoice.supplier_ncf in content
        assert invoice.supplier_rnc in content

    def test_csv_excludes_draft_invoices(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        make_supplier_invoice(org, status=PurchaseDocument.Status.DRAFT, supplier_ncf="B0199999999")
        login(client, user)
        set_active_org(client, org)

        today = timezone.now().date()
        resp = client.get(
            reverse("purchases:report_606"),
            {"month": str(today.month), "year": str(today.year), "format": "csv"},
        )

        assert "B0199999999" not in resp.content.decode("utf-8")


@pytest.mark.django_db
class TestAPAgingContent:

    def test_overdue_invoice_appears(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        supplier = SupplierFactory(organization=org, name="Distribuidora Vencida SRL")
        make_supplier_invoice(
            org,
            supplier=supplier,
            due_date=timezone.now().date() - timedelta(days=45),
        )
        login(client, user)
        set_active_org(client, org)

        resp = client.get(reverse("purchases:report_aging"))

        assert resp.status_code == 200
        assert "Distribuidora Vencida SRL" in resp.content.decode("utf-8")


@pytest.mark.django_db
class TestReportCacheInvalidation:

    def test_606_cache_busts_on_new_invoice(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)
        today = timezone.now().date()
        params = {"month": str(today.month), "year": str(today.year)}

        resp1 = client.get(reverse("purchases:report_606"), params)
        assert resp1.status_code == 200
        assert len(resp1.context["invoices"]) == 0

        # Creating the invoice fires post_save → signals bump the per-org
        # generation, so the cached (empty) report becomes unreachable.
        make_supplier_invoice(org)

        resp2 = client.get(reverse("purchases:report_606"), params)
        assert resp2.status_code == 200
        assert len(resp2.context["invoices"]) == 1

    def test_payment_save_bumps_generation(self):
        org = OrganizationFactory()
        assert cache.get(f"purchases_report_gen:{org.pk}") is None
        SupplierPaymentFactory(organization=org)
        assert cache.get(f"purchases_report_gen:{org.pk}") is not None
