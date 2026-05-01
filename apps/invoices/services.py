"""
apps/invoices/services.py
Business-logic services for the invoices app.

All public functions assume they are called from within a request/view context
where request.organization is already set.
"""
from django.db import transaction
from django.utils import timezone

from .models import Invoice, NCFSequence


class NCFService:
    """
    Handles the atomic assignment of an e-NCF to a confirmed Invoice.

    Usage (inside a view POST handler):
        try:
            NCFService.confirm(invoice)
        except ValueError as exc:
            messages.error(request, str(exc))
    """

    @staticmethod
    @transaction.atomic
    def confirm(invoice: Invoice) -> Invoice:
        """
        Transition an Invoice from DRAFT → CONFIRMED by assigning the next
        e-NCF from the organization's active sequence for the invoice's NCF type.

        Raises:
            ValueError  — if the invoice is not in DRAFT status, if no active
                          sequence exists for this NCF type, or if the sequence
                          is exhausted.
            ValidationError — if the invoice fails DGII business-rule validation
                              (e.g. missing RNC for Crédito Fiscal).
        """
        if invoice.status != Invoice.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden confirmar facturas en estado Borrador. "
                f"Estado actual: {invoice.get_status_display()}."
            )

        # Run DGII field-level validation
        invoice.full_clean()

        # Assign next e-NCF atomically
        encf = NCFSequence.generate(invoice.organization, invoice.ncf_type)

        invoice.encf = encf
        invoice.status = Invoice.Status.CONFIRMED
        invoice.save(update_fields=["encf", "status", "updated_at"])

        return invoice

    @staticmethod
    def mark_sent(invoice: Invoice) -> Invoice:
        """Transition CONFIRMED → SENT."""
        if invoice.status != Invoice.Status.CONFIRMED:
            raise ValueError("Solo se pueden enviar facturas confirmadas.")
        invoice.status = Invoice.Status.SENT
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    def mark_paid(invoice: Invoice, payment) -> Invoice:
        """Transition CONFIRMED / SENT / OVERDUE → PAID."""
        allowed = (Invoice.Status.CONFIRMED, Invoice.Status.SENT, Invoice.Status.OVERDUE)
        if invoice.status not in allowed:
            raise ValueError("La factura no puede marcarse como pagada en su estado actual.")
        invoice.status = Invoice.Status.PAID
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    def cancel(invoice: Invoice) -> Invoice:
        """
        Cancel a confirmed/sent/overdue invoice.
        The e-NCF is retained (to appear in format 608) and the invoice is
        soft-deleted after status change.
        DRAFT invoices are just hard-deleted (no e-NCF was assigned).
        """
        if invoice.status == Invoice.Status.PAID:
            raise ValueError(
                "No se puede anular una factura pagada. "
                "Emita una Nota de Crédito en su lugar."
            )
        if invoice.status == Invoice.Status.CANCELLED:
            raise ValueError("La factura ya está anulada.")

        invoice.status = Invoice.Status.CANCELLED
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    def mark_overdue_bulk(organization) -> int:
        """
        Mark all SENT invoices with a past due_date as OVERDUE.
        Intended to be called from a management command or Celery beat task.
        Returns the count of invoices updated.
        """
        today = timezone.now().date()
        updated = (
            Invoice.objects
            .filter(
                organization=organization,
                status=Invoice.Status.SENT,
                due_date__lt=today,
            )
            .update(status=Invoice.Status.OVERDUE)
        )
        return updated
