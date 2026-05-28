"""Tests for purchase app services."""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.purchases.models import (
    PurchaseDocument, PurchaseDocumentItem, PurchaseSequence,
    SupplierPayment, SupplierPaymentAllocation,
)
from apps.purchases.services import (
    PurchaseOrderService, SupplierInvoiceService, SupplierPaymentService,
)
from .factories import (
    SupplierFactory, PurchaseDocumentFactory, PurchaseDocumentItemFactory,
    SupplierPaymentFactory,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_po_with_item(org=None, supplier=None, unit_price=Decimal("1000.00")):
    """Return a DRAFT PurchaseOrder with one line item."""
    supplier = supplier or SupplierFactory()
    po = PurchaseDocumentFactory(
        organization=supplier.organization if org is None else org,
        supplier=supplier,
        doc_type=PurchaseDocument.DocType.PURCHASE_ORDER,
        status=PurchaseDocument.Status.DRAFT,
    )
    PurchaseDocumentItemFactory(
        purchase_document=po,
        quantity=Decimal("1"),
        unit_price=unit_price,
        itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_18,
    )
    po.recompute_totals()
    po.refresh_from_db()
    return po


def make_confirmed_si(org, supplier, supplier_ncf="B0100000001", unit_price=Decimal("1000.00")):
    """Return a CONFIRMED SupplierInvoice."""
    si = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
        status=PurchaseDocument.Status.DRAFT,
        supplier_ncf=supplier_ncf,
        supplier_ncf_type="B01",
    )
    PurchaseDocumentItemFactory(
        purchase_document=si,
        quantity=Decimal("1"),
        unit_price=unit_price,
        itbis_rate=PurchaseDocumentItem.ITBISRate.RATE_18,
    )
    si.recompute_totals()
    SupplierInvoiceService.confirm(si)
    si.refresh_from_db()
    return si


# ── PurchaseOrderService ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderService:

    def test_confirm_assigns_number(self):
        po = make_po_with_item()
        org = po.organization
        PurchaseSequence.objects.create(organization=org, prefix="OC", next_value=1, padding=5)
        PurchaseOrderService.confirm(po)
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CONFIRMED
        assert po.number.startswith("OC-")

    def test_confirm_only_from_draft(self):
        po = make_po_with_item()
        org = po.organization
        PurchaseSequence.objects.create(organization=org, prefix="OC", next_value=1, padding=5)
        PurchaseOrderService.confirm(po)
        with pytest.raises(ValueError):
            PurchaseOrderService.confirm(po)

    def test_cancel_draft(self):
        po = make_po_with_item()
        PurchaseOrderService.cancel(po)
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CANCELLED

    def test_cancel_confirmed(self):
        po = make_po_with_item()
        org = po.organization
        PurchaseSequence.objects.create(organization=org, prefix="OC", next_value=1, padding=5)
        PurchaseOrderService.confirm(po)
        PurchaseOrderService.cancel(po)
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CANCELLED

    def test_receive_creates_supplier_invoice(self):
        po = make_po_with_item()
        org = po.organization
        PurchaseSequence.objects.create(organization=org, prefix="OC", next_value=1, padding=5)
        PurchaseOrderService.confirm(po)
        po_returned, si = PurchaseOrderService.receive_and_invoice(po)
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.RECEIVED
        assert si.doc_type == PurchaseDocument.DocType.SUPPLIER_INVOICE
        assert si.status == PurchaseDocument.Status.DRAFT
        assert si.linked_purchase_order == po
        assert si.supplier == po.supplier
        assert si.items.count() == 1

    def test_receive_only_from_confirmed(self):
        po = make_po_with_item()
        with pytest.raises(ValueError):
            PurchaseOrderService.receive_and_invoice(po)

    def test_receive_updates_si_totals(self):
        po = make_po_with_item(unit_price=Decimal("500.00"))
        org = po.organization
        PurchaseSequence.objects.create(organization=org, prefix="OC", next_value=1, padding=5)
        PurchaseOrderService.confirm(po)
        _, si = PurchaseOrderService.receive_and_invoice(po)
        si.refresh_from_db()
        assert si.subtotal > 0
        assert si.total > 0


# ── SupplierInvoiceService ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierInvoiceService:

    def test_confirm_sets_status_and_rnc(self):
        supplier = SupplierFactory(id_number="131000123")
        org = supplier.organization
        si = PurchaseDocumentFactory(
            organization=org, supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000001",
            supplier_ncf_type="B01",
        )
        PurchaseDocumentItemFactory(purchase_document=si)
        si.recompute_totals()
        SupplierInvoiceService.confirm(si)
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CONFIRMED
        assert si.supplier_rnc == supplier.id_number

    def test_confirm_requires_ncf(self):
        supplier = SupplierFactory()
        org = supplier.organization
        si = PurchaseDocumentFactory(
            organization=org, supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="",
        )
        PurchaseDocumentItemFactory(purchase_document=si)
        si.recompute_totals()
        with pytest.raises(ValueError):
            SupplierInvoiceService.confirm(si)

    def test_confirm_enforces_ncf_uniqueness(self):
        supplier = SupplierFactory()
        org = supplier.organization
        make_confirmed_si(org, supplier, supplier_ncf="B0100000001")
        si2 = PurchaseDocumentFactory(
            organization=org, supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000001",
            supplier_ncf_type="B01",
        )
        PurchaseDocumentItemFactory(purchase_document=si2)
        si2.recompute_totals()
        with pytest.raises(ValueError):
            SupplierInvoiceService.confirm(si2)

    def test_confirm_updates_item_cost_price(self):
        from apps.items.models import Item
        supplier = SupplierFactory()
        org = supplier.organization
        item = Item.objects.create(
            organization=org,
            name="Producto Test",
            item_type=Item.ItemType.PURCHASE,
            unit_price=Decimal("0.00"),
            cost_price=None,
        )
        si = PurchaseDocumentFactory(
            organization=org, supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000099",
            supplier_ncf_type="B01",
        )
        PurchaseDocumentItemFactory(
            purchase_document=si,
            item=item,
            unit_price=Decimal("750.00"),
        )
        si.recompute_totals()
        SupplierInvoiceService.confirm(si)
        item.refresh_from_db()
        assert item.cost_price == Decimal("750.00")
        assert item.default_supplier == supplier

    def test_confirm_does_not_overwrite_default_supplier(self):
        from apps.items.models import Item
        supplier1 = SupplierFactory()
        supplier2 = SupplierFactory(organization=supplier1.organization)
        org = supplier1.organization
        item = Item.objects.create(
            organization=org,
            name="Producto Existente",
            item_type=Item.ItemType.PURCHASE,
            unit_price=Decimal("0.00"),
            default_supplier=supplier1,
        )
        si = PurchaseDocumentFactory(
            organization=org, supplier=supplier2,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000077",
            supplier_ncf_type="B01",
        )
        PurchaseDocumentItemFactory(purchase_document=si, item=item, unit_price=Decimal("900.00"))
        si.recompute_totals()
        SupplierInvoiceService.confirm(si)
        item.refresh_from_db()
        # default_supplier must remain supplier1 (not overwritten)
        assert item.default_supplier == supplier1

    def test_cancel_confirmed_invoice(self):
        supplier = SupplierFactory()
        org = supplier.organization
        si = make_confirmed_si(org, supplier)
        SupplierInvoiceService.cancel(si)
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CANCELLED

    def test_reopen_cancelled_invoice(self):
        supplier = SupplierFactory()
        org = supplier.organization
        si = make_confirmed_si(org, supplier)
        SupplierInvoiceService.cancel(si)
        SupplierInvoiceService.reopen(si)
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.DRAFT

    def test_cancel_only_when_no_allocations(self):
        supplier = SupplierFactory()
        org = supplier.organization
        si = make_confirmed_si(org, supplier)
        payment = SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=timezone.now().date(),
            method=SupplierPayment.Method.CASH,
            reference="",
            notes="",
            allocations=[{"invoice": si, "amount": si.total}],
        )
        with pytest.raises(ValueError):
            SupplierInvoiceService.cancel(si)


# ── SupplierPaymentService ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierPaymentService:

    def test_create_payment_derives_amount_from_allocations(self):
        supplier = SupplierFactory()
        org = supplier.organization
        si = make_confirmed_si(org, supplier, supplier_ncf="B0100000010")
        payment = SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=timezone.now().date(),
            method=SupplierPayment.Method.TRANSFER,
            reference="TRF-001",
            notes="",
            allocations=[{"invoice": si, "amount": Decimal("500.00")}],
        )
        assert payment.amount == Decimal("500.00")
        assert payment.allocations.count() == 1

    def test_full_payment_marks_invoice_paid(self):
        supplier = SupplierFactory()
        org = supplier.organization
        si = make_confirmed_si(org, supplier, supplier_ncf="B0100000020")
        SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=timezone.now().date(),
            method=SupplierPayment.Method.CASH,
            reference="",
            notes="",
            allocations=[{"invoice": si, "amount": si.total}],
        )
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.PAID

    def test_delete_payment_reopens_paid_invoice(self):
        supplier = SupplierFactory()
        org = supplier.organization
        si = make_confirmed_si(org, supplier, supplier_ncf="B0100000030")
        payment = SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=timezone.now().date(),
            method=SupplierPayment.Method.CASH,
            reference="",
            notes="",
            allocations=[{"invoice": si, "amount": si.total}],
        )
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.PAID
        SupplierPaymentService.delete_payment(payment)
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CONFIRMED
        assert not SupplierPayment.objects.filter(pk=payment.pk).exists()


# ── Item Delete Guard ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestItemDeleteGuard:

    def test_item_referenced_in_purchase_line_cannot_be_deleted(self):
        from apps.items.models import Item
        supplier = SupplierFactory()
        org = supplier.organization
        item = Item.objects.create(
            organization=org,
            name="Artículo en OC",
            item_type=Item.ItemType.PURCHASE,
            unit_price=Decimal("0.00"),
        )
        po = PurchaseDocumentFactory(
            organization=org, supplier=supplier,
            doc_type=PurchaseDocument.DocType.PURCHASE_ORDER,
        )
        PurchaseDocumentItemFactory(purchase_document=po, item=item)
        with pytest.raises(ValueError):
            item.delete()
