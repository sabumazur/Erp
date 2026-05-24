"""
Tests for invoice views — status transitions, permission guards, DGII rules.
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory, OrganizationFactory
from apps.core.models import Module
from apps.items.tests.factories import ItemFactory
from apps.sales.forms import InvoiceItemForm, SaleOrderForm
from apps.sales.models import SalesDocument
from apps.sales.services import NCFService
from apps.sales.tests.factories import (
    CustomerFactory, SalesDocumentFactory, SalesDocumentItemFactory, NCFSequenceFactory,
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
        resp = client.get(reverse("sales:customer_list"))
        assert resp.status_code in (302, 403)

    def test_customer_list_accessible_to_member(self, client):
        user, org, _ = make_member(Membership.Role.MEMBER)
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("sales:customer_list"))
        assert resp.status_code == 200

    def test_create_customer_via_post(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:customer_list"), {
            "name": "Empresa Test S.R.L.",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
            "email": "test@empresa.com",
            "phone": "",
            "address": "", "city": "", "province": "",
            "country": "República Dominicana",
            "default_ncf_type": 31,
            "notes": "",
        })
        assert resp.status_code == 302
        from apps.sales.models import Customer
        assert Customer.objects.filter(organization=org, name="Empresa Test S.R.L.").exists()


# ── Invoice views ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestInvoiceListView:

    def test_invoice_list_shows_org_invoices(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        customer = CustomerFactory(organization=org)
        invoice = SalesDocumentFactory(organization=org, customer=customer)
        resp = client.get(reverse("sales:invoice_list"))
        assert resp.status_code == 200

    def test_invoice_list_denied_without_sales_module(self, client):
        user, org, membership = make_member(Membership.Role.MEMBER)
        team = TeamFactory(organization=org)
        team.modules.add(Module.objects.create(name="Inventory", slug="inventory"))
        membership.team = team
        membership.save(update_fields=["team", "updated_at"])
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("sales:invoice_list"))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestInvoiceConfirmView:

    def _setup(self):
        user, org, _ = make_member()
        seq = NCFSequenceFactory(organization=org, ncf_type=31)
        customer = CustomerFactory(organization=org, rnc_cedula="101234567")
        invoice = SalesDocumentFactory(organization=org, customer=customer, ncf_type=31)
        SalesDocumentItemFactory(document=invoice, unit_price=Decimal("1000.00"))
        return user, org, invoice

    def test_confirm_assigns_encf(self, client):
        user, org, invoice = self._setup()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:invoice_confirm", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.encf == "E310000000001"
        assert invoice.status == SalesDocument.Status.CONFIRMED

    def test_confirm_requires_login(self, client):
        _, org, invoice = self._setup()
        resp = client.post(reverse("sales:invoice_confirm", kwargs={"pk": invoice.pk}))
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestInvoiceCancelView:

    def test_cancel_sets_status(self, client):
        user, org, _ = make_member()
        seq = NCFSequenceFactory(organization=org, ncf_type=31)
        customer = CustomerFactory(organization=org, rnc_cedula="101234567")
        invoice = SalesDocumentFactory(organization=org, customer=customer, ncf_type=31)
        SalesDocumentItemFactory(document=invoice)
        login(client, user)
        set_active_org(client, org)
        NCFService.confirm(invoice)
        resp = client.post(reverse("sales:invoice_cancel", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        invoice.refresh_from_db()
        assert invoice.status == SalesDocument.Status.CANCELLED


@pytest.mark.django_db
class TestInvoiceDeleteView:

    def test_delete_draft_succeeds(self, client):
        user, org, _ = make_member()
        customer = CustomerFactory(organization=org)
        invoice = SalesDocumentFactory(organization=org, customer=customer, status=SalesDocument.Status.DRAFT)
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:invoice_delete", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        assert not SalesDocument.objects.filter(pk=invoice.pk).exists()

    def test_delete_confirmed_fails(self, client):
        user, org, _ = make_member()
        seq = NCFSequenceFactory(organization=org, ncf_type=31)
        customer = CustomerFactory(organization=org, rnc_cedula="101234567")
        invoice = SalesDocumentFactory(organization=org, customer=customer, ncf_type=31)
        SalesDocumentItemFactory(document=invoice)
        NCFService.confirm(invoice)
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:invoice_delete", kwargs={"pk": invoice.pk}))
        assert resp.status_code == 302
        assert SalesDocument.objects.filter(pk=invoice.pk).exists()


@pytest.mark.django_db
class TestInvoiceRouteDocumentTypeIsolation:

    @pytest.mark.parametrize(
        ("route_name", "method", "data"),
        [
            ("invoice_detail", "get", {}),
            ("invoice_edit", "get", {}),
            ("invoice_confirm", "post", {}),
            ("invoice_send", "post", {}),
            ("invoice_pay", "post", {"amount": "1.00", "date": "2026-05-24", "method": "TRANSFER"}),
            ("invoice_cancel", "post", {}),
            ("invoice_delete", "post", {}),
            ("credit_note_create", "get", {}),
            ("invoice_pdf", "get", {}),
            ("invoice_print", "get", {}),
        ],
    )
    def test_invoice_routes_reject_quotation_ids(self, client, route_name, method, data):
        user, org, _ = make_member()
        quotation = SalesDocumentFactory(
            organization=org,
            customer=CustomerFactory(organization=org),
            doc_type=SalesDocument.DocType.QUOTATION,
        )
        login(client, user)
        set_active_org(client, org)
        url = reverse(f"sales:{route_name}", kwargs={"pk": quotation.pk})
        response = getattr(client, method)(url, data)
        assert response.status_code == 404


@pytest.mark.django_db
class TestCreditNoteCreateView:

    def test_creates_note_against_issued_invoice(self, client):
        user, org, _ = make_member()
        customer = CustomerFactory(organization=org)
        invoice = SalesDocumentFactory(
            organization=org,
            customer=customer,
            status=SalesDocument.Status.CONFIRMED,
            encf="E310000000001",
        )
        login(client, user)
        set_active_org(client, org)

        response = client.post(
            reverse("sales:credit_note_create", kwargs={"pk": invoice.pk}),
            {
                "ncf_type": "34",
                "issue_date": "2026-05-24",
                "due_date": "",
                "notes": "",
                "terms": "",
                "items-TOTAL_FORMS": "0",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "1000",
            },
        )

        assert response.status_code == 302
        assert SalesDocument.invoices.filter(
            ncf_type=34, encf_modified=invoice, organization=org
        ).exists()


@pytest.mark.django_db
class TestInvoiceItemCatalogValidation:

    def _form(self, item, organization, instance=None):
        return InvoiceItemForm(
            {
                "item": str(item.pk),
                "description": "Catalog line",
                "quantity": "1",
                "unit_price": "10.00",
                "itbis_rate": "RATE_18",
            },
            instance=instance,
            organization=organization,
        )

    def test_rejects_item_from_other_organization(self):
        org = OrganizationFactory()
        item = ItemFactory()
        form = self._form(item, org)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_rejects_inactive_new_item(self):
        org = OrganizationFactory()
        item = ItemFactory(organization=org, is_active=False)
        form = self._form(item, org)
        assert not form.is_valid()
        assert "item" in form.errors

    def test_existing_line_retains_deactivated_item(self):
        org = OrganizationFactory()
        document = SalesDocumentFactory(organization=org)
        item = ItemFactory(organization=org, is_active=False)
        line = SalesDocumentItemFactory(document=document, item=item)
        form = self._form(item, org, instance=line)
        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestItemQuickCreateView:

    def test_rejects_negative_price(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)
        response = client.post(
            reverse("sales:item_quick_create"),
            {
                "name": "Invalid item",
                "unit": "UNIT",
                "unit_price": "-1.00",
                "itbis_rate": "RATE_18",
            },
        )
        assert response.status_code == 422


# -- Sale order form behavior --------------------------------------------------

@pytest.mark.django_db
class TestSaleOrderFormView:

    def test_new_order_defaults_delivery_date_to_today(self):
        from datetime import date

        form = SaleOrderForm(organization=OrganizationFactory())

        assert form.initial["delivery_date"] == date.today()

    @pytest.mark.parametrize("view_name", ["sale_order_create", "sale_order_edit"])
    def test_issue_date_change_updates_delivery_date_on_create_and_edit(self, client, view_name):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        kwargs = {}
        if view_name == "sale_order_edit":
            order = SalesDocumentFactory(
                organization=org,
                customer=CustomerFactory(organization=org),
                doc_type=SalesDocument.DocType.SALE_ORDER,
            )
            kwargs["pk"] = order.pk

        response = client.get(reverse(f"sales:{view_name}", kwargs=kwargs))

        assert response.status_code == 200
        content = response.content.decode()
        assert "issueInput.addEventListener('change'" in content
        assert "deliveryInput.value = issueInput.value" in content


# -- Report views --------------------------------------------------------------

@pytest.mark.django_db
class TestReportViews:

    def test_report_607_returns_txt(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(
            reverse("sales:report_607"),
            {"month": "1", "year": "2026"},
        )
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/plain")

    def test_report_608_returns_txt(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(
            reverse("sales:report_608"),
            {"month": "1", "year": "2026"},
        )
        assert resp.status_code == 200
        assert resp["Content-Type"].startswith("text/plain")

    def test_report_requires_month_year(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("sales:report_607"))
        assert resp.status_code == 302  # redirect with error message

    def test_credit_note_reduces_customer_report_total(self, client):
        from django.utils import timezone

        user, org, _ = make_member()
        customer = CustomerFactory(organization=org)
        invoice = SalesDocumentFactory(
            organization=org,
            customer=customer,
            status=SalesDocument.Status.CONFIRMED,
            encf="E310000000001",
        )
        SalesDocumentItemFactory(document=invoice, unit_price=Decimal("100.00"), itbis_rate="EXEMPT")
        note = SalesDocumentFactory(
            organization=org,
            customer=customer,
            status=SalesDocument.Status.CONFIRMED,
            ncf_type=34,
            encf="E340000000001",
            encf_modified=invoice,
        )
        SalesDocumentItemFactory(document=note, unit_price=Decimal("40.00"), itbis_rate="EXEMPT")
        today = timezone.localdate()
        login(client, user)
        set_active_org(client, org)

        response = client.get(
            reverse("sales:report_invoices_by_customer"),
            {
                "customer": str(customer.pk),
                "date_from": today.isoformat(),
                "date_to": today.isoformat(),
            },
        )

        assert response.status_code == 200
        assert response.context["totals"]["total"] == Decimal("60.00")


# ── CustomerQuickCreateForm ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerQuickCreateForm:
    def _form(self, data, org=None):
        from apps.sales.forms import CustomerQuickCreateForm
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
        from apps.sales.tests.factories import CustomerFactory
        c = CustomerFactory(rnc_cedula="101234563", id_type="RNC")
        form = self._form(
            {"name": "Otro", "id_type": "RNC", "rnc_cedula": c.rnc_cedula},
            org=c.organization,
        )
        assert not form.is_valid()
        assert "rnc_cedula" in form.errors

    def test_same_rnc_different_org(self):
        from apps.sales.tests.factories import CustomerFactory
        CustomerFactory(rnc_cedula="101234563", id_type="RNC")
        form = self._form({"name": "Y", "id_type": "RNC", "rnc_cedula": "101234563"})
        assert form.is_valid(), form.errors


# ── CustomerSearchView ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerSearchView:

    def _get(self, client, org, q=""):
        from django.urls import reverse
        return client.get(reverse("sales:customer_search"), {"q": q})

    def test_requires_login(self, client):
        from apps.accounts.tests.factories import OrganizationFactory
        org = OrganizationFactory()
        resp = client.get("/sales/htmx/customers/search/")
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
        from apps.sales.tests.factories import CustomerFactory
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
        from apps.sales.tests.factories import CustomerFactory
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
        from apps.sales.tests.factories import CustomerFactory
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
        return client.post(reverse("sales:customer_quick_create"),
                           urllib.parse.urlencode(data),
                           content_type="application/x-www-form-urlencoded",
                           HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_requires_login(self, client):
        resp = client.post("/sales/htmx/customers/create/", {})
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
        from apps.sales.tests.factories import CustomerFactory
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


# ── ItemSearchView ────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestItemSearchView:

    def _get(self, client, org, q=""):
        return client.get(reverse("sales:item_search"), {"q": q})

    def test_requires_login(self, client):
        resp = client.get(reverse("sales:item_search"))
        assert resp.status_code in (302, 403)

    def test_returns_200(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = self._get(client, org)
        assert resp.status_code == 200

    def test_scope_to_org(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        Item.objects.create(
            organization=org, name="Mi Artículo",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("100.00"), is_active=True,
        )
        other_org = OrganizationFactory()
        Item.objects.create(
            organization=other_org, name="Otro Org",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("50.00"), is_active=True,
        )
        resp = self._get(client, org)
        content = resp.content.decode()
        assert "Mi Artículo" in content
        assert "Otro Org" not in content

    def test_search_filters_by_name(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        Item.objects.create(
            organization=org, name="Consultoría Web",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("200.00"), is_active=True,
        )
        Item.objects.create(
            organization=org, name="Mantenimiento",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("150.00"), is_active=True,
        )
        resp = self._get(client, org, q="Consultoría")
        content = resp.content.decode()
        assert "Consultoría Web" in content
        assert "Mantenimiento" not in content

    def test_excludes_purchase_only_items(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        Item.objects.create(
            organization=org, name="Solo Compra",
            item_type=Item.ItemType.PURCHASE,
            unit_price=Decimal("50.00"), is_active=True,
        )
        resp = self._get(client, org)
        assert "Solo Compra" not in resp.content.decode()

    def test_returns_at_most_50_rows(self, client):
        from decimal import Decimal
        from apps.items.models import Item
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        for i in range(60):
            Item.objects.create(
                organization=org, name=f"Artículo {i:03d}",
                item_type=Item.ItemType.SALE,
                unit_price=Decimal("10.00"), is_active=True,
            )
        resp = self._get(client, org)
        assert resp.content.decode().count("<tr") <= 50
