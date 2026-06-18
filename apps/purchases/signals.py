"""
apps/purchases/signals.py
Cache-invalidation signals for the purchases report views.

Cached purchase reports embed a per-org generation value in their cache key
(see apps/purchases/views/reports.py). Bumping the generation on every
mutation makes stale keys unreachable without deleting them explicitly.
"""
import logging
import time

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import PurchaseDocument, PurchaseDocumentItem, SupplierPayment

logger = logging.getLogger(__name__)


def _bump_purchases_report_gen(org_id):
    cache.set(f"purchases_report_gen:{org_id}", int(time.time()), timeout=None)


@receiver(post_save, sender=PurchaseDocument)
def invalidate_reports_on_doc_save(sender, instance, **kwargs):
    _bump_purchases_report_gen(instance.organization_id)


@receiver(post_delete, sender=PurchaseDocument)
def invalidate_reports_on_doc_delete(sender, instance, **kwargs):
    _bump_purchases_report_gen(instance.organization_id)


@receiver(post_save, sender=SupplierPayment)
def invalidate_reports_on_payment_save(sender, instance, **kwargs):
    _bump_purchases_report_gen(instance.organization_id)


@receiver(post_delete, sender=SupplierPayment)
def invalidate_reports_on_payment_delete(sender, instance, **kwargs):
    _bump_purchases_report_gen(instance.organization_id)


@receiver(post_save, sender=PurchaseDocumentItem)
def invalidate_reports_on_item_save(sender, instance, **kwargs):
    # ReportITBISCreditsView aggregates PurchaseDocumentItem rows directly,
    # so item-level mutations must bump the generation too.
    _bump_purchases_report_gen(instance.purchase_document.organization_id)


@receiver(post_delete, sender=PurchaseDocumentItem)
def invalidate_reports_on_item_delete(sender, instance, **kwargs):
    try:
        _bump_purchases_report_gen(instance.purchase_document.organization_id)
    except Exception:
        logger.exception("purchases report gen bump failed after item delete (document may have been deleted)")
