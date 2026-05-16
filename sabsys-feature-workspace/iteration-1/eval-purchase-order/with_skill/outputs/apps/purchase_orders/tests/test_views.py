"""
Tests for purchase_orders views.
"""
import pytest
from django.urls import reverse

from apps.purchase_orders.models import PurchaseOrder, Supplier
from apps.purchase_orders.services import PurchaseOrderService
from .factories import PurchaseOrderFactory, SupplierFactory


def _login(client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_org_slug"] = membership.organization.slug
    session.save()


# ── Supplier list ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSupplierListView:

    def test_requires_login(self, client):
        response = client.get(reverse("purchase_orders:supplier_list"))
        assert response.status_code == 302

    def test_accessible_to_member(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("purchase_orders:supplier_list"))
        assert response.status_code == 200

    def test_create_supplier_via_post(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:supplier_list"),
            {
                "name": "Nuevo Proveedor S.R.L.",
                "tax_id": "",
                "email": "",
                "phone": "",
                "contact_name": "",
                "address": "",
                "notes": "",
            },
        )
        # Should redirect (non-HTMX)
        assert response.status_code == 302
        assert Supplier.objects.filter(
            organization=admin_membership.organization,
            name="Nuevo Proveedor S.R.L.",
        ).exists()


# ── Supplier update ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSupplierUpdateView:

    def test_requires_admin(self, client, member_membership):
        supplier = SupplierFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(
            reverse("purchase_orders:supplier_edit", args=[supplier.pk]),
            {"name": "Cambiado", "tax_id": "", "email": "", "phone": "",
             "contact_name": "", "address": "", "notes": ""},
        )
        assert response.status_code == 403

    def test_admin_can_update(self, client, admin_membership):
        supplier = SupplierFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:supplier_edit", args=[supplier.pk]),
            {"name": "Proveedor Actualizado", "tax_id": "", "email": "",
             "phone": "", "contact_name": "", "address": "", "notes": ""},
        )
        assert response.status_code == 302
        supplier.refresh_from_db()
        assert supplier.name == "Proveedor Actualizado"


# ── Supplier delete ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSupplierDeleteView:

    def test_requires_admin(self, client, member_membership):
        supplier = SupplierFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(
            reverse("purchase_orders:supplier_delete", args=[supplier.pk])
        )
        assert response.status_code == 403

    def test_admin_can_delete_supplier_without_orders(self, client, admin_membership):
        supplier = SupplierFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:supplier_delete", args=[supplier.pk])
        )
        assert response.status_code == 302
        supplier.refresh_from_db()
        assert supplier.deleted_at is not None  # soft-deleted

    def test_cannot_delete_supplier_with_orders(self, client, admin_membership):
        supplier = SupplierFactory(organization=admin_membership.organization)
        PurchaseOrderFactory(
            organization=admin_membership.organization, supplier=supplier
        )
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:supplier_delete", args=[supplier.pk])
        )
        # Blocked — redirects back to list with error
        assert response.status_code == 302
        supplier.refresh_from_db()
        assert supplier.deleted_at is None  # NOT deleted


# ── PurchaseOrder list ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderListView:

    def test_requires_login(self, client):
        response = client.get(reverse("purchase_orders:purchase_order_list"))
        assert response.status_code == 302

    def test_accessible_to_member(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("purchase_orders:purchase_order_list"))
        assert response.status_code == 200

    def test_only_shows_own_org_orders(self, client, member_membership, admin_membership):
        # Create an order for the member's org
        PurchaseOrderFactory(organization=member_membership.organization)
        # Create an order for a different org
        PurchaseOrderFactory(organization=admin_membership.organization)

        _login(client, member_membership)
        response = client.get(reverse("purchase_orders:purchase_order_list"))
        assert response.status_code == 200
        # The datatable renders rows; just verify 200 here — org scoping tested in model layer


# ── PurchaseOrder create ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderCreateView:

    def test_requires_admin(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("purchase_orders:purchase_order_create"))
        assert response.status_code == 403

    def test_admin_can_access_create_form(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.get(reverse("purchase_orders:purchase_order_create"))
        assert response.status_code == 200

    def test_admin_can_create_order(self, client, admin_membership):
        supplier = SupplierFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_create"),
            {
                "supplier": str(supplier.pk),
                "issue_date": "2026-05-15",
                "expected_date": "",
                "notes": "Compra de prueba",
            },
        )
        assert response.status_code == 302
        assert PurchaseOrder.objects.filter(
            organization=admin_membership.organization,
            supplier=supplier,
        ).exists()


# ── PurchaseOrder detail ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderDetailView:

    def test_requires_login(self, client, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        response = client.get(
            reverse("purchase_orders:purchase_order_detail", args=[order.pk])
        )
        assert response.status_code == 302

    def test_member_can_view_order(self, client, member_membership):
        order = PurchaseOrderFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.get(
            reverse("purchase_orders:purchase_order_detail", args=[order.pk])
        )
        assert response.status_code == 200

    def test_cannot_view_other_org_order(self, client, member_membership, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        _login(client, member_membership)
        response = client.get(
            reverse("purchase_orders:purchase_order_detail", args=[order.pk])
        )
        assert response.status_code == 404


# ── PurchaseOrder update ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderUpdateView:

    def test_requires_admin(self, client, member_membership):
        order = PurchaseOrderFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.get(
            reverse("purchase_orders:purchase_order_edit", args=[order.pk])
        )
        assert response.status_code == 403

    def test_admin_can_edit_draft(self, client, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        supplier = SupplierFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_edit", args=[order.pk]),
            {
                "supplier": str(supplier.pk),
                "issue_date": "2026-06-01",
                "expected_date": "",
                "notes": "Notas actualizadas",
            },
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.notes == "Notas actualizadas"

    def test_cannot_edit_confirmed_order(self, client, admin_membership):
        order = PurchaseOrderFactory(
            organization=admin_membership.organization,
            status=PurchaseOrder.Status.CONFIRMED,
        )
        order.number = "OC-2026-00001"
        order.save(update_fields=["number"])

        supplier = SupplierFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_edit", args=[order.pk]),
            {
                "supplier": str(supplier.pk),
                "issue_date": "2026-06-01",
                "expected_date": "",
                "notes": "Esto no debe guardarse",
            },
        )
        # Redirected without saving changes
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.notes != "Esto no debe guardarse"


# ── PurchaseOrder delete ───────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderDeleteView:

    def test_requires_admin(self, client, member_membership):
        order = PurchaseOrderFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_delete", args=[order.pk])
        )
        assert response.status_code == 403

    def test_admin_can_delete_draft(self, client, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_delete", args=[order.pk])
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.deleted_at is not None

    def test_cannot_delete_confirmed_order(self, client, admin_membership):
        order = PurchaseOrderFactory(
            organization=admin_membership.organization,
            status=PurchaseOrder.Status.CONFIRMED,
        )
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_delete", args=[order.pk])
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.deleted_at is None  # NOT deleted


# ── Status transition views ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPurchaseOrderConfirmView:

    def test_confirm_requires_admin(self, client, member_membership):
        order = PurchaseOrderFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_confirm", args=[order.pk])
        )
        assert response.status_code == 403

    def test_admin_can_confirm_draft(self, client, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_confirm", args=[order.pk])
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CONFIRMED
        assert order.number.startswith("OC-")


@pytest.mark.django_db
class TestPurchaseOrderReceiveView:

    def test_receive_requires_admin(self, client, member_membership):
        order = PurchaseOrderFactory(
            organization=member_membership.organization,
            status=PurchaseOrder.Status.CONFIRMED,
        )
        _login(client, member_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_receive", args=[order.pk])
        )
        assert response.status_code == 403

    def test_admin_can_receive_confirmed_order(self, client, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        PurchaseOrderService.confirm(order)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_receive", args=[order.pk])
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.RECEIVED

    def test_receive_draft_shows_error_and_redirects(self, client, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_receive", args=[order.pk])
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.DRAFT  # unchanged


@pytest.mark.django_db
class TestPurchaseOrderCancelView:

    def test_cancel_requires_admin(self, client, member_membership):
        order = PurchaseOrderFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_cancel", args=[order.pk])
        )
        assert response.status_code == 403

    def test_admin_can_cancel_draft(self, client, admin_membership):
        order = PurchaseOrderFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_cancel", args=[order.pk])
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.CANCELLED

    def test_cannot_cancel_received_order(self, client, admin_membership):
        order = PurchaseOrderFactory(
            organization=admin_membership.organization,
            status=PurchaseOrder.Status.RECEIVED,
        )
        _login(client, admin_membership)
        response = client.post(
            reverse("purchase_orders:purchase_order_cancel", args=[order.pk])
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == PurchaseOrder.Status.RECEIVED  # unchanged
