"""Query-count / write-path regression tests for the performance pass.

Guards against regressions in:
  - the suspend_recompute bulk-save path (recompute once, not per item)
  - status_pill_counts collapsing N status COUNTs into a single GROUP BY
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.core.datatable import status_pill_counts
from apps.sales.models import SalesDocument, SalesDocumentItem
from apps.sales.signals import suspend_recompute
from apps.sales.tests.factories import (
    SalesDocumentFactory,
    SalesDocumentItemFactory,
)


@pytest.mark.django_db
def test_suspend_recompute_runs_once_not_per_item(org):
    """Saving N line items inside suspend_recompute must recompute totals
    exactly once on exit, not once per item (the old signal storm)."""
    invoice = SalesDocumentFactory(organization=org)
    with patch.object(
        SalesDocument, "recompute_totals", autospec=True
    ) as mock_recompute:
        with suspend_recompute(invoice):
            for _ in range(5):
                SalesDocumentItemFactory(document=invoice)
            assert mock_recompute.call_count == 0  # suppressed inside the block
        assert mock_recompute.call_count == 1  # recomputed once on exit


@pytest.mark.django_db
def test_suspend_recompute_totals_correct(org):
    """The single deferred recompute must produce the same totals the
    per-item path produced."""
    invoice = SalesDocumentFactory(organization=org)
    with suspend_recompute(invoice):
        for _ in range(3):
            SalesDocumentItemFactory(
                document=invoice,
                quantity=Decimal("1.0000"),
                unit_price=Decimal("1000.00"),
                itbis_rate=SalesDocumentItem.ITBISRate.RATE_18,
            )
    invoice.refresh_from_db()
    assert invoice.subtotal == Decimal("3000.00")
    assert invoice.itbis_18 == Decimal("540.00")
    assert invoice.total == Decimal("3540.00")


@pytest.mark.django_db
def test_status_pill_counts_single_query(org):
    """status_pill_counts must compute every pill from one grouped query,
    not one COUNT per pill."""
    SalesDocumentFactory.create_batch(
        3, organization=org, status=SalesDocument.Status.DRAFT
    )
    SalesDocumentFactory(organization=org, status=SalesDocument.Status.PAID)
    qs = SalesDocument.invoices.filter(organization=org)
    specs = [
        {"value": "DRAFT", "label": "Borrador"},
        {"value": "PAID", "label": "Pagada"},
        {"value": "SENT", "label": "Enviada"},
    ]
    with CaptureQueriesContext(connection) as captured:
        pills = status_pill_counts(qs, specs)
    assert len(captured.captured_queries) == 1
    counts = {p["value"]: p["count"] for p in pills}
    assert counts == {"DRAFT": 3, "PAID": 1, "SENT": 0}
