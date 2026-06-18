from decimal import Decimal

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.sales.models import SalesDocument
from apps.sales.tests.factories import (
    CustomerFactory,
    SalesDocumentFactory,
    SalesDocumentItemFactory,
)

REPORT_URLS = [
    ("sales:report_aging", {}),
    ("sales:report_statement", {}),
    ("sales:report_sales_period", {"year": "2026"}),
    ("sales:report_invoices_by_customer", {"date_from": "2026-01-01", "date_to": "2026-12-31"}),
    ("sales:report_collections", {"date_from": "2026-01-01", "date_to": "2026-12-31"}),
    ("sales:report_itbis", {"year": "2026", "month": "6"}),
    ("sales:report_ncf_type", {"year": "2026", "month": "6"}),
]

# 607 / 608 redirect to the report hub when month/year are missing, so they
# get their own access cases below instead of the generic 200 happy path.
ALL_REPORT_URLS = REPORT_URLS + [
    ("sales:report_607", {"month": "6", "year": "2026"}),
    ("sales:report_608", {"month": "6", "year": "2026"}),
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


def make_confirmed_invoice(org, customer=None, **kwargs):
    defaults = {
        "status": SalesDocument.Status.CONFIRMED,
        "encf": "E310000000001",
    }
    defaults.update(kwargs)
    invoice = SalesDocumentFactory(
        organization=org,
        customer=customer or CustomerFactory(organization=org),
        **defaults,
    )
    SalesDocumentItemFactory(document=invoice, unit_price=Decimal("1000.00"))
    invoice.refresh_from_db()
    return invoice


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestSalesReportAccess:

    @pytest.mark.parametrize("url_name,params", ALL_REPORT_URLS)
    def test_anonymous_is_redirected(self, client, url_name, params):
        resp = client.get(reverse(url_name), params)
        assert resp.status_code in (302, 403)

    @pytest.mark.parametrize("url_name,params", ALL_REPORT_URLS)
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

    @pytest.mark.parametrize("url_name", ["sales:report_607", "sales:report_608"])
    def test_607_608_redirect_without_month_year(self, client, url_name):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert resp.url == reverse("sales:reports")


@pytest.mark.django_db
class TestReport607Content:

    def test_txt_contains_confirmed_invoice_row(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        invoice = make_confirmed_invoice(org)
        login(client, user)
        set_active_org(client, org)

        today = timezone.now().date()
        resp = client.get(
            reverse("sales:report_607"),
            {"month": str(today.month), "year": str(today.year)},
        )

        assert resp.status_code == 200
        assert resp["Content-Disposition"].startswith("attachment")
        content = resp.content.decode("utf-8")
        assert invoice.encf in content
        assert invoice.customer.rnc_cedula in content
        # Pipe-delimited DGII layout: buyer id and type come first.
        first_row = content.splitlines()[0]
        assert first_row.split("|")[0] == invoice.customer.rnc_cedula

    def test_txt_excludes_draft_invoices(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        make_confirmed_invoice(org, status=SalesDocument.Status.DRAFT, encf="E319999999999")
        login(client, user)
        set_active_org(client, org)

        today = timezone.now().date()
        resp = client.get(
            reverse("sales:report_607"),
            {"month": str(today.month), "year": str(today.year)},
        )

        assert "E319999999999" not in resp.content.decode("utf-8")


@pytest.mark.django_db
class TestReport608Content:

    def test_txt_contains_cancelled_invoice(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        invoice = make_confirmed_invoice(
            org, status=SalesDocument.Status.CANCELLED, encf="E310000000777"
        )
        login(client, user)
        set_active_org(client, org)

        today = timezone.now().date()
        resp = client.get(
            reverse("sales:report_608"),
            {"month": str(today.month), "year": str(today.year)},
        )

        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        assert invoice.encf in content
        assert content.splitlines()[0].split("|")[0] == invoice.encf


@pytest.mark.django_db
class TestStatementContent:

    def test_statement_renders_customer_invoices(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        customer = CustomerFactory(organization=org, name="Cliente Estado SRL")
        make_confirmed_invoice(org, customer=customer)
        login(client, user)
        set_active_org(client, org)

        resp = client.get(
            reverse("sales:report_statement"), {"customer": str(customer.pk)}
        )

        assert resp.status_code == 200
        assert "Cliente Estado SRL" in resp.content.decode("utf-8")


@pytest.mark.django_db
class TestAgingContent:

    def test_aging_lists_outstanding_customer(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        customer = CustomerFactory(organization=org, name="Cliente Moroso SRL")
        make_confirmed_invoice(org, customer=customer)
        login(client, user)
        set_active_org(client, org)

        resp = client.get(reverse("sales:report_aging"))

        assert resp.status_code == 200
        assert "Cliente Moroso SRL" in resp.content.decode("utf-8")
