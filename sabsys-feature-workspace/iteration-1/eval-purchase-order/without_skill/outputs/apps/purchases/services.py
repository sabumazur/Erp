"""
apps/purchases/services.py

Business-logic services for the purchases app.

All public methods assume they are called from within a request/view context
where request.organization is already set.
"""
import logging

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import PurchaseOrder, PurchaseOrderSequence

logger = logging.getLogger(__name__)


class PurchaseOrderService:
    """
    State-machine transitions for PurchaseOrder documents.

    Lifecycle:
        DRAFT → CONFIRMED → RECEIVED
                          → CANCELLED
        DRAFT → CANCELLED
    """

    @staticmethod
    @transaction.atomic
    def confirm(order: PurchaseOrder) -> PurchaseOrder:
        """
        Transition a PurchaseOrder from DRAFT → CONFIRMED.

        Atomically assigns the next sequential purchase order number
        from the organization's PurchaseOrderSequence.

        Raises:
            ValueError — if the order is not in DRAFT status.
        """
        if order.status != PurchaseOrder.Status.DRAFT:
            raise ValueError(
                _(
                    "Solo se pueden confirmar órdenes de compra en Borrador. "
                    "Estado actual: %(status)s."
                ) % {"status": order.get_status_display()}
            )

        number = PurchaseOrderSequence.generate(order.organization)
        order.number = number
        order.status = PurchaseOrder.Status.CONFIRMED
        order.save(update_fields=["number", "status", "updated_at"])

        logger.info(
            "PurchaseOrder %s confirmed: %s (org=%s)",
            order.pk, order.number, order.organization_id,
        )
        return order

    @staticmethod
    @transaction.atomic
    def receive(order: PurchaseOrder) -> PurchaseOrder:
        """
        Transition a PurchaseOrder from CONFIRMED → RECEIVED.

        Marks the order as fully received. Only CONFIRMED orders
        may be received; DRAFT orders must first be confirmed.

        Raises:
            ValueError — if the order is not in CONFIRMED status.
        """
        if order.status != PurchaseOrder.Status.CONFIRMED:
            raise ValueError(
                _(
                    "Solo se pueden marcar como recibidas órdenes confirmadas. "
                    "Estado actual: %(status)s."
                ) % {"status": order.get_status_display()}
            )

        order.status = PurchaseOrder.Status.RECEIVED
        order.save(update_fields=["status", "updated_at"])

        logger.info(
            "PurchaseOrder %s received (org=%s)",
            order.pk, order.organization_id,
        )
        return order

    @staticmethod
    @transaction.atomic
    def cancel(order: PurchaseOrder) -> PurchaseOrder:
        """
        Cancel a PurchaseOrder (DRAFT or CONFIRMED → CANCELLED).

        RECEIVED orders cannot be cancelled.

        Raises:
            ValueError — if the order is already RECEIVED or CANCELLED.
        """
        if order.status == PurchaseOrder.Status.RECEIVED:
            raise ValueError(
                _("No se puede anular una orden de compra que ya fue recibida.")
            )
        if order.status == PurchaseOrder.Status.CANCELLED:
            raise ValueError(_("La orden de compra ya está anulada."))

        order.status = PurchaseOrder.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])

        logger.info(
            "PurchaseOrder %s cancelled (org=%s)",
            order.pk, order.organization_id,
        )
        return order
