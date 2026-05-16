"""
apps/purchase_orders/services.py
Business-logic services for the purchase_orders app.
"""
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import PurchaseOrder


def _next_po_number(organization) -> str:
    """
    Generate the next sequential PO number for the organization.

    Format: OC-{year}-{zero-padded 5-digit counter}
    e.g.  OC-2026-00001

    Uses SELECT FOR UPDATE on the latest confirmed/received/cancelled order to
    avoid duplicate numbers under concurrent requests.
    """
    from django.utils import timezone

    year = timezone.now().year
    prefix = f"OC-{year}-"

    # Lock the highest existing number for this org+year to prevent races.
    last = (
        PurchaseOrder.all_objects.select_for_update()
        .filter(organization=organization, number__startswith=prefix)
        .order_by("-number")
        .first()
    )

    if last and last.number:
        try:
            seq = int(last.number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1

    return f"{prefix}{seq:05d}"


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

        Atomically assigns the next sequential PO number for the organization.

        Raises:
            ValueError — if the order is not in DRAFT status.
        """
        if order.status != PurchaseOrder.Status.DRAFT:
            raise ValueError(
                _(
                    "Solo se pueden confirmar órdenes de compra en estado Borrador. "
                    "Estado actual: %(status)s."
                )
                % {"status": order.get_status_display()}
            )

        order.number = _next_po_number(order.organization)
        order.status = PurchaseOrder.Status.CONFIRMED
        order.save(update_fields=["number", "status", "updated_at"])
        return order

    @staticmethod
    @transaction.atomic
    def receive(order: PurchaseOrder) -> PurchaseOrder:
        """
        Transition a PurchaseOrder from CONFIRMED → RECEIVED.

        Raises:
            ValueError — if the order is not in CONFIRMED status.
        """
        if order.status != PurchaseOrder.Status.CONFIRMED:
            raise ValueError(
                _(
                    "Solo se pueden marcar como recibidas las órdenes confirmadas. "
                    "Estado actual: %(status)s."
                )
                % {"status": order.get_status_display()}
            )

        order.status = PurchaseOrder.Status.RECEIVED
        order.save(update_fields=["status", "updated_at"])
        return order

    @staticmethod
    @transaction.atomic
    def cancel(order: PurchaseOrder) -> PurchaseOrder:
        """
        Transition a PurchaseOrder from DRAFT or CONFIRMED → CANCELLED.

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
        return order
