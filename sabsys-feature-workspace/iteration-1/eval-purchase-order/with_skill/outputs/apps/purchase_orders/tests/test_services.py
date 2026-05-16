"""
Tests for PurchaseOrderService status transitions.
"""
import pytest

from apps.purchase_orders.models import PurchaseOrder
from apps.purchase_orders.services import PurchaseOrderService
from .factories import PurchaseOrderFactory, SupplierFactory


# ── PurchaseOrderService.confirm ───────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderServiceConfirm:

    def test_confirm_transitions_draft_to_confirmed(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        PurchaseOrderService.confirm(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CONFIRMED

    def test_confirm_assigns_number(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        PurchaseOrderService.confirm(order)
        order.refresh_from_db()
        assert order.number != ""
        assert order.number.startswith("OC-")

    def test_confirm_number_is_sequential(self):
        org = SupplierFactory().organization
        o1 = PurchaseOrderFactory(
            organization=org,
            supplier=SupplierFactory(organization=org),
        )
        o2 = PurchaseOrderFactory(
            organization=org,
            supplier=SupplierFactory(organization=org),
        )
        PurchaseOrderService.confirm(o1)
        PurchaseOrderService.confirm(o2)
        o1.refresh_from_db()
        o2.refresh_from_db()
        # Numbers should be different
        assert o1.number != o2.number
        # o2 should be greater than o1
        assert o2.number > o1.number

    def test_confirm_raises_if_not_draft(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.CONFIRMED)
        with pytest.raises(ValueError, match="Borrador"):
            PurchaseOrderService.confirm(order)

    def test_confirm_raises_if_cancelled(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.CANCELLED)
        with pytest.raises(ValueError):
            PurchaseOrderService.confirm(order)

    def test_confirm_raises_if_received(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.RECEIVED)
        with pytest.raises(ValueError):
            PurchaseOrderService.confirm(order)


# ── PurchaseOrderService.receive ───────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderServiceReceive:

    def test_receive_transitions_confirmed_to_received(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        PurchaseOrderService.confirm(order)
        PurchaseOrderService.receive(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.RECEIVED

    def test_receive_raises_if_draft(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        with pytest.raises(ValueError, match="confirmadas"):
            PurchaseOrderService.receive(order)

    def test_receive_raises_if_cancelled(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.CANCELLED)
        with pytest.raises(ValueError):
            PurchaseOrderService.receive(order)

    def test_receive_raises_if_already_received(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.RECEIVED)
        with pytest.raises(ValueError):
            PurchaseOrderService.receive(order)


# ── PurchaseOrderService.cancel ────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderServiceCancel:

    def test_cancel_draft_order(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        PurchaseOrderService.cancel(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED

    def test_cancel_confirmed_order(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        PurchaseOrderService.confirm(order)
        PurchaseOrderService.cancel(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED

    def test_cancel_raises_if_received(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.RECEIVED)
        with pytest.raises(ValueError, match="recibida"):
            PurchaseOrderService.cancel(order)

    def test_cancel_raises_if_already_cancelled(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.CANCELLED)
        with pytest.raises(ValueError, match="anulada"):
            PurchaseOrderService.cancel(order)


# ── Full lifecycle ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderLifecycle:

    def test_full_happy_path_draft_confirmed_received(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)

        assert order.status == PurchaseOrder.Status.DRAFT
        assert order.number == ""

        PurchaseOrderService.confirm(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CONFIRMED
        assert order.number.startswith("OC-")

        PurchaseOrderService.receive(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.RECEIVED

    def test_cancel_from_draft(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        PurchaseOrderService.cancel(order)
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED

    def test_cannot_receive_after_cancel(self):
        order = PurchaseOrderFactory(status=PurchaseOrder.Status.DRAFT)
        PurchaseOrderService.confirm(order)
        PurchaseOrderService.cancel(order)
        with pytest.raises(ValueError):
            PurchaseOrderService.receive(order)
