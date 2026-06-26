import pytest
from apps.sales.forms import InvoiceItemForm
from apps.sales.tests.factories import SalesDocumentItemFactory


@pytest.mark.django_db
def test_invoice_item_form_preserves_sort_order_on_instance():
    """Ensure InvoiceItemForm preserves sort_order from instance when POST omits it."""
    line = SalesDocumentItemFactory()
    org = line.document.organization
    data = {
        "item": str(line.item.pk) if getattr(line, "item", None) else "",
        "description": line.description or "Catalog line",
        "quantity": str(line.quantity),
        "unit_price": str(line.unit_price),
        "itbis_rate": line.itbis_rate,
    }
    form = InvoiceItemForm(data, instance=line, organization=org)
    assert form.is_valid(), form.errors
    assert form.cleaned_data.get("sort_order") == line.sort_order
