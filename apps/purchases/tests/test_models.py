from decimal import Decimal

import pytest

from apps.accounts.tests.factories import OrganizationFactory
from apps.core.models import DocumentSequence
from apps.purchases.models import (
    PurchaseDocument,
    PurchaseDocumentItem,
    Supplier,
)
from apps.purchases.tests.factories import (
    PurchaseDocumentFactory,
    PurchaseDocumentItemFactory,
    SupplierFactory,
    SupplierPaymentFactory,
)


_PO_DEFAULTS = {"prefix": "OC", "padding": 5, "include_year": False}


@pytest.mark.django_db
class TestPurchaseSequence:

    def test_generate_returns_prefixed_padded_number(self):
        org = OrganizationFactory()
        assert DocumentSequence.generate(org, "PURCHASE_ORDER", defaults=_PO_DEFAULTS) == "OC-00001"

    def test_generate_increments(self):
        org = OrganizationFactory()
        DocumentSequence.generate(org, "PURCHASE_ORDER", defaults=_PO_DEFAULTS)
        assert DocumentSequence.generate(org, "PURCHASE_ORDER", defaults=_PO_DEFAULTS) == "OC-00002"

    def test_generate_is_isolated_per_org(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        DocumentSequence.generate(org_a, "PURCHASE_ORDER", defaults=_PO_DEFAULTS)
        DocumentSequence.generate(org_a, "PURCHASE_ORDER", defaults=_PO_DEFAULTS)
        assert DocumentSequence.generate(org_b, "PURCHASE_ORDER", defaults=_PO_DEFAULTS) == "OC-00001"


@pytest.mark.django_db
class TestPurchaseDocumentItemCompute:

    def test_compute_rate_18(self):
        item = PurchaseDocumentItemFactory(
            quantity=Decimal("2.0000"),
            unit_price=Decimal("100.00"),
            itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_18,
        )
        assert item.line_total == Decimal("200.00")
        assert item.itbis_amount == Decimal("36.00")
        assert item.line_total_with_itbis == Decimal("236.00")

    def test_compute_rate_16(self):
        item = PurchaseDocumentItemFactory(
            quantity=Decimal("1.0000"),
            unit_price=Decimal("500.00"),
            itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_16,
        )
        assert item.line_total == Decimal("500.00")
        assert item.itbis_amount == Decimal("80.00")
        assert item.line_total_with_itbis == Decimal("580.00")

    def test_compute_exempt(self):
        item = PurchaseDocumentItemFactory(
            quantity=Decimal("3.0000"),
            unit_price=Decimal("50.00"),
            itbis_rate=PurchaseDocumentItem.ITBISRate.EXEMPT,
        )
        assert item.line_total == Decimal("150.00")
        assert item.itbis_amount == Decimal("0.00")
        assert item.line_total_with_itbis == Decimal("150.00")


@pytest.mark.django_db
class TestPurchaseDocumentRecomputeTotals:

    def test_recompute_splits_itbis_18_and_16(self):
        doc = PurchaseDocumentFactory()
        PurchaseDocumentItemFactory(
            purchase_document=doc,
            unit_price=Decimal("1000.00"),
            itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_18,
        )
        PurchaseDocumentItemFactory(
            purchase_document=doc,
            unit_price=Decimal("500.00"),
            itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_16,
        )
        PurchaseDocumentItemFactory(
            purchase_document=doc,
            unit_price=Decimal("200.00"),
            itbis_rate=PurchaseDocumentItem.ITBISRate.EXEMPT,
        )

        doc.recompute_totals()
        doc.refresh_from_db()

        assert doc.subtotal == Decimal("1700.00")
        assert doc.itbis_18 == Decimal("180.00")
        assert doc.itbis_16 == Decimal("80.00")
        assert doc.total == Decimal("1960.00")
        assert doc.itbis_total == Decimal("260.00")


@pytest.mark.django_db
class TestSupplierPaymentDelete:

    def test_delete_raises_value_error(self):
        payment = SupplierPaymentFactory()
        with pytest.raises(ValueError):
            payment.delete()


@pytest.mark.django_db
class TestSupplierDeleteGuard:

    def test_delete_blocked_when_supplier_has_documents(self):
        doc = PurchaseDocumentFactory()
        with pytest.raises(ValueError):
            doc.supplier.delete()

    def test_delete_blocked_when_supplier_has_payments(self):
        payment = SupplierPaymentFactory()
        with pytest.raises(ValueError):
            payment.supplier.delete()

    def test_delete_allowed_when_supplier_is_clean(self):
        supplier = SupplierFactory()
        supplier.delete()
        assert not Supplier.objects.filter(pk=supplier.pk).exists()
        assert Supplier.all_objects.filter(pk=supplier.pk).exists()
