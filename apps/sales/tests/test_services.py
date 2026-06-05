"""
Tests for PaymentService and QuotationService.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.sales.models import SalesDocument, SalesDocumentItem, Payment, PaymentAllocation
from apps.sales.services import PaymentService, QuotationService
from .factories import (
    CustomerFactory,
    SalesDocumentFactory,
    SalesDocumentItemFactory,
    NCFSequenceFactory,
    PaymentFactory,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_confirmed_invoice(organization, customer, total=Decimal("1000.00")):
    """Return a CONFIRMED invoice with a single line item totalling `total`."""
    from apps.sales.models import NCFSequence as _NCFSeq
    _NCFSeq.objects.get_or_create(
        organization=organization, ncf_type=31, is_active=True,
        defaults={"current_seq": 0, "max_seq": 9999999999, "series": "E"},
    )
    inv = SalesDocumentFactory(
        organization=organization,
        customer=customer,
        ncf_type=31,
        status=SalesDocument.Status.DRAFT,
    )
    SalesDocumentItemFactory(
        document=inv,
        quantity=Decimal("1"),
        unit_price=(total / Decimal("1.18")).quantize(Decimal("0.01")),
        itbis_rate=SalesDocumentItem.ITBISRate.RATE_18,
    )
    inv.recompute_totals()
    inv.refresh_from_db()
    # Manually confirm (assign encf)
    from apps.sales.services import NCFService
    NCFService.confirm(inv)
    inv.refresh_from_db()
    return inv


# ── PaymentService.register ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestPaymentServiceRegister:

    def test_registers_payment_and_allocation(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(org, customer)

        payment = PaymentService.register(
            organization=org,
            customer=customer,
            payment_date=timezone.now().date(),
            method=Payment.Method.TRANSFER,
            reference="REF-001",
            notes="",
            allocations=[{"invoice": inv, "amount": inv.total}],
        )

        assert payment.pk is not None
        assert payment.amount == inv.total
        assert PaymentAllocation.objects.filter(payment=payment, invoice=inv).exists()

    def test_auto_marks_invoice_paid_when_fully_covered(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(org, customer)

        PaymentService.register(
            organization=org,
            customer=customer,
            payment_date=timezone.now().date(),
            method=Payment.Method.TRANSFER,
            reference="",
            notes="",
            allocations=[{"invoice": inv, "amount": inv.total}],
        )
        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.PAID

    def test_partial_payment_does_not_mark_paid(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(org, customer)
        partial = inv.total / 2

        PaymentService.register(
            organization=org,
            customer=customer,
            payment_date=timezone.now().date(),
            method=Payment.Method.TRANSFER,
            reference="",
            notes="",
            allocations=[{"invoice": inv, "amount": partial}],
        )
        inv.refresh_from_db()
        assert inv.status != SalesDocument.Status.PAID

    def test_raises_when_amount_exceeds_balance(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(org, customer)

        with pytest.raises(ValueError, match="excede el saldo"):
            PaymentService.register(
                organization=org,
                customer=customer,
                payment_date=timezone.now().date(),
                method=Payment.Method.TRANSFER,
                reference="",
                notes="",
                allocations=[{"invoice": inv, "amount": inv.total + Decimal("1")}],
            )

    def test_raises_with_empty_allocations(self):
        customer = CustomerFactory()
        org = customer.organization

        with pytest.raises(ValueError, match="al menos una factura"):
            PaymentService.register(
                organization=org,
                customer=customer,
                payment_date=timezone.now().date(),
                method=Payment.Method.TRANSFER,
                reference="",
                notes="",
                allocations=[],
            )

    def test_raises_when_invoice_belongs_to_different_org(self):
        customer = CustomerFactory()
        org = customer.organization
        other_customer = CustomerFactory()  # different org
        other_inv = make_confirmed_invoice(other_customer.organization, other_customer)

        with pytest.raises(ValueError, match="no pertenece a esta organización"):
            PaymentService.register(
                organization=org,
                customer=customer,
                payment_date=timezone.now().date(),
                method=Payment.Method.TRANSFER,
                reference="",
                notes="",
                allocations=[{"invoice": other_inv, "amount": other_inv.total}],
            )

    def test_multi_invoice_payment(self):
        customer = CustomerFactory()
        org = customer.organization
        inv1 = make_confirmed_invoice(org, customer, total=Decimal("590.00"))
        inv2 = make_confirmed_invoice(org, customer, total=Decimal("590.00"))

        payment = PaymentService.register(
            organization=org,
            customer=customer,
            payment_date=timezone.now().date(),
            method=Payment.Method.TRANSFER,
            reference="",
            notes="",
            allocations=[
                {"invoice": inv1, "amount": inv1.total},
                {"invoice": inv2, "amount": inv2.total},
            ],
        )

        assert payment.amount == inv1.total + inv2.total
        assert PaymentAllocation.objects.filter(payment=payment).count() == 2

    def test_rejects_invoice_for_different_customer_in_same_org(self):
        customer = CustomerFactory()
        other_customer = CustomerFactory(organization=customer.organization)
        inv = make_confirmed_invoice(customer.organization, other_customer)

        with pytest.raises(ValueError, match="cliente seleccionado"):
            PaymentService.register(
                organization=customer.organization,
                customer=customer,
                payment_date=timezone.now().date(),
                method=Payment.Method.TRANSFER,
                reference="",
                notes="",
                allocations=[{"invoice": inv, "amount": inv.total}],
            )

    def test_rejects_duplicate_allocation_rows(self):
        customer = CustomerFactory()
        inv = make_confirmed_invoice(customer.organization, customer)

        with pytest.raises(ValueError, match="repetirse"):
            PaymentService.register(
                organization=customer.organization,
                customer=customer,
                payment_date=timezone.now().date(),
                method=Payment.Method.TRANSFER,
                reference="",
                notes="",
                allocations=[
                    {"invoice": inv, "amount": Decimal("10.00")},
                    {"invoice": inv, "amount": Decimal("10.00")},
                ],
            )

    def test_rejects_credit_note_payment(self):
        customer = CustomerFactory()
        org = customer.organization
        original = make_confirmed_invoice(org, customer)
        NCFSequenceFactory(organization=org, ncf_type=34, current_seq=0)
        note = SalesDocumentFactory(
            organization=org,
            customer=customer,
            ncf_type=34,
            encf_modified=original,
        )
        SalesDocumentItemFactory(document=note)
        from apps.sales.services import NCFService
        NCFService.confirm(note)

        with pytest.raises(ValueError, match="notas"):
            PaymentService.register(
                organization=org,
                customer=customer,
                payment_date=timezone.now().date(),
                method=Payment.Method.TRANSFER,
                reference="",
                notes="",
                allocations=[{"invoice": note, "amount": note.total}],
            )


# ── PaymentService.delete ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPaymentServiceDelete:

    def test_deletes_payment_and_reopens_invoice(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(org, customer)

        payment = PaymentService.register(
            organization=org,
            customer=customer,
            payment_date=timezone.now().date(),
            method=Payment.Method.TRANSFER,
            reference="",
            notes="",
            allocations=[{"invoice": inv, "amount": inv.total}],
        )
        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.PAID

        PaymentService.delete(payment)

        assert not Payment.objects.filter(pk=payment.pk).exists()
        inv.refresh_from_db()
        assert inv.status != SalesDocument.Status.PAID

    def test_partial_payment_delete_does_not_reopen(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(org, customer)

        p1 = PaymentService.register(
            organization=org, customer=customer,
            payment_date=timezone.now().date(),
            method=Payment.Method.TRANSFER, reference="", notes="",
            allocations=[{"invoice": inv, "amount": inv.total / 2}],
        )
        p2 = PaymentService.register(
            organization=org, customer=customer,
            payment_date=timezone.now().date(),
            method=Payment.Method.TRANSFER, reference="", notes="",
            allocations=[{"invoice": inv, "amount": inv.total / 2}],
        )
        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.PAID

        # Delete one of the two payments — invoice should reopen
        PaymentService.delete(p1)
        inv.refresh_from_db()
        assert inv.status != SalesDocument.Status.PAID


# ── QuotationService ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestQuotationService:

    def _draft_quotation(self, organization=None, customer=None):
        if customer is None:
            customer = CustomerFactory()
        org = organization or customer.organization
        q = SalesDocumentFactory(
            organization=org,
            customer=customer,
            status=SalesDocument.Status.DRAFT,
            doc_type=SalesDocument.DocType.QUOTATION,
        )
        SalesDocumentItemFactory(document=q, quantity=Decimal("1"), unit_price=Decimal("500"))
        q.recompute_totals()
        return q

    def test_confirm_assigns_doc_number(self):
        q = self._draft_quotation()
        QuotationService.confirm(q)
        q.refresh_from_db()
        assert q.status == SalesDocument.Status.CONFIRMED
        assert q.doc_number.startswith("COT-")

    def test_confirm_raises_if_not_draft(self):
        q = self._draft_quotation()
        QuotationService.confirm(q)
        with pytest.raises(ValueError, match="Borrador"):
            QuotationService.confirm(q)

    def test_send_transitions_confirmed_to_sent(self):
        q = self._draft_quotation()
        QuotationService.confirm(q)
        QuotationService.send(q)
        q.refresh_from_db()
        assert q.status == SalesDocument.Status.SENT

    def test_accept_transitions_sent_to_accepted(self):
        q = self._draft_quotation()
        QuotationService.confirm(q)
        QuotationService.send(q)
        QuotationService.accept(q)
        q.refresh_from_db()
        assert q.status == SalesDocument.Status.ACCEPTED

    def test_reject_transitions_sent_to_rejected(self):
        q = self._draft_quotation()
        QuotationService.confirm(q)
        QuotationService.send(q)
        QuotationService.reject(q)
        q.refresh_from_db()
        assert q.status == SalesDocument.Status.REJECTED

    def test_convert_to_invoice_creates_draft_invoice(self):
        customer = CustomerFactory()
        q = self._draft_quotation(customer=customer)
        QuotationService.confirm(q)
        QuotationService.send(q)
        QuotationService.accept(q)

        NCFSequenceFactory(organization=customer.organization, ncf_type=31, current_seq=0)
        invoice = QuotationService.convert_to_invoice(q, ncf_type=31)

        assert invoice.doc_type == SalesDocument.DocType.INVOICE
        assert invoice.status == SalesDocument.Status.DRAFT
        assert invoice.customer == customer
        assert invoice.items.count() == q.items.count()

        q.refresh_from_db()
        assert q.status == SalesDocument.Status.CONVERTED

    def test_convert_raises_if_not_accepted(self):
        q = self._draft_quotation()
        QuotationService.confirm(q)
        with pytest.raises(ValueError, match="aceptadas"):
            QuotationService.convert_to_invoice(q, ncf_type=31)

    def test_expire_bulk_marks_expired(self):
        from datetime import timedelta
        customer = CustomerFactory()
        org = customer.organization
        q = self._draft_quotation(customer=customer)
        QuotationService.confirm(q)
        QuotationService.send(q)

        # Back-date valid_until so it's in the past
        q.valid_until = timezone.now().date() - timedelta(days=1)
        q.save(update_fields=["valid_until"])

        count = QuotationService.expire_bulk(org)
        assert count >= 1
        q.refresh_from_db()
        assert q.status == SalesDocument.Status.EXPIRED


# ─ SaleOrderService.consolidate_and_invoice ────────────

@pytest.mark.django_db
class TestSaleOrderConsolidate:

    def _draft_order(self, org, customer, *, with_item=True):
        order = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.SALE_ORDER,
            status=SalesDocument.Status.DRAFT,
            issue_date=timezone.now().date(),
        )
        if with_item:
            SalesDocumentItemFactory(
                document=order,
                quantity=Decimal("1"),
                unit_price=Decimal("1000.00"),
                itbis_rate=SalesDocumentItem.ITBISRate.RATE_18,
            )
            order.recompute_totals()
            order.refresh_from_db()
        return order

    def test_consolidate_pulls_draft_orders(self):
        from apps.sales.services import SaleOrderService
        customer = CustomerFactory()
        org = customer.organization
        today = timezone.now().date()
        o1 = self._draft_order(org, customer)
        o2 = self._draft_order(org, customer)

        invoice = SaleOrderService.consolidate_and_invoice(
            organization=org,
            customer=customer,
            period_start=today,
            period_end=today,
            ncf_type=31,
        )

        assert invoice.doc_type == SalesDocument.DocType.INVOICE
        assert invoice.status == SalesDocument.Status.DRAFT
        assert invoice.items.count() == 2
        for o in (o1, o2):
            o.refresh_from_db()
            assert o.status == SalesDocument.Status.INVOICED
            assert o.consolidated_into_id == invoice.pk

    def test_consolidate_skips_empty_orders(self):
        from apps.sales.services import SaleOrderService
        customer = CustomerFactory()
        org = customer.organization
        today = timezone.now().date()
        good = self._draft_order(org, customer)
        empty = self._draft_order(org, customer, with_item=False)

        invoice = SaleOrderService.consolidate_and_invoice(
            organization=org,
            customer=customer,
            period_start=today,
            period_end=today,
            ncf_type=31,
        )

        # Only the order with a line produced a consolidated line.
        assert invoice.items.count() == 1
        empty.refresh_from_db()
        assert empty.status == SalesDocument.Status.DRAFT
        assert empty.consolidated_into_id is None
