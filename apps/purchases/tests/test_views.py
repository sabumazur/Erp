from decimal import Decimal
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.items.models import Item
from apps.items.tests.factories import ItemFactory
from apps.purchases.forms import (
    PurchaseDocumentItemForm,
    PurchaseOrderForm,
    SupplierForm,
    SupplierInvoiceForm,
    SupplierPaymentHeaderForm,
)
from apps.purchases.models import PurchaseDocument
from apps.purchases.tests.factories import PurchaseDocumentFactory, SupplierFactory


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


def render_crispy_form(form):
    return Template("{% load crispy_forms_tags %}{% crispy form %}").render(
        Context({"form": form})
    )


@pytest.mark.django_db
class TestPurchaseItemPicker:

    def test_search_excludes_sale_only_items(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        purchase_item = ItemFactory(
            organization=org,
            name="Compra Especial",
            item_type=Item.ItemType.PURCHASE,
            cost_price=Decimal("42.00"),
        )
        ItemFactory(
            organization=org,
            name="Venta Especial",
            item_type=Item.ItemType.SALE,
            cost_price=Decimal("99.00"),
        )
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:purchase_item_search"), {"q": "Especial"})

        assert response.status_code == 200
        content = response.content.decode()
        assert purchase_item.name in content
        assert "Venta Especial" not in content
        assert 'data-unit-price="42"' in content

    def test_quick_create_creates_purchase_item(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.post(
            reverse("purchases:item_quick_create"),
            {
                "name": "Nuevo insumo",
                "unit": "UNIT",
                "unit_price": "25",
                "itbis_rate": "RATE_18",
            },
        )

        assert response.status_code == 200
        item = Item.objects.get(organization=org, name="Nuevo insumo")
        assert item.item_type == Item.ItemType.PURCHASE
        assert item.cost_price == Decimal("25")
        assert response.json()["unit_price"] == "25"

    def test_purchase_forms_define_item_quick_create_url(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        supplier = SupplierFactory(organization=org)
        invoice = PurchaseDocumentFactory(
            organization=org,
            supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
        )
        login(client, user)
        set_active_org(client, org)

        create_response = client.get(reverse("purchases:po_create"))
        invoice_response = client.get(reverse("purchases:supplier_invoice_edit", args=[invoice.pk]))

        assert "window.ITEM_QUICK_CREATE_URL" in create_response.content.decode()
        assert "window.ITEM_QUICK_CREATE_URL" in invoice_response.content.decode()


@pytest.mark.django_db
class TestPurchaseOrderForm:

    def test_currency_fields_are_not_rendered_for_purchase_orders(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:po_create"))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'name="currency"' not in content
        assert 'name="exchange_rate"' not in content

    def test_purchase_order_form_excludes_currency_fields(self):
        form = PurchaseOrderForm(organization=OrganizationFactory())

        assert "currency" not in form.fields
        assert "exchange_rate" not in form.fields

    @pytest.mark.parametrize(
        "form_cls",
        [PurchaseOrderForm, SupplierInvoiceForm, SupplierPaymentHeaderForm],
    )
    def test_purchase_document_optional_notes_render_as_header_chip(self, form_cls):
        form = form_cls(organization=OrganizationFactory())

        html = render_crispy_form(form)

        assert html.count('id="opt-add-row"') == 1
        assert 'data-target="opt-notes-wrap"' in html
        assert 'id="opt-notes-wrap"' in html
        assert "Añadir notas" in html
        assert "doc-optfields-grid--single" in html

    @pytest.mark.parametrize(
        "template_path",
        [
            "templates/purchases/purchase_order_form.html",
            "templates/purchases/supplier_invoice_form.html",
        ],
    )
    def test_purchase_document_templates_remove_legacy_notes_accordion(self, template_path):
        source = Path(template_path).read_text(encoding="utf-8")
        totals = Path("templates/components/_doc_inline_totals.html").read_text(encoding="utf-8")

        # Legacy structures removed
        assert "doc-notes-acc" not in source
        assert "doc-bottom-grid mb-3" not in source
        assert 'class="d-flex justify-content-end mb-3"' not in source
        assert 'class="doc-totals-card" style="width:360px"' not in source

        # Inline totals partial wired up
        assert "_doc_inline_totals.html" in source

        # Grand total IDs live in the inline totals partial
        for total_id in ["grand-subtotal", "grand-itbis18", "grand-itbis16", "grand-total"]:
            assert total_id in totals

    def test_supplier_payment_form_template_loads_optional_fields_script(self):
        source = Path("templates/purchases/supplier_payment_form.html").read_text(
            encoding="utf-8"
        )

        assert "sales/partials/item_js.html" in source

    def test_supplier_payment_form_template_uses_doc_chrome(self):
        source = Path("templates/purchases/supplier_payment_form.html").read_text(
            encoding="utf-8"
        )

        assert "kv-card" not in source
        assert 'class="app-table-wrap doc-order-card mb-3"' in source
        assert 'class="app-table-wrap doc-lines-card mb-3"' in source

    def test_purchase_order_create_starts_with_one_item_row(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:po_create"))

        assert response.status_code == 200
        assert response.context["formset"].total_form_count() == 1

    def test_supplier_invoice_create_starts_with_one_item_row(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:supplier_invoice_create"))

        assert response.status_code == 200
        assert response.context["formset"].total_form_count() == 1

    def test_purchase_line_quantity_and_price_are_positive_integers(self):
        form = PurchaseDocumentItemForm(organization=OrganizationFactory())

        assert form.fields["quantity"].widget.attrs["step"] == "1"
        assert form.fields["quantity"].widget.attrs["min"] == "1"
        assert form.fields["unit_price"].widget.attrs["step"] == "1"
        assert form.fields["unit_price"].widget.attrs["min"] == "1"
        assert form.fields["description"].widget.attrs.get("placeholder") in (None, "")

    @pytest.mark.parametrize("field", ["quantity", "unit_price"])
    def test_purchase_line_rejects_non_positive_values(self, field):
        data = {
            "description": "Linea",
            "quantity": "1",
            "unit_price": "1",
            "itbis_rate": "RATE_18",
        }
        data[field] = "0"

        form = PurchaseDocumentItemForm(data=data, organization=OrganizationFactory())

        assert not form.is_valid()
        assert field in form.errors

    @pytest.mark.parametrize("field", ["quantity", "unit_price"])
    def test_purchase_line_rejects_decimal_values(self, field):
        data = {
            "description": "Linea",
            "quantity": "1",
            "unit_price": "1",
            "itbis_rate": "RATE_18",
        }
        data[field] = "1.5"

        form = PurchaseDocumentItemForm(data=data, organization=OrganizationFactory())

        assert not form.is_valid()
        assert field in form.errors


@pytest.mark.django_db
class TestSupplierForm:

    def test_supplier_form_rnc_cedula_lookup_attrs(self):
        form = SupplierForm(organization=OrganizationFactory())
        attrs = form.fields["rnc_cedula"].widget.attrs

        assert "default_ncf_type" not in form.fields
        assert attrs["hx-get"] == reverse("sales:rnc_lookup")
        assert attrs["hx-trigger"] == "blur changed"
        assert attrs["hx-include"] == "closest form"
        assert attrs["hx-target"] == "#rnc-lookup-result"
        assert attrs["hx-indicator"] == "#rnc-lookup-spinner"

    def test_supplier_form_id_type_choices_are_only_rnc_and_cedula(self):
        form = SupplierForm(organization=OrganizationFactory())

        assert list(form.fields["id_type"].choices) == [
            ("RNC", "RNC"),
            ("CED", "Cédula"),
        ]

    def test_supplier_picker_quick_create_offers_only_rnc_and_cedula(self):
        source = Path("templates/purchases/partials/supplier_picker_modal.html").read_text(
            encoding="utf-8"
        )

        assert 'option value="RNC"' in source
        assert 'option value="CED"' in source
        assert 'option value="PAS"' not in source
        assert 'option value="EXT"' not in source

    def test_supplier_create_page_has_rnc_lookup_ui_and_swal_config(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:supplier_create"))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'id="rnc-lookup-spinner"' in content
        assert 'id="rnc-lookup-result"' in content
        assert "rncFoundTitle" in content

    def test_supplier_create_page_places_contact_below_address(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:supplier_create"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "default_ncf_type" not in content
        assert content.index("Dirección") < content.index("Contacto")


    def test_supplier_form_accepts_rnc_without_check_digit_validation(self):
        org = OrganizationFactory()

        form = SupplierForm(
            data={
                "name": "Proveedor Sin Validar Digito",
                "id_type": "RNC",
                "rnc_cedula": "130461550",
                "email": "",
                "phone": "",
                "contact_name": "",
                "address": "",
                "city": "",
                "payment_term": "",
                "credit_limit": "",
                "notes": "",
            },
            organization=org,
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_data["rnc_cedula"] == "130461550"

    def test_supplier_model_accepts_rnc_without_check_digit_validation(self):
        supplier = SupplierFactory.build(
            organization=OrganizationFactory(),
            rnc_cedula="130461550",
        )

        supplier.full_clean()

    def test_supplier_model_rejects_rnc_with_wrong_length(self):
        supplier = SupplierFactory.build(
            organization=OrganizationFactory(),
            rnc_cedula="12345678",
        )

        with pytest.raises(ValidationError):
            supplier.full_clean()

    def test_supplier_model_rejects_unsupported_id_type(self):
        supplier = SupplierFactory.build(
            organization=OrganizationFactory(),
            id_type="PAS",
            rnc_cedula="AB123456",
        )

        with pytest.raises(ValidationError):
            supplier.full_clean()


@pytest.mark.django_db
class TestPurchaseMutationPermissions:

    def test_member_cannot_open_purchase_order_create(self, client):
        user, org, _ = make_member(Membership.Role.MEMBER)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:po_create"))

        assert response.status_code == 403

    def test_admin_can_open_purchase_order_create(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:po_create"))

        assert response.status_code == 200

    def test_member_cannot_create_supplier_payment(self, client):
        user, org, _ = make_member(Membership.Role.MEMBER)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:supplier_payment_create"))

        assert response.status_code == 403

    def test_admin_can_open_supplier_payment_create(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:supplier_payment_create"))

        assert response.status_code == 200

    def test_supplier_payment_create_uses_supplier_picker(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)

        response = client.get(reverse("purchases:supplier_payment_create"))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'id="supplier-display-text"' in content
        assert 'onclick="openSupplierPicker()"' in content
        assert 'id="supplierPickerModal"' in content
        assert "window.SUPPLIER_QUICK_CREATE_URL" in content
        assert 'id="id_supplier"' in content
        assert '<select name="supplier"' not in content
