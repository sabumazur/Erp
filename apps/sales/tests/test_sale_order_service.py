"""
Tests for SaleOrderService transitions that were missing from the original suite.

Gaps covered:
  - SaleOrderService.mark_delivered
  - SaleOrderService.cancel
"""
from decimal import Decimal

import pytest

from apps.sales.models import SalesDocument, SalesDocumentItem
from apps.sales.services import SaleOrderService
from .factories import (
    CustomerFactory,
    SalesDocumentFactory,
    SalesDocumentItemFactory,
    NCFSequenceFactory,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def make_confirmed_order(organization, customer):
    """Return a CONFIRMED sale order with one line item."""
    order = SalesDocumentFactory(
        organization=organization,
        customer=customer,
        doc_type=SalesDocument.DocType.SALE_ORDER,
        status=SalesDocument.Status.CONFIRMED,
        doc_number="OV-0001",
    )
    SalesDocumentItemFactory(document=order)
    return order


def make_draft_order(organization, customer):
    return SalesDocumentFactory(
        organization=organization,
        customer=customer,
        doc_type=SalesDocument.DocType.SALE_ORDER,
        status=SalesDocument.Status.DRAFT,
    )


# ── SaleOrderService.mark_delivered ──────────────────────────────────────────

@pytest.mark.django_db
class TestSaleOrderMarkDelivered:

    def test_transitions_confirmed_to_delivered(self):
        customer = CustomerFactory()
        org = customer.organization
        order = make_confirmed_order(org, customer)

        result = SaleOrderService.mark_delivered(order, signed_by="Juan Pérez")

        order.refresh_from_db()
        assert order.status == SalesDocument.Status.DELIVERED
        assert order.signed_by == "Juan Pérez"
        assert result == order

    def test_raises_when_order_not_confirmed(self):
        customer = CustomerFactory()
        org = customer.organization
        order = make_draft_order(org, customer)

        with pytest.raises(ValueError, match="confirmadas"):
            SaleOrderService.mark_delivered(order, signed_by="Juan")

    def test_allows_blank_signed_by(self):
        customer = CustomerFactory()
        org = customer.organization
        order = make_confirmed_order(org, customer)

        result = SaleOrderService.mark_delivered(order, signed_by="")
        assert result.signed_by == ""
        assert result.status == SalesDocument.Status.DELIVERED

    def test_strips_signed_by(self):
        customer = CustomerFactory()
        org = customer.organization
        order = make_confirmed_order(org, customer)

        SaleOrderService.mark_delivered(order, signed_by="  Ana  ")

        order.refresh_from_db()
        assert order.signed_by == "Ana"

    def test_raises_when_wrong_doc_type(self):
        customer = CustomerFactory()
        org = customer.organization
        # Create an invoice, not a sale order
        invoice = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.INVOICE,
            status=SalesDocument.Status.CONFIRMED,
        )

        with pytest.raises(ValueError, match="orden de venta"):
            SaleOrderService.mark_delivered(invoice, signed_by="Alguien")


# ── SaleOrderService.cancel ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestSaleOrderCancel:

    def test_cancels_draft_order(self):
        customer = CustomerFactory()
        org = customer.organization
        order = make_draft_order(org, customer)

        SaleOrderService.cancel(order)

        order.refresh_from_db()
        assert order.status == SalesDocument.Status.CANCELLED

    def test_cancels_confirmed_order(self):
        customer = CustomerFactory()
        org = customer.organization
        order = make_confirmed_order(org, customer)

        SaleOrderService.cancel(order)

        order.refresh_from_db()
        assert order.status == SalesDocument.Status.CANCELLED

    def test_raises_when_already_cancelled(self):
        customer = CustomerFactory()
        org = customer.organization
        order = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.SALE_ORDER,
            status=SalesDocument.Status.CANCELLED,
        )

        with pytest.raises(ValueError, match="ya está anulada"):
            SaleOrderService.cancel(order)

    def test_raises_when_delivered(self):
        customer = CustomerFactory()
        org = customer.organization
        order = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.SALE_ORDER,
            status=SalesDocument.Status.DELIVERED,
        )

        with pytest.raises(ValueError, match="entregada"):
            SaleOrderService.cancel(order)

    def test_raises_when_invoiced(self):
        customer = CustomerFactory()
        org = customer.organization
        order = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.SALE_ORDER,
            status=SalesDocument.Status.INVOICED,
        )

        with pytest.raises(ValueError, match="facturada"):
            SaleOrderService.cancel(order)

    def test_raises_when_wrong_doc_type(self):
        customer = CustomerFactory()
        org = customer.organization
        invoice = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.INVOICE,
            status=SalesDocument.Status.DRAFT,
        )

        with pytest.raises(ValueError, match="orden de venta"):
            SaleOrderService.cancel(invoice)
