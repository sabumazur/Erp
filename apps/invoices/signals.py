"""
apps/invoices/signals.py
Post-save signals that keep Invoice totals in sync whenever line items change.
"""
import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import InvoiceItem

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InvoiceItem)
def recompute_invoice_on_item_save(sender, instance, **kwargs):
    """
    Recompute Invoice subtotal / itbis_18 / itbis_16 / total every time
    a line item is saved.

    Note: InvoiceItem.save() already calls compute() to populate its own
    line_total / itbis_amount fields before this signal fires, so the values
    read here are always up to date.
    """
    instance.invoice.recompute_totals()


@receiver(post_delete, sender=InvoiceItem)
def recompute_invoice_on_item_delete(sender, instance, **kwargs):
    """Recompute totals when a line item is removed."""
    try:
        instance.invoice.recompute_totals()
    except Exception:
        logger.exception("recompute_totals failed after InvoiceItem delete (invoice may have been deleted)")
