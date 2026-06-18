"""
Tests for invoice views — status transitions, permission guards, DGII rules.
"""
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.template import Context, Template
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, TeamFactory, UserFactory, OrganizationFactory
from apps.core.models import Module
from apps.items.tests.factories import ItemFactory
from apps.sales.forms import (
    CreditNoteForm,
    CustomerForm,
    InvoiceForm,
    InvoiceItemForm,
    PaymentHeaderForm,
    QuotationForm,
    SaleOrderForm,
)
from apps.sales.models import CustomerDepartment, SalesDocument
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


def render_crispy_form(form):
    return Template("{% load crispy_forms_tags %}{% crispy form %}").render(
        Context({"form": form})
    )


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

    def test_customer_list_does_not_accept_post(self, client):
        """CustomerListView no longer handles POST — create moved to customer_create."""
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:customer_list"), {"name": "X"})
        assert resp.status_code == 405

    def test_customer_form_rnc_lookup_attrs(self):
        form = CustomerForm()
        attrs = form.fields["rnc_cedula"].widget.attrs

        assert attrs["hx-get"] == reverse("sales:rnc_lookup")
        assert attrs["hx-trigger"] == "blur changed"
        assert attrs["hx-include"] == "closest form"
        assert attrs["hx-target"] == "#rnc-lookup-result"
        assert attrs["hx-indicator"] == "#rnc-lookup-spinner"

    def test_customer_form_id_type_choices_are_only_rnc_and_cedula(self):
        form = CustomerForm()

        assert list(form.fields["id_type"].choices) == [
            ("RNC", "RNC"),
            ("CED", "Cédula"),
        ]

    def test_customer_picker_quick_create_offers_only_rnc_and_cedula(self):
        source = Path("templates/sales/partials/customer_picker_modal.html").read_text(
            encoding="utf-8"
        )

        assert 'option value="RNC"' in source
        assert 'option value="CED"' in source
        assert 'option value="PAS"' not in source
        assert 'option value="EXT"' not in source

    def test_edit_htmx_get_returns_full_page_not_partial(self, client):
        """After removing HTMX modal, an HTMX GET must return the full page (200)."""
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        customer = CustomerFactory(organization=org)
        resp = client.get(
            reverse("sales:customer_edit", args=[customer.pk]),
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        # Must NOT be a partial: full page has form in context
        assert "form" in resp.context

    def test_edit_post_redirects_to_customer_detail(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        # Use a fixed known-valid RNC to avoid factory sequence producing repeated digits.
        customer = CustomerFactory(organization=org, rnc_cedula="101234563", id_type="RNC")
        resp = client.post(
            reverse("sales:customer_edit", args=[customer.pk]),
            {
                "name": "Updated Name S.R.L.",
                "id_type": "RNC",
                "rnc_cedula": "101234563",
                "email": "",
                "phone": "",
                "contact_name": "", "contact_number": "",
                "address": "", "city": "", "province": "",
                "country": "República Dominicana",
                "default_ncf_type": 31,
                "notes": "",
                "change_reason": "",
            },
        )
        assert resp.status_code == 302
        assert resp["Location"] == reverse("sales:customer_detail", args=[customer.pk])

    def test_edit_context_has_smart_buttons(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        customer = CustomerFactory(organization=org)
        resp = client.get(reverse("sales:customer_edit", args=[customer.pk]))
        assert resp.status_code == 200
        assert "smart_buttons" in resp.context
        assert "invoice_count" in resp.context["smart_buttons"]
        assert "payment_count" in resp.context["smart_buttons"]
        assert "dept_count" in resp.context["smart_buttons"]


@pytest.mark.django_db
class TestRNCLookupView:
    def _request(self, client, monkeypatch, result, params=None):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        cache.clear()

        calls = []

        def fake_lookup(value, id_type):
            calls.append((value, id_type))
            return result

        monkeypatch.setattr("apps.sales.validators.lookup_name", fake_lookup)
        response = client.get(reverse("sales:rnc_lookup"), params or {
            "id_type": "RNC",
            "rnc_cedula": "1-01-23456-3",
        })
        return response, calls

    def test_lookup_found_triggers_event_with_name_and_normalized_value(self, client, monkeypatch):
        response, calls = self._request(client, monkeypatch, ("EMPRESA TEST SRL", "DGII"))

        trigger = json.loads(response.headers["HX-Trigger"])

        assert calls == [("1-01-23456-3", "RNC")]
        assert trigger["rncFound"]["name"] == "EMPRESA TEST SRL"
        assert trigger["rncFound"]["value"] == "1-01-23456-3"
        assert trigger["rncFound"]["normalized_value"] == "101234563"

    def test_lookup_missing_value_returns_no_trigger(self, client, monkeypatch):
        response, calls = self._request(
            client,
            monkeypatch,
            ("IGNORED", "DGII"),
            {"id_type": "RNC", "rnc_cedula": ""},
        )

        assert response.content == b""
        assert "HX-Trigger" not in response.headers
        assert calls == []

    def test_lookup_not_found_triggers_warning_event(self, client, monkeypatch):
        response, calls = self._request(client, monkeypatch, (None, ""))

        trigger = json.loads(response.headers["HX-Trigger"])

        assert calls == [("1-01-23456-3", "RNC")]
        assert trigger == {"rncNotFound": {"value": "1-01-23456-3", "normalized_value": "101234563"}}

    def test_lookup_found_result_is_cached(self, client, monkeypatch):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        cache.clear()
        calls = []

        def fake_lookup(value, id_type):
            calls.append((value, id_type))
            return "EMPRESA TEST SRL", "DGII"

        monkeypatch.setattr("apps.sales.validators.lookup_name", fake_lookup)
        url = reverse("sales:rnc_lookup")
        params = {"id_type": "RNC", "rnc_cedula": "101234563"}

        first = client.get(url, params)
        second = client.get(url, params)

        assert first.headers["HX-Trigger"] == second.headers["HX-Trigger"]
        assert calls == [("101234563", "RNC")]

    def test_rnc_lookup_response_body_is_empty_on_found(self, client, monkeypatch):
        """Response body must be empty so HTMX does not visually swap stale content."""
        response, _ = self._request(client, monkeypatch, ("EMPRESA TEST SRL", "DGII"))
        assert response.content == b""

    def test_rnc_lookup_response_body_is_empty_on_not_found(self, client, monkeypatch):
        """Not-found response body must also be empty."""
        response, _ = self._request(client, monkeypatch, (None, ""))
        assert response.content == b""

    def test_rnc_lookup_always_returns_200(self, client, monkeypatch):
        """HTMX only processes HX-Trigger headers on HTTP 200."""
        found, _ = self._request(client, monkeypatch, ("EMPRESA TEST SRL", "DGII"))
        not_found, _ = self._request(client, monkeypatch, (None, ""))
        assert found.status_code == 200
        assert not_found.status_code == 200

    def test_rnc_lookup_cached_second_request_returns_identical_trigger(self, client, monkeypatch):
        """A second request for the same RNC (simulating duplicate blur from Swal focus-steal)
        returns the identical HX-Trigger — the Swal.isVisible() guard in JS is what prevents
        the second event from replacing the open dialog."""
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        cache.clear()
        calls = []

        def fake_lookup(value, id_type):
            calls.append((value, id_type))
            return "EMPRESA TEST SRL", "DGII"

        monkeypatch.setattr("apps.sales.validators.lookup_name", fake_lookup)
        url = reverse("sales:rnc_lookup")
        params = {"id_type": "RNC", "rnc_cedula": "101234563"}

        resp1 = client.get(url, params)
        resp2 = client.get(url, params)  # duplicate request — simulates second blur

        assert resp1.content == b""
        assert resp2.content == b""
        assert json.loads(resp1.headers["HX-Trigger"]) == json.loads(resp2.headers["HX-Trigger"])
        assert len(calls) == 1  # only one real DGII call; second served from cache


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

    def test_customer_field_is_plain_hidden_input(self):
        form = SaleOrderForm(organization=OrganizationFactory())
        attrs = form.fields["customer"].widget.attrs

        assert attrs["id"] == "id_customer"
        assert "hx-get" not in attrs
        assert "hx-target" not in attrs

    def test_payment_header_customer_uses_picker_and_outstanding_invoice_htmx(self):
        form = PaymentHeaderForm(organization=OrganizationFactory())

        html = render_crispy_form(form)
        attrs = form.fields["customer"].widget.attrs

        assert attrs["id"] == "id_customer"
        assert attrs["hx-get"] == reverse("sales:payment_outstanding_invoices")
        assert attrs["hx-trigger"] == "change"
        assert attrs["hx-target"] == "#allocation-tbody"
        assert attrs["hx-swap"] == "innerHTML"
        assert attrs["hx-include"] == "this"
        assert 'type="hidden"' in html
        assert 'id="customer-display-text"' in html
        assert "openCustomerPicker()" in html
        assert '<select name="customer"' not in html

    @pytest.mark.parametrize(
        ("form_cls", "expected"),
        [
            (
                InvoiceForm,
                [
                    ("opt-terms-wrap", "Añadir términos"),
                    ("opt-notes-wrap", "Añadir notas"),
                ],
            ),
            (
                QuotationForm,
                [
                    ("opt-terms-wrap", "Añadir términos"),
                    ("opt-notes-wrap", "Añadir notas"),
                ],
            ),
            (
                SaleOrderForm,
                [("opt-notes-wrap", "Añadir notas")],
            ),
            (
                CreditNoteForm,
                [
                    ("opt-terms-wrap", "Añadir términos"),
                    ("opt-notes-wrap", "Añadir notas"),
                ],
            ),
            (
                PaymentHeaderForm,
                [("opt-notes-wrap", "Añadir notas")],
            ),
        ],
    )
    def test_document_optional_fields_render_as_header_chips(self, form_cls, expected):
        kwargs = {}
        if form_cls is not CreditNoteForm:
            kwargs["organization"] = OrganizationFactory()
        form = form_cls(**kwargs)

        html = render_crispy_form(form)

        assert html.count('id="opt-add-row"') == 1
        assert html.count("doc-optfields") >= 1
        for target, label in expected:
            assert f'data-target="{target}"' in html
            assert f'id="{target}"' in html
            assert label in html

    @pytest.mark.parametrize(
        "template_path",
        [
            "templates/sales/invoice_form.html",
            "templates/sales/sale_order_form.html",
        ],
    )
    def test_sales_document_templates_remove_legacy_notes_accordion(self, template_path):
        source = Path(template_path).read_text(encoding="utf-8")

        assert "doc-notes-acc" not in source
        assert "doc-bottom-grid mb-3" not in source
        assert 'class="d-flex justify-content-end mb-3"' in source
        assert 'class="doc-totals-card"' in source
        assert 'style="width:360px"' not in source
        for total_id in [
            "grand-subtotal",
            "grand-itbis18",
            "grand-itbis16",
            "grand-total",
        ]:
            assert total_id in source

    def test_payment_form_template_loads_optional_fields_script(self):
        source = Path("templates/sales/payment_form.html").read_text(encoding="utf-8")

        assert "sales/partials/item_js.html" in source

    def test_payment_form_template_uses_doc_chrome(self):
        source = Path("templates/sales/payment_form.html").read_text(encoding="utf-8")

        assert "kv-card" not in source
        assert 'class="app-table-wrap doc-order-card mb-3"' in source
        assert 'class="app-table-wrap doc-lines-card mb-3"' in source

    def test_payment_create_uses_existing_customer_picker_without_quick_create(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("sales:payment_create"))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'id="customerPickerModal"' in content
        assert 'id="customer-display-text"' in content
        assert 'id="id_customer"' in content
        assert 'allow_create=0' in content
        assert '<select name="customer"' not in content
        assert "CUSTOMER_QUICK_CREATE_URL" not in content
        assert "Nuevo cliente" not in content
        assert "Crear y seleccionar" not in content

    def test_customer_picker_empty_state_hides_create_link_when_disabled(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        disabled = client.get(
            reverse("sales:customer_search"),
            {"q": "cliente-inexistente", "allow_create": "0"},
        )
        default = client.get(reverse("sales:customer_search"), {"q": "cliente-inexistente"})

        assert disabled.status_code == 200
        assert "No se encontraron clientes" in disabled.content.decode()
        assert "Crear uno nuevo" not in disabled.content.decode()
        assert "Crear uno nuevo" in default.content.decode()

    def test_department_options_are_scoped_to_selected_customer(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        customer = CustomerFactory(organization=org)
        other_customer = CustomerFactory(organization=org)
        dept = CustomerDepartment.objects.create(
            organization=org,
            customer=customer,
            name="Sucursal Norte",
            is_active=True,
        )
        CustomerDepartment.objects.create(
            organization=org,
            customer=other_customer,
            name="Sucursal Sur",
            is_active=True,
        )
        CustomerDepartment.objects.create(
            organization=org,
            customer=customer,
            name="Sucursal Inactiva",
            is_active=False,
        )

        resp = client.get(
            reverse("sales:departments_for_customer"),
            {"customer": customer.pk},
        )

        assert resp.status_code == 200
        content = resp.content.decode()
        assert f'value="{dept.pk}"' in content
        assert "Sucursal Norte" in content
        assert "Sucursal Sur" not in content
        assert "Sucursal Inactiva" not in content

    def test_sale_order_department_field_is_disabled_without_customer_departments(self):
        org = OrganizationFactory()
        customer = CustomerFactory(organization=org)

        blank_form = SaleOrderForm(organization=org)
        customer_form = SaleOrderForm(data={"customer": customer.pk}, organization=org)

        assert blank_form.fields["department"].widget.attrs["disabled"] == "disabled"
        assert customer_form.fields["department"].widget.attrs["disabled"] == "disabled"

    def test_sale_order_department_field_is_enabled_for_customer_with_departments(self):
        org = OrganizationFactory()
        customer = CustomerFactory(organization=org)
        CustomerDepartment.objects.create(
            organization=org,
            customer=customer,
            name="Sucursal Norte",
            is_active=True,
        )

        form = SaleOrderForm(data={"customer": customer.pk}, organization=org)

        assert "disabled" not in form.fields["department"].widget.attrs

    def test_sale_order_template_disables_department_until_customer_has_options(self):
        source = Path("templates/sales/sale_order_form.html").read_text(encoding="utf-8")

        assert "setDepartmentDisabled(deptSel, true)" in source
        assert "hasDepartmentOptions(deptSel)" in source
        assert "setDepartmentDisabled(deptSel, !hasDepartmentOptions(deptSel))" in source

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


# -- Sale order email view -----------------------------------------------------

@pytest.mark.django_db
class TestSaleOrderEmailView:

    def _order(self, org, *, with_item, email="customer@example.com"):
        customer = CustomerFactory(organization=org, email=email)
        order = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.SALE_ORDER,
            status=SalesDocument.Status.DRAFT,
        )
        if with_item:
            SalesDocumentItemFactory(document=order, unit_price=Decimal("1000.00"))
            order.recompute_totals()
            order.refresh_from_db()
        return order

    def test_email_empty_order_blocked(self, client, mailoutbox):
        user, org, _ = make_member()
        order = self._order(org, with_item=False)
        login(client, user)
        set_active_org(client, org)

        resp = client.post(reverse("sales:sale_order_email", kwargs={"pk": order.pk}))

        assert resp.status_code == 302
        assert resp.url == reverse("sales:sale_order_detail", kwargs={"pk": order.pk})
        assert len(mailoutbox) == 0

    def test_email_draft_with_items_sends(self, client, mailoutbox):
        user, org, _ = make_member()
        order = self._order(org, with_item=True)
        login(client, user)
        set_active_org(client, org)

        with patch("apps.sales.views.sale_orders.send_sale_order_email", return_value=True) as send:
            resp = client.post(reverse("sales:sale_order_email", kwargs={"pk": order.pk}))

        assert resp.status_code == 302
        send.assert_called_once()


# -- Report views --------------------------------------------------------------

@pytest.mark.django_db
class TestReportViews:

    def test_report_index_template_contains_scroll_overflow_guards(self):
        source = Path("templates/core/reports.html").read_text(encoding="utf-8")

        assert "#main-content { min-height: 0; overflow-x: hidden; }" in source
        assert "scrollbar-gutter" not in source
        assert "min-width: 0;" in source
        assert ".rep-card-body {" in source
        assert ".rep-grid {" in source
        assert ".rep-export-field { min-width: 0; }" in source

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

    def test_rnc_does_not_validate_check_digit(self):
        form = self._form({"name": "Empresa X", "id_type": "RNC", "rnc_cedula": "130461550"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["rnc_cedula"] == "130461550"

    def test_missing_name(self):
        form = self._form({"id_type": "RNC", "rnc_cedula": "101234563"})
        assert not form.is_valid()
        assert "name" in form.errors

    def test_repeated_rnc_is_valid_when_length_matches(self):
        form = self._form({"name": "X", "id_type": "RNC", "rnc_cedula": "000000000"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["rnc_cedula"] == "000000000"

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


# ── CustomerCreateView ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCustomerCreateView:

    def test_get_returns_200(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("sales:customer_create"))
        assert resp.status_code == 200

    def test_get_requires_login(self, client):
        resp = client.get(reverse("sales:customer_create"))
        assert resp.status_code in (302, 403)

    def test_post_valid_creates_customer_and_redirects_to_detail(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:customer_create"), {
            "name": "Farmacia Nueva S.R.L.",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
            "email": "",
            "phone": "",
            "contact_name": "", "contact_number": "",
            "address": "", "city": "", "province": "",
            "country": "República Dominicana",
            "default_ncf_type": 31,
            "notes": "",
            "change_reason": "",
        })
        from apps.sales.models import Customer
        customer = Customer.objects.get(organization=org, name="Farmacia Nueva S.R.L.")
        assert resp.status_code == 302
        assert resp["Location"] == reverse("sales:customer_detail", args=[customer.pk])

    def test_post_invalid_rnc_returns_form_errors(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        resp = client.post(reverse("sales:customer_create"), {
            "name": "Test",
            "id_type": "RNC",
            "rnc_cedula": "123",  # too short
            "country": "República Dominicana",
            "default_ncf_type": 31,
        })
        assert resp.status_code == 200
        assert resp.context["form"].errors

    def test_post_duplicate_rnc_returns_form_error(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        CustomerFactory(organization=org, rnc_cedula="101234563")
        resp = client.post(reverse("sales:customer_create"), {
            "name": "Otro Cliente",
            "id_type": "RNC",
            "rnc_cedula": "101234563",
            "country": "República Dominicana",
            "default_ncf_type": 31,
        })
        assert resp.status_code == 200
        assert "rnc_cedula" in resp.context["form"].errors
