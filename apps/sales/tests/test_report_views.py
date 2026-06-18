"""
Tests for sales report views: AgingReport, SalesByPeriod, ITBIS, NCFType.

All report views carry admin_required = True:
  - Unauthenticated  -> 302
  - MEMBER role      -> 403
  - ADMIN/OWNER role -> 200

Also tests org isolation, date filtering, and empty-state (no 500).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.sales.models import SalesDocument
from apps.sales.services import NCFService

from .factories import (
    CustomerFactory,
    NCFSequenceFactory,
    SalesDocumentFactory,
    SalesDocumentItemFactory,
)


# ---- helpers -----------------------------------------------------------------

def _login(client, membership):
    client.force_login(membership.user)
    s = client.session
    s["active_org_slug"] = membership.organization.slug
    s.save()


def _make_admin(org=None):
    org = org or OrganizationFactory()
    return MembershipFactory(user=UserFactory(), organization=org, role=Membership.Role.ADMIN)


def _make_member(org=None):
    org = org or OrganizationFactory()
    return MembershipFactory(user=UserFactory(), organization=org, role=Membership.Role.MEMBER)


def _confirmed_invoice(org, customer, issue_date=None):
    NCFSequenceFactory(organization=org, ncf_type=31)
    inv = SalesDocumentFactory(
        organization=org,
        customer=customer,
        ncf_type=31,
        status=SalesDocument.Status.DRAFT,
        issue_date=issue_date or date.today(),
    )
    SalesDocumentItemFactory(
        document=inv,
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
    )
    inv.recompute_totals()
    inv.refresh_from_db()
    NCFService.confirm(inv)
    inv.refresh_from_db()
    return inv


# ---- Aging -------------------------------------------------------------------

@pytest.mark.django_db
class TestAgingReportView:

    def test_requires_login(self, client):
        assert client.get(reverse("sales:report_aging")).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(reverse("sales:report_aging")).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(reverse("sales:report_aging")).status_code == 200

    def test_empty_state(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(reverse("sales:report_aging"))
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        _confirmed_invoice(org_b, CustomerFactory(organization=org_b))
        _login(client, ms_a)
        r = client.get(reverse("sales:report_aging"))
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_bad_customer_param_no_500(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(reverse("sales:report_aging"), {"customer": "9999"})
        assert r.status_code in (200, 404)


# ---- SalesByPeriod -----------------------------------------------------------

@pytest.mark.django_db
class TestReportSalesByPeriodView:

    def test_requires_login(self, client):
        assert client.get(reverse("sales:report_sales_period")).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(reverse("sales:report_sales_period")).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(reverse("sales:report_sales_period")).status_code == 200

    def test_empty_state_with_year(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(reverse("sales:report_sales_period"), {"year": "2020"})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        year = date.today().year
        _confirmed_invoice(org_b, CustomerFactory(organization=org_b), issue_date=date(year, 1, 15))
        _login(client, ms_a)
        r = client.get(reverse("sales:report_sales_period"), {"year": str(year)})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_date_filter_wrong_month_empty(self, client):
        ms = _make_admin()
        org = ms.organization
        year = date.today().year
        _confirmed_invoice(org, CustomerFactory(organization=org), issue_date=date(year, 1, 15))
        _login(client, ms)
        r = client.get(reverse("sales:report_sales_period"), {"year": str(year), "month": "2"})
        assert r.status_code == 200
        assert r.context["rows"] == []


# ---- ITBIS -------------------------------------------------------------------

@pytest.mark.django_db
class TestReportITBISView:

    def test_requires_login(self, client):
        assert client.get(reverse("sales:report_itbis")).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(reverse("sales:report_itbis")).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(reverse("sales:report_itbis")).status_code == 200

    def test_empty_state_with_year(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(reverse("sales:report_itbis"), {"year": "2010"})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        year = date.today().year
        _confirmed_invoice(org_b, CustomerFactory(organization=org_b), issue_date=date(year, 1, 10))
        _login(client, ms_a)
        r = client.get(reverse("sales:report_itbis"), {"year": str(year)})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_date_filter_wrong_month_empty(self, client):
        ms = _make_admin()
        org = ms.organization
        year = date.today().year
        _confirmed_invoice(org, CustomerFactory(organization=org), issue_date=date(year, 1, 10))
        _login(client, ms)
        r = client.get(reverse("sales:report_itbis"), {"year": str(year), "month": "2"})
        assert r.status_code == 200
        assert r.context["rows"] == []


# ---- NCFType -----------------------------------------------------------------

@pytest.mark.django_db
class TestReportSalesByNCFTypeView:

    def test_requires_login(self, client):
        assert client.get(reverse("sales:report_ncf_type")).status_code == 302

    def test_member_forbidden(self, client):
        ms = _make_member()
        _login(client, ms)
        assert client.get(reverse("sales:report_ncf_type")).status_code == 403

    def test_admin_200(self, client):
        ms = _make_admin()
        _login(client, ms)
        assert client.get(reverse("sales:report_ncf_type")).status_code == 200

    def test_empty_state_with_month_year(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.get(reverse("sales:report_ncf_type"), {"year": "2010", "month": "1"})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        year = date.today().year
        _confirmed_invoice(org_b, CustomerFactory(organization=org_b), issue_date=date(year, 1, 5))
        _login(client, ms_a)
        r = client.get(reverse("sales:report_ncf_type"), {"year": str(year), "month": "1"})
        assert r.status_code == 200
        assert r.context["rows"] == []

    def test_correct_month_has_rows(self, client):
        ms = _make_admin()
        org = ms.organization
        year = date.today().year
        _confirmed_invoice(org, CustomerFactory(organization=org), issue_date=date(year, 1, 5))
        _login(client, ms)
        r = client.get(reverse("sales:report_ncf_type"), {"year": str(year), "month": "1"})
        assert r.status_code == 200
        assert len(r.context["rows"]) >= 1

    def test_wrong_month_empty(self, client):
        ms = _make_admin()
        org = ms.organization
        year = date.today().year
        _confirmed_invoice(org, CustomerFactory(organization=org), issue_date=date(year, 1, 5))
        _login(client, ms)
        r = client.get(reverse("sales:report_ncf_type"), {"year": str(year), "month": "6"})
        assert r.status_code == 200
        assert r.context["rows"] == []
