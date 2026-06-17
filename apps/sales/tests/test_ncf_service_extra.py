"""
Tests for NCFService transitions that were missing from the original suite.

Gaps covered:
  - NCFService.mark_overdue_bulk
  - NCFService.reopen
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounts.tests.factories import OrganizationFactory
from apps.sales.models import SalesDocument
from apps.sales.services import NCFService
from .factories import CustomerFactory, SalesDocumentFactory, NCFSequenceFactory


# ── helpers ───────────────────────────────────────────────────────────────────

def make_confirmed_invoice(org, customer, *, due_date=None):
    """Create a confirmed invoice with a past due_date (SENT status)."""
    NCFSequenceFactory(organization=org, ncf_type=31)
    inv = SalesDocumentFactory(
        organization=org,
        customer=customer,
        ncf_type=31,
        status=SalesDocument.Status.DRAFT,
        due_date=due_date or (date.today() - timedelta(days=10)),
    )
    NCFService.confirm(inv)
    inv.refresh_from_db()
    # Manually move to SENT to mimic send workflow
    inv.status = SalesDocument.Status.SENT
    inv.save(update_fields=["status", "updated_at"])
    inv.refresh_from_db()
    return inv


# ── NCFService.mark_overdue_bulk ──────────────────────────────────────────────

@pytest.mark.django_db
class TestNCFMarkOverdueBulk:

    def test_marks_sent_overdue_invoices(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(
            org, customer, due_date=date.today() - timedelta(days=5)
        )
        assert inv.status == SalesDocument.Status.SENT

        count = NCFService.mark_overdue_bulk(org)

        inv.refresh_from_db()
        assert count >= 1
        assert inv.status == SalesDocument.Status.OVERDUE

    def test_does_not_mark_future_due_invoices(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(
            org, customer, due_date=date.today() + timedelta(days=30)
        )

        NCFService.mark_overdue_bulk(org)

        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.SENT

    def test_does_not_affect_other_orgs(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = make_confirmed_invoice(
            org, customer, due_date=date.today() - timedelta(days=1)
        )

        other_org = OrganizationFactory()
        NCFService.mark_overdue_bulk(other_org)

        inv.refresh_from_db()
        # Should still be SENT — not affected by other org bulk update
        assert inv.status == SalesDocument.Status.SENT

    def test_returns_count_of_updated(self):
        customer = CustomerFactory()
        org = customer.organization
        # Create 3 overdue invoices (NCFSequence is unique per org+ncf_type — create once)
        NCFSequenceFactory(organization=org, ncf_type=31)
        for _ in range(3):
            inv = SalesDocumentFactory(
                organization=org,
                customer=customer,
                ncf_type=31,
                status=SalesDocument.Status.SENT,
                due_date=date.today() - timedelta(days=1),
            )

        count = NCFService.mark_overdue_bulk(org)
        assert count >= 3

    def test_does_not_mark_paid_invoices(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = SalesDocumentFactory(
            organization=org,
            customer=customer,
            status=SalesDocument.Status.PAID,
            due_date=date.today() - timedelta(days=1),
        )

        NCFService.mark_overdue_bulk(org)

        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.PAID


# ── NCFService.reopen ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNCFReopen:

    def test_transitions_paid_to_sent(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.INVOICE,
            ncf_type=31,
            status=SalesDocument.Status.PAID,
        )

        NCFService.reopen(inv)

        inv.refresh_from_db()
        assert inv.status == SalesDocument.Status.SENT

    def test_raises_when_not_paid(self):
        customer = CustomerFactory()
        org = customer.organization
        inv = SalesDocumentFactory(
            organization=org,
            customer=customer,
            status=SalesDocument.Status.CONFIRMED,
        )

        with pytest.raises(ValueError, match="Pagada"):
            NCFService.reopen(inv)

    def test_raises_for_credit_note(self):
        customer = CustomerFactory()
        org = customer.organization
        # Create a parent CONFIRMED invoice so the credit note can reference it
        parent = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.INVOICE,
            ncf_type=31,
            status=SalesDocument.Status.CONFIRMED,
        )
        # Set encf directly — bypasses full_clean so we don't need the full NCF flow
        SalesDocument.objects.filter(pk=parent.pk).update(encf="E310000000001")
        parent.refresh_from_db()

        credit_note = SalesDocumentFactory(
            organization=org,
            customer=customer,
            doc_type=SalesDocument.DocType.INVOICE,
            ncf_type=34,  # Nota de Crédito (e-CF)
            status=SalesDocument.Status.PAID,
            encf_modified=parent,
        )

        with pytest.raises(ValueError):
            NCFService.reopen(credit_note)
