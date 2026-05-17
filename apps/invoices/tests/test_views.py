"""
Tests for invoice views — status transitions, permission guards, DGII rules.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, UserFactory, OrganizationFactory
from apps.invoices.models import Invoice
from apps.invoices.services import NCFService
from apps.invoices.tests.factories import (
    CustomerFactory, InvoiceFactory, InvoiceItemFactory, NCFSequenceFactory,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def login(client, user):
    client.force_login(user)


def make_member(role=Membership.Role.ADMIN):
    """Create an org + user + membership. Returns (user, org, membership)."""
    org = OrganizationFactory()
    user = UserFactory()
    membership = MembershipFactory(user=user, organization=org, role=role)
    return user, org, membership


def set_active_org(client, org):
    session = client.session
    session["active_org_slug"] = org.slug
    session.save()


# ── Customer views ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerViews:

    def test_customer_list_requires_login(self, client):
        resp = client.get(reverse("invoices:customer_list"))
        assert resp.status_code in (302, 403)

    def test_customer_list_accessible_to_member(self, client):
        user, org, _ = make_member(Membership.Role.MEMBER)
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("invoices:customer_list"))
        assert resp.status_code == 200

    def test_create_customer_via_post(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("invoices:customer_list"), {
            "name": "Empresa Test S.R.L.",
            "id_type": "RNC",
            "rnc_cedula": "101234565",
            "email": "test@empresa.com",
            "phone": "",
            "address": "", "city": "", "province": "",
            "country": "República Dominicana",
            "default_ncf_type": 31,
            "notes": "",
        })
        assert resp.status_code == 302
        from apps.invoices.models import Customer
        assert Customer.objects.filter(organization=org, name="Empresa Test S.R.L.").exists()


# ── Invoice views ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestInvoiceListView:

    def test_invoice_list_shows_org_invoices(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        customer = CustomerFactory(organization=org)
        invoice = InvoiceFactory(organization=org, customer=customer)
        resp = client.get(reverse("invoices:invoice_list"))
        assert resp.status_code == 200


@pytest.mark.django_db
class TestInvoiceConfirmView:

    def _setup(self):
        user, org, _ = make_member()
        seq = NCFSequenceFactory(organization=org, ncf_type=31)
        customer = CustomerFactory(organization=org, rnc_cedula="101234567")
        invoice = InvoiceFactory(organization=org, customer=customer, ncf_type=31)
        InvoiceItemFactory(invoice=invoice, unit_price=Decimal("1000.00"))
        return user, org, invoice

    def test_confirm_assigns_encf(self, client):
        user, org, invoice = self._setup()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("invoices:invoice_confirm", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.encf == "E310000000001"
        assert invoice.status == Invoice.Status.CONFIRMED

    def test_confirm_requires_login(self, client):
        _, org, invoice = self._setup()
        resp = client.post(reverse("invoices:invoice_confirm", kwargs={"pk": invoice.pk}))
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestInvoiceCancelView:

    def test_cancel_sets_status(self, client):
        user, org, _ = make_member()
        seq = NCFSequenceFactory(organization=org, ncf_type=31)
        customer = CustomerFactory(organization=org, rnc_cedula="101234567")
        invoice = InvoiceFactory(organization=org, customer=customer, ncf_type=31)
        InvoiceItemFactory(invoice=invoice)
        login(client, user)
        set_active_org(client, org)
        NCFService.confirm(invoice)
        resp = client.post(reverse("invoices:invoice_cancel", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.status == Invoice.Status.CANCELLED


@pytest.mark.django_db
class TestInvoiceDeleteView:

    def test_delete_draft_succeeds(self, client):
        user, org, _ = make_member()
        customer = CustomerFactory(organization=org)
        invoice = InvoiceFactory(organization=org, customer=customer, status=Invoice.Status.DRAFT)
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("invoices:invoice_delete", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        assert not Invoice.objects.filter(pk=invoice.pk).exists()

    def test_delete_confirmed_fails(self, client):
        user, org, _ = make_member()
        seq = NCFSequenceFactory(organization=org, ncf_type=31)
        customer = CustomerFactory(organization=org, rnc_cedula="101234567")
        invoice = InvoiceFactory(organization=org, customer=customer, ncf_type=31)
        InvoiceItemFactory(invoice=invoice)
        NCFService.confirm(invoice)
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("invoices:invoice_delete", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        assert Invoice.objects.filter(pk=invoice.pk).exists()


# ── Report views ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestReportViews:

    def test_report_607_returns_txt(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(
            reverse("invoices:report_607"),
            {"month": "1", "year": "2026"},
        )
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/plain")

    def test_report_608_returns_txt(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(
            reverse("invoices:report_608"),
            {"month": "1", "year": "2026"},
        )
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/plain")

    def test_report_requires_month_year(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("invoices:report_607"))
        assert resp.status_code == 302  # redirect with error message


# ── CustomerQuickCreateForm ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerQuickCreateForm:
    def _form(self, data, org=None):
        from apps.invoices.forms import CustomerQuickCreateForm
        if org is None:
            from apps.accounts.tests.factories import OrganizationFactory
            org = OrganizationFactory()
        return CustomerQuickCreateForm(data, organization=org)

    def test_valid_rnc(self):
        form = self._form({"name": "Empresa X", "id_type": "RNC", "rnc_cedula": "101234563"})
        assert form.is_valid(), form.errors

    def test_missing_name(self):
        form = self._form({"id_type": "RNC", "rnc_cedula": "101234563"})
        assert not form.is_valid()
        assert "name" in form.errors

    def test_invalid_rnc_checksum(self):
        form = self._form({"name": "X", "id_type": "RNC", "rnc_cedula": "000000000"})
        assert not form.is_valid()
        assert "rnc_cedula" in form.errors

    def test_duplicate_rnc_same_org(self):
        from apps.invoices.tests.factories import CustomerFactory
        c = CustomerFactory(rnc_cedula="101234563", id_type="RNC")
        form = self._form(
            {"name": "Otro", "id_type": "RNC", "rnc_cedula": c.rnc_cedula},
            org=c.organization,
        )
        assert not form.is_valid()
        assert "rnc_cedula" in form.errors

    def test_same_rnc_different_org(self):
        from apps.invoices.tests.factories import CustomerFactory
        CustomerFactory(rnc_cedula="101234563", id_type="RNC")
        form = self._form({"name": "Y", "id_type": "RNC", "rnc_cedula": "101234563"})
        assert form.is_valid(), form.errors


# ── CustomerSearchView ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerSearchView:

    def _get(self, client, org, q=""):
        from django.urls import reverse
        return client.get(reverse("invoices:customer_search"), {"q": q})

    def test_requires_login(self, client):
        from apps.accounts.tests.factories import OrganizationFactory
        org = OrganizationFactory()
        resp = client.get("/invoices/htmx/customers/search/")
        assert resp.status_code in (302, 403)

    def test_returns_200(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._get(client, org)
        assert resp.status_code == 200

    def test_scope_to_org(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        from apps.invoices.tests.factories import CustomerFactory
        c_mine = CustomerFactory(organization=org, name="Mi Cliente")
        c_other = CustomerFactory(name="Otro Org")
        resp = self._get(client, org)
        content = resp.content.decode()
        assert "Mi Cliente" in content
        assert "Otro Org" not in content

    def test_search_filters_by_name(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        from apps.invoices.tests.factories import CustomerFactory
        CustomerFactory(organization=org, name="Ferretería Central")
        CustomerFactory(organization=org, name="Supermercado Norte")
        resp = self._get(client, org, q="Ferretería")
        content = resp.content.decode()
        assert "Ferretería Central" in content
        assert "Supermercado Norte" not in content

    def test_returns_at_most_25_rows(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        from apps.invoices.tests.factories import CustomerFactory
        for i in range(30):
            CustomerFactory(organization=org)
        resp = self._get(client, org)
        # count <tr> tags in response
        assert resp.content.decode().count("<tr") <= 26  # 25 data rows + possible empty-state


# ── CustomerQuickCreateView ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerQuickCreateView:

    def _post(self, client, org, data):
        import urllib.parse
        from django.urls import reverse
        return client.post(reverse("invoices:customer_quick_create"),
                           urllib.parse.urlencode(data),
                           content_type="application/x-www-form-urlencoded",
                           HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_requires_login(self, client):
        resp = client.post("/invoices/htmx/customers/create/", {})
        assert resp.status_code in (302, 403)

    def test_creates_customer_returns_json(self, client):
        import json
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._post(client, org, {
            "name": "Empresa Nueva S.R.L.",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "pk" in data
        assert data["name"] == "Empresa Nueva S.R.L."
        assert data["rnc_cedula"] == "101234563"
        assert "default_ncf_type" in data

    def test_invalid_returns_422(self, client):
        import json
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._post(client, org, {
            "name": "",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
        })
        assert resp.status_code == 422
        data = json.loads(resp.content)
        assert "errors" in data
        assert "name" in data["errors"]

    def test_duplicate_rnc_returns_422(self, client):
        import json
        from apps.invoices.tests.factories import CustomerFactory
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        CustomerFactory(organization=org, rnc_cedula="101234563", id_type="RNC")
        resp = self._post(client, org, {
            "name": "Otro",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
        })
        assert resp.status_code == 422
        data = json.loads(resp.content)
        assert "errors" in data

    def test_viewer_cannot_create(self, client):
        user, org, _ = make_member(Membership.Role.VIEWER)
        login(client, user)
        set_active_org(client, org)
        resp = self._post(client, org, {
            "name": "X",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
        })
        assert resp.status_code in (302, 403)
