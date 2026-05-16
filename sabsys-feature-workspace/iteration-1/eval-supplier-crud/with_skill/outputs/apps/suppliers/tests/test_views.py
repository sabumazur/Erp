import pytest
from django.urls import reverse
from apps.suppliers.models import Supplier
from apps.suppliers.tests.factories import SupplierFactory


@pytest.mark.django_db
class TestSupplierViews:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    # ------------------------------------------------------------------ list --

    def test_list_requires_login(self, client):
        response = client.get(reverse("suppliers:supplier_list"))
        assert response.status_code == 302

    def test_list_accessible_to_member(self, client, member_membership):
        self._login(client, member_membership)
        response = client.get(reverse("suppliers:supplier_list"))
        assert response.status_code == 200

    def test_list_only_shows_org_suppliers(self, client, member_membership):
        own = SupplierFactory(organization=member_membership.organization)
        other = SupplierFactory()  # different org
        self._login(client, member_membership)
        response = client.get(reverse("suppliers:supplier_list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert own.name in content
        assert other.name not in content

    # ----------------------------------------------------------------- detail --

    def test_detail_accessible_to_member(self, client, member_membership):
        supplier = SupplierFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.get(reverse("suppliers:supplier_detail", args=[supplier.pk]))
        assert response.status_code == 200

    def test_detail_404_for_other_org(self, client, member_membership):
        supplier = SupplierFactory()  # different org
        self._login(client, member_membership)
        response = client.get(reverse("suppliers:supplier_detail", args=[supplier.pk]))
        assert response.status_code == 404

    # ----------------------------------------------------------------- create --

    def test_create_requires_admin(self, client, member_membership):
        self._login(client, member_membership)
        response = client.post(
            reverse("suppliers:supplier_create"),
            {"name": "Nuevo Proveedor", "status": Supplier.Status.ACTIVE},
        )
        assert response.status_code == 403

    def test_create_admin_can_create(self, client, admin_membership):
        self._login(client, admin_membership)
        response = client.post(
            reverse("suppliers:supplier_create"),
            {
                "name": "Proveedor Test",
                "rnc": "",
                "phone": "809-555-0000",
                "email": "test@proveedor.com",
                "status": Supplier.Status.ACTIVE,
            },
        )
        assert response.status_code == 302
        assert Supplier.objects.for_org(admin_membership.organization).filter(
            name="Proveedor Test"
        ).exists()

    # ------------------------------------------------------------------ edit --

    def test_edit_requires_admin(self, client, member_membership):
        supplier = SupplierFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.post(
            reverse("suppliers:supplier_edit", args=[supplier.pk]),
            {"name": "Cambiado", "status": Supplier.Status.ACTIVE},
        )
        assert response.status_code == 403

    def test_edit_admin_can_update(self, client, admin_membership):
        supplier = SupplierFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.post(
            reverse("suppliers:supplier_edit", args=[supplier.pk]),
            {
                "name": "Nombre Actualizado",
                "rnc": supplier.rnc,
                "phone": supplier.phone,
                "email": supplier.email,
                "status": Supplier.Status.INACTIVE,
            },
        )
        assert response.status_code == 302
        supplier.refresh_from_db()
        assert supplier.name == "Nombre Actualizado"
        assert supplier.status == Supplier.Status.INACTIVE

    def test_edit_404_for_other_org(self, client, admin_membership):
        supplier = SupplierFactory()  # different org
        self._login(client, admin_membership)
        response = client.post(
            reverse("suppliers:supplier_edit", args=[supplier.pk]),
            {"name": "Hack", "status": Supplier.Status.ACTIVE},
        )
        assert response.status_code == 404

    # ----------------------------------------------------------------- delete --

    def test_delete_requires_admin(self, client, member_membership):
        supplier = SupplierFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.post(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        assert response.status_code == 403

    def test_delete_soft_deletes_supplier(self, client, admin_membership):
        supplier = SupplierFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.post(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        assert response.status_code == 302
        supplier.refresh_from_db()
        assert supplier.deleted_at is not None  # soft-deleted

    def test_delete_404_for_other_org(self, client, admin_membership):
        supplier = SupplierFactory()  # different org
        self._login(client, admin_membership)
        response = client.post(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        assert response.status_code == 404

    def test_deleted_supplier_not_in_list(self, client, admin_membership):
        supplier = SupplierFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        client.post(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        response = client.get(reverse("suppliers:supplier_list"))
        assert supplier.name not in response.content.decode()
