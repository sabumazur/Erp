"""
apps/invoices/signals.py
Post-save signals that keep SalesDocument totals in sync whenever line items change.
"""
import logging
import threading
import time
from contextlib import contextmanager

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import SalesDocument, SalesDocumentItem, Payment

logger = logging.getLogger(__name__)

# Thread-local flag to suspend per-item recompute during bulk (formset) saves.
_recompute_state = threading.local()


@contextmanager
def suspend_recompute(document):
    """Suspend per-item ``recompute_totals`` while many line items are saved,
    then recompute the document totals exactly once on exit."""
    _recompute_state.suspended = True
    try:
        yield
    finally:
        _recompute_state.suspended = False
        document.recompute_totals()


def _recompute_suspended():
    return getattr(_recompute_state, "suspended", False)


def _bust_dashboard(org_id):
    cache.delete(f"dashboard:{org_id}")


def _bust_aging(org_id):
    cache.set(f"aging_gen:{org_id}", int(time.time()), timeout=None)


@receiver(post_save, sender=SalesDocument)
def invalidate_dashboard_on_doc_save(sender, instance, **kwargs):
    _bust_dashboard(instance.organization_id)
    _bust_aging(instance.organization_id)


@receiver(post_delete, sender=SalesDocument)
def invalidate_dashboard_on_doc_delete(sender, instance, **kwargs):
    _bust_dashboard(instance.organization_id)
    _bust_aging(instance.organization_id)


@receiver(post_save, sender=Payment)
def invalidate_dashboard_on_payment_save(sender, instance, **kwargs):
    _bust_dashboard(instance.organization_id)
    _bust_aging(instance.organization_id)


@receiver(post_delete, sender=Payment)
def invalidate_dashboard_on_payment_delete(sender, instance, **kwargs):
    _bust_dashboard(instance.organization_id)
    _bust_aging(instance.organization_id)


@receiver(post_save, sender=SalesDocumentItem)
def recompute_invoice_on_item_save(sender, instance, **kwargs):
    """
    Recompute SalesDocument subtotal / itbis_18 / itbis_16 / total every time
    a line item is saved.

    Note: SalesDocumentItem.save() already calls compute() to populate its own
    line_total / itbis_amount fields before this signal fires, so the values
    read here are always up to date.
    """
    if _recompute_suspended():
        return
    instance.document.recompute_totals()


@receiver(post_delete, sender=SalesDocumentItem)
def recompute_invoice_on_item_delete(sender, instance, **kwargs):
    """Recompute totals when a line item is removed."""
    if _recompute_suspended():
        return
    try:
        instance.document.recompute_totals()
    except Exception:
        logger.exception("recompute_totals failed after SalesDocumentItem delete (document may have been deleted)")
