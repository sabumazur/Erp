"""
Service tests for the purchases app.

Covers:
  - PurchaseOrderService.confirm()  — happy path, wrong-status guard, org isolation
  - PurchaseOrderService.cancel()   — happy path, guard (already received)
  - SupplierInvoiceService.confirm() — happy path, no-NCF guard, duplicate-NCF guard
  - SupplierInvoiceService.cancel()  — happy path, already-paid guard, allocated guard
  - SupplierPaymentService.create_payment() — happy path, overpayment guard, duplicate guard
  - SupplierPaymentService.delete_payment() — happy path, invoice status reverted
"""
from decimal import Decimal

import pytest

from apps.accounts.tests.factories import OrganizationFactory
from apps.purchases.models import (
    PurchaseDocument,
    PurchaseDocumentItem,
    PurchaseSequence,
    SupplierPayment,
    SupplierPaymentAllocation,
)
from apps.purchases.services import (
    PurchaseOrderService,
    SupplierInvoiceService,
    SupplierPaymentService,
)
from apps.purchases.tests.factories import (
    PurchaseDocumentFactory,
    PurchaseDocumentItemFactory,
    SupplierFactory,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ensure_sequence(org):
    PurchaseSequence.objects.get_or_create(
        organization=org,
        defaults={"prefix": "OC", "next_value": 1, "padding": 5},
    )


def _make_draft_po(org=None, supplier=None, unit_price=Decimal("1000.00")):
    supplier = supplier or SupplierFactory()
    org = org or supplier.organization
    po = PurchaseDocumentFactory(
        organization=org,
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


def _make_confirmed_po(org=None, supplier=None):
    supplier = supplier or SupplierFactory()
    org = org or supplier.organization
    _ensure_sequence(org)
    po = _make_draft_po(org=org, supplier=supplier)
    PurchaseOrderService.confirm(po)
    po.refresh_from_db()
    return po


def _make_confirmed_si(org, supplier, ncf="B0100000001", unit_price=Decimal("1000.00")):
    si = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
        status=PurchaseDocument.Status.DRAFT,
        supplier_ncf=ncf,
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


# ── PurchaseOrderService.confirm() ─────────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderConfirm:

    def test_happy_path_assigns_number_and_status(self):
        supplier = SupplierFactory()
        org = supplier.organization
        _ensure_sequence(org)
        po = _make_draft_po(org=org, supplier=supplier)

        PurchaseOrderService.confirm(po)
        po.refresh_from_db()

        assert po.status == PurchaseDocument.Status.CONFIRMED
        assert po.number.startswith("OC-")

    def test_sequence_increments_monotonically(self):
        supplier = SupplierFactory()
        org = supplier.organization
        _ensure_sequence(org)

        po1 = _make_draft_po(org=org, supplier=supplier)
        po2 = _make_draft_po(org=org, supplier=supplier)
        PurchaseOrderService.confirm(po1)
        PurchaseOrderService.confirm(po2)
        po1.refresh_from_db()
        po2.refresh_from_db()

        assert po1.number != po2.number

    def test_wrong_status_raises_value_error(self):
        po = _make_confirmed_po()
        with pytest.raises(ValueError, match="Borrador"):
            PurchaseOrderService.confirm(po)

    def test_wrong_doc_type_raises_value_error(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = PurchaseDocumentFactory(
            organization=org,
            supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
        )
        with pytest.raises(ValueError):
            PurchaseOrderService.confirm(si)

    def test_org_isolation_sequence_is_per_org(self):
        """Two orgs each get their own sequence starting from OC-00001."""
        s1 = SupplierFactory()
        org1 = s1.organization
        s2 = SupplierFactory()
        org2 = s2.organization
        _ensure_sequence(org1)
        _ensure_sequence(org2)

        po1 = _make_draft_po(org=org1, supplier=s1)
        po2 = _make_draft_po(org=org2, supplier=s2)
        PurchaseOrderService.confirm(po1)
        PurchaseOrderService.confirm(po2)
        po1.refresh_from_db()
        po2.refresh_from_db()

        # Both get the first number in their own sequence
        assert po1.number == "OC-00001"
        assert po2.number == "OC-00001"


# ── PurchaseOrderService.cancel() ──────────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderCancel:

    def test_cancel_draft(self):
        po = _make_draft_po()
        PurchaseOrderService.cancel(po)
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CANCELLED

    def test_cancel_confirmed(self):
        po = _make_confirmed_po()
        PurchaseOrderService.cancel(po)
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CANCELLED

    def test_cannot_cancel_received(self):
        po = _make_confirmed_po()
        # Advance to RECEIVED
        PurchaseOrderService.receive_and_invoice(po)
        po.refresh_from_db()
        with pytest.raises(ValueError, match="recibida"):
            PurchaseOrderService.cancel(po)

    def test_cannot_cancel_already_cancelled(self):
        po = _make_draft_po()
        PurchaseOrderService.cancel(po)
        po.refresh_from_db()
        with pytest.raises(ValueError):
            PurchaseOrderService.cancel(po)


# ── SupplierInvoiceService.confirm() ───────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierInvoiceConfirm:

    def test_happy_path_sets_confirmed_and_rnc(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org, rnc_cedula="101234567")
        si = _make_confirmed_si(org, supplier, ncf="B0100000001")
        assert si.status == PurchaseDocument.Status.CONFIRMED
        assert si.supplier_rnc == "101234567"

    def test_missing_ncf_raises_value_error(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = PurchaseDocumentFactory(
            organization=org,
            supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="",
        )
        PurchaseDocumentItemFactory(purchase_document=si, unit_price=Decimal("500.00"))
        si.recompute_totals()
        with pytest.raises(ValueError, match="NCF"):
            SupplierInvoiceService.confirm(si)

    def test_duplicate_ncf_per_org_raises_value_error(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        _make_confirmed_si(org, supplier, ncf="B0100000001")

        si2 = PurchaseDocumentFactory(
            organization=org,
            supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000001",
            supplier_ncf_type="B01",
        )
        PurchaseDocumentItemFactory(purchase_document=si2, unit_price=Decimal("500.00"))
        si2.recompute_totals()
        with pytest.raises(ValueError, match="NCF"):
            SupplierInvoiceService.confirm(si2)

    def test_same_ncf_different_org_is_allowed(self):
        """NCF uniqueness is scoped per org — same NCF in org B must not raise."""
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        supplier_a = SupplierFactory(organization=org_a)
        supplier_b = SupplierFactory(organization=org_b)

        _make_confirmed_si(org_a, supplier_a, ncf="B0100000001")
        # Should not raise
        si_b = _make_confirmed_si(org_b, supplier_b, ncf="B0100000001")
        assert si_b.status == PurchaseDocument.Status.CONFIRMED

    def test_already_confirmed_raises_value_error(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier)
        with pytest.raises(ValueError, match="Borrador"):
            SupplierInvoiceService.confirm(si)


# ── SupplierInvoiceService.cancel() ────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierInvoiceCancel:

    def test_cancel_confirmed_invoice(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier)
        SupplierInvoiceService.cancel(si)
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CANCELLED

    def test_cannot_cancel_paid_invoice(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("1000.00"))

        SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=si.issue_date,
            method="TRANSFER",
            reference="REF-001",
            notes="",
            allocations=[{"invoice": si, "amount": si.total}],
        )
        si.refresh_from_db()
        with pytest.raises(ValueError, match="pagada"):
            SupplierInvoiceService.cancel(si)

    def test_cannot_cancel_invoice_with_allocations(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("5000.00"))

        # Partial payment — invoice stays CONFIRMED, not PAID
        SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=si.issue_date,
            method="TRANSFER",
            reference="PARTIAL",
            notes="",
            allocations=[{"invoice": si, "amount": Decimal("100.00")}],
        )
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CONFIRMED

        with pytest.raises(ValueError, match="pagos aplicados"):
            SupplierInvoiceService.cancel(si)


# ── SupplierPaymentService.create_payment() ────────────────────────────────────

@pytest.mark.django_db
class TestSupplierPaymentCreate:

    def test_happy_path_full_payment_marks_paid(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("2000.00"))

        payment = SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=si.issue_date,
            method="TRANSFER",
            reference="BANK-001",
            notes="",
            allocations=[{"invoice": si, "amount": si.total}],
        )

        assert payment.pk is not None
        assert payment.amount == si.total
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.PAID

    def test_partial_payment_leaves_confirmed(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("5000.00"))
        partial = Decimal("100.00")

        SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=si.issue_date,
            method="CASH",
            reference="",
            notes="",
            allocations=[{"invoice": si, "amount": partial}],
        )

        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CONFIRMED

    def test_overpayment_raises_value_error(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("1000.00"))
        over = si.total + Decimal("1.00")

        with pytest.raises(ValueError, match="excede"):
            SupplierPaymentService.create_payment(
                supplier=supplier,
                org=org,
                payment_date=si.issue_date,
                method="TRANSFER",
                reference="",
                notes="",
                allocations=[{"invoice": si, "amount": over}],
            )

    def test_duplicate_invoice_in_same_payment_raises(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("2000.00"))

        with pytest.raises(ValueError, match="repetirse"):
            SupplierPaymentService.create_payment(
                supplier=supplier,
                org=org,
                payment_date=si.issue_date,
                method="TRANSFER",
                reference="",
                notes="",
                allocations=[
                    {"invoice": si, "amount": Decimal("500.00")},
                    {"invoice": si, "amount": Decimal("500.00")},
                ],
            )

    def test_wrong_org_supplier_raises(self):
        org_a = OrganizationFactory()
        org_b = OrganizationFactory()
        supplier_a = SupplierFactory(organization=org_a)
        supplier_b = SupplierFactory(organization=org_b)
        si = _make_confirmed_si(org_b, supplier_b, unit_price=Decimal("1000.00"))

        with pytest.raises(ValueError, match="organización"):
            SupplierPaymentService.create_payment(
                supplier=supplier_a,  # org_a supplier
                org=org_a,
                payment_date=si.issue_date,
                method="TRANSFER",
                reference="",
                notes="",
                allocations=[{"invoice": si, "amount": si.total}],
            )

    def test_empty_allocations_raises(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        with pytest.raises(ValueError, match="factura"):
            SupplierPaymentService.create_payment(
                supplier=supplier,
                org=org,
                payment_date=None,
                method="TRANSFER",
                reference="",
                notes="",
                allocations=[],
            )


# ── SupplierPaymentService.delete_payment() ────────────────────────────────────

@pytest.mark.django_db
class TestSupplierPaymentDelete:

    def test_delete_reverts_paid_invoice_to_confirmed(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("1000.00"))

        payment = SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=si.issue_date,
            method="TRANSFER",
            reference="DEL-TEST",
            notes="",
            allocations=[{"invoice": si, "amount": si.total}],
        )
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.PAID

        SupplierPaymentService.delete_payment(payment)

        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CONFIRMED
        assert not SupplierPayment.objects.filter(pk=payment.pk).exists()

    def test_delete_removes_allocations(self):
        org = OrganizationFactory()
        supplier = SupplierFactory(organization=org)
        si = _make_confirmed_si(org, supplier, unit_price=Decimal("1000.00"))

        payment = SupplierPaymentService.create_payment(
            supplier=supplier,
            org=org,
            payment_date=si.issue_date,
            method="TRANSFER",
            reference="",
            notes="",
            allocations=[{"invoice": si, "amount": si.total}],
        )
        payment_pk = payment.pk
        SupplierPaymentService.delete_payment(payment)

        assert not SupplierPaymentAllocation.objects.filter(payment_id=payment_pk).exists()
