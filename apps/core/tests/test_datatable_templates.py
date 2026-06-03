from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.core.paginator import Paginator
from django.template.loader import render_to_string

from apps.core.datatable import DTColumn


ROW_PK = "00000000-0000-0000-0000-000000000001"


class EmptyRelated:
    def all(self):
        return []


def _row(**kwargs):
    defaults = {
        "pk": ROW_PK,
        "status": "DRAFT",
        "issue_date": date(2026, 1, 15),
        "due_date": date(2026, 2, 15),
        "valid_until": date(2026, 2, 15),
        "delivery_date": date(2026, 2, 15),
        "expected_date": date(2026, 2, 15),
        "total": Decimal("1234.56"),
        "amount": Decimal("1234.56"),
        "customer": SimpleNamespace(
            pk=ROW_PK,
            name="Cliente Demo",
            rnc_cedula="101123456",
        ),
        "supplier": SimpleNamespace(name="Proveedor Demo"),
        "display_number": "DOC-001",
        "doc_number": "DOC-001",
        "number": "PO-001",
        "supplier_ncf": "B0100000001",
        "department": None,
        "method": "TRANSFER",
        "reference": "REF-001",
        "allocations": EmptyRelated(),
        "code": "ITM-001",
        "name": "Servicio Demo",
        "item_type": "BOTH",
        "unit": "UNIT",
        "unit_price": Decimal("1234.56"),
        "cost_price": Decimal("1234.56"),
        "itbis_rate": "RATE_18",
        "is_active": True,
        "encf": "E310000000001",
    }
    defaults.update(kwargs)
    return SimpleNamespace(
        **defaults,
        get_method_display=lambda: "Transferencia",
        get_status_display=lambda: "Borrador",
        get_item_type_display=lambda: "Ambos",
        get_unit_display=lambda: "Unidad",
        get_itbis_rate_display=lambda: "18%",
    )


def test_pagination_renders_segmented_toolbar_buttons():
    page_obj = Paginator(range(60), 10).page(3)

    html = render_to_string(
        "components/datatable/pagination.html",
        {
            "dt_page_obj": page_obj,
            "dt_page_range": [1, 2, 3, 4, 5, None, 6],
        },
    )

    assert 'class="dt-pagination d-inline-flex align-items-center gap-1"' in html
    assert "dt-page-btn" in html
    assert "dt-page-btn-active" in html
    assert 'onclick="dtPage(2)"' in html
    assert 'onclick="dtPage(4)"' in html
    assert "page-link" not in html


def test_pagination_renders_on_single_page():
    page_obj = Paginator(range(5), 10).page(1)

    html = render_to_string(
        "components/datatable/pagination.html",
        {
            "dt_page_obj": page_obj,
            "dt_page_range": [1],
        },
    )

    assert 'class="dt-pagination d-inline-flex align-items-center gap-1"' in html
    assert "dt-page-btn-active" in html
    assert html.count("disabled") == 2


def test_column_visibility_dropdown_renders_bulk_controls_and_model_bound_checkboxes():
    page_obj = Paginator([], 10).page(1)

    html = render_to_string(
        "components/datatable/wrapper.html",
        {
            "dt_columns": [
                DTColumn("name", "Nombre"),
                DTColumn("status", "Estado"),
            ],
            "dt_column_keys_json": '["name", "status"]',
            "dt_default_visible_json": '["name"]',
            "dt_sort": "name",
            "dt_page_obj": page_obj,
            "dt_total": 0,
            "dt_page_range": [1],
            "dt_url": "items:item_list",
            "dt_action_url": "/items/",
            "dt_push_url": "false",
            "dt_row_template": "items/partials/item_row.html",
            "dt_filter_template": "",
            "dt_ribbon_template": "",
            "dt_search_placeholder": "Buscar",
            "dt_id": "test-items",
            "dt_q": "",
            "active_filter_count": 0,
            "dt_status_pills": [],
            "dt_active_status": "",
            "dt_page_size": 10,
            "dt_page_size_options": [10, 25],
        },
    )

    assert "Seleccionar todo" in html
    assert "Anular selección" in html
    assert 'x-model="visible"' in html
    # Column visibility is driven reactively by a $watch on `visible`;
    # checkboxes are pure x-model with no per-element @change handler.
    assert "commitVisible" not in html
    assert "toggleCol" not in html


def test_sales_datatable_money_cells_omit_currency_prefix():
    for template_name in [
        "sales/partials/invoice_row.html",
        "sales/partials/quotation_row.html",
        "sales/partials/sale_order_row.html",
        "sales/partials/payment_row.html",
    ]:
        html = render_to_string(template_name, {"row": _row()})

        assert 'class="amt"' in html
        assert "1,234.56" in html
        assert "RD$" not in html


def test_purchases_datatable_money_cells_omit_currency_prefix():
    for template_name in [
        "purchases/partials/purchase_order_row.html",
        "purchases/partials/supplier_invoice_row.html",
        "purchases/partials/supplier_payment_row.html",
    ]:
        html = render_to_string(template_name, {"row": _row()})

        assert 'class="amt"' in html
        assert "1,234.56" in html
        assert "RD$" not in html


def test_items_datatable_money_cells_omit_currency_prefix():
    html = render_to_string(
        "items/partials/item_row.html",
        {
            "row": _row(),
            "membership": SimpleNamespace(is_admin=True),
            "csrf_token": "test-token",
        },
    )

    assert 'class="amt"' in html
    assert "1,234.56" in html
    assert "RD$" not in html


def test_sales_document_rows_disable_edit_for_non_drafts():
    for template_name in [
        "sales/partials/invoice_row.html",
        "sales/partials/quotation_row.html",
        "sales/partials/sale_order_row.html",
    ]:
        draft_html = render_to_string(template_name, {"row": _row(status="DRAFT")})
        confirmed_html = render_to_string(template_name, {"row": _row(status="CONFIRMED")})

        assert 'data-action="edit"' in draft_html
        assert 'aria-disabled="true"' not in draft_html
        assert 'data-action="edit-disabled"' in confirmed_html
        assert 'aria-disabled="true"' in confirmed_html


def test_purchase_document_rows_disable_edit_for_non_drafts():
    for template_name in [
        "purchases/partials/purchase_order_row.html",
        "purchases/partials/supplier_invoice_row.html",
    ]:
        draft_html = render_to_string(template_name, {"row": _row(status="DRAFT")})
        confirmed_html = render_to_string(template_name, {"row": _row(status="CONFIRMED")})

        assert 'data-action="edit"' in draft_html
        assert 'aria-disabled="true"' not in draft_html
        assert 'data-action="edit-disabled"' in confirmed_html
        assert 'aria-disabled="true"' in confirmed_html
