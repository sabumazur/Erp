"""
Tests for supplier views — list, create, update, delete, permission guards.
"""
import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.suppliers.models import Supplier
from apps.suppliers.tests.factories import SupplierFactory


# ── Helpers ───────────────────────────────────────────────────────────────────

def login(client, user):
    client.force_login(user)


def make_member(role=Membership.Role.ADMIN):
    """Create an org + user + membership. Returns (user, org, membership)."""
    org        = OrganizationFactory()
    user       = UserFactory()
    membership = MembershipFactory(user=user, organization=org, role=role)
    return user, org, membership


def set_active_org(client, org):
    session = client.session
    session["active_org_slug"] = org.slug
    session.save()


# ── List view ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierListView:

    def test_list_requires_login(self, client):
        resp = client.get(reverse("suppliers:supplier_list"))
        assert resp.status_code in (302, 403)

    def test_list_accessible_to_member(self, client):
        user, org, _ = make_member(Membership.Role.MEMBER)
        login(client, user)
        set_active_org(client, org)
        resp = client.get(reverse("suppliers:supplier_list"))
        assert resp.status_code == 200

    def test_list_shows_only_org_suppliers(self, client):
        user, org, _ = make_member()
        other_org    = OrganizationFactory()
        login(client, user)
        set_active_org(client, org)

        own    = SupplierFactory(organization=org)
        other  = SupplierFactory(organization=other_org)

        resp = client.get(reverse("suppliers:supplier_list"))
        assert resp.status_code == 200
        # The response context should contain only the org's supplier
        page_obj = resp.context["dt_page_obj"]
        pks = [s.pk for s in page_obj.object_list]
        assert own.pk in pks
        assert other.pk not in pks


# ── Create ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierCreate:

    def test_create_supplier_via_post(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)

        resp = client.post(reverse("suppliers:supplier_list"), {
            "name":   "Distribuidora Nacional S.R.L.",
            "rnc":    "101000001",
            "phone":  "809-555-1234",
            "email":  "info@distri.com.do",
            "status": Supplier.Status.ACTIVE,
        })
        assert resp.status_code == 302
        assert Supplier.objects.filter(
            organization=org, name="Distribuidora Nacional S.R.L."
        ).exists()

    def test_create_requires_name(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)

        resp = client.post(reverse("suppliers:supplier_list"), {
            "name":   "",
            "status": Supplier.Status.ACTIVE,
        })
        # Should re-render the form with errors, not redirect
        assert resp.status_code == 200
        assert not Supplier.objects.filter(organization=org).exists()

    def test_create_scopes_to_active_org(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)

        client.post(reverse("suppliers:supplier_list"), {
            "name":   "Solo para Org A",
            "status": Supplier.Status.ACTIVE,
        })
        supplier = Supplier.objects.get(name="Solo para Org A")
        assert supplier.organization == org


# ── Detail ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierDetailView:

    def test_detail_returns_200(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=org)

        resp = client.get(reverse("suppliers:supplier_detail", args=[supplier.pk]))
        assert resp.status_code == 200

    def test_detail_cross_org_returns_404(self, client):
        user, org, _ = make_member()
        other_org    = OrganizationFactory()
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=other_org)

        resp = client.get(reverse("suppliers:supplier_detail", args=[supplier.pk]))
        assert resp.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierUpdateView:

    def test_update_supplier(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=org, name="Original S.R.L.")

        resp = client.post(
            reverse("suppliers:supplier_edit", args=[supplier.pk]),
            {
                "name":   "Actualizado S.R.L.",
                "rnc":    supplier.rnc,
                "phone":  supplier.phone,
                "email":  supplier.email,
                "status": Supplier.Status.ACTIVE,
            },
        )
        assert resp.status_code == 302
        supplier.refresh_from_db()
        assert supplier.name == "Actualizado S.R.L."

    def test_update_cross_org_returns_404(self, client):
        user, org, _ = make_member()
        other_org    = OrganizationFactory()
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=other_org)

        resp = client.post(
            reverse("suppliers:supplier_edit", args=[supplier.pk]),
            {"name": "Hack", "status": Supplier.Status.ACTIVE},
        )
        assert resp.status_code == 404

    def test_update_inactive_status(self, client):
        user, org, _ = make_member()
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=org, status=Supplier.Status.ACTIVE)

        client.post(
            reverse("suppliers:supplier_edit", args=[supplier.pk]),
            {
                "name":   supplier.name,
                "rnc":    supplier.rnc,
                "phone":  supplier.phone,
                "email":  supplier.email,
                "status": Supplier.Status.INACTIVE,
            },
        )
        supplier.refresh_from_db()
        assert supplier.status == Supplier.Status.INACTIVE


# ── Delete ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierDeleteView:

    def test_delete_requires_admin(self, client):
        user, org, _ = make_member(Membership.Role.MEMBER)
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=org)

        resp = client.post(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        # Non-admin should be forbidden (403) or redirected
        assert resp.status_code in (302, 403)
        # Supplier should still exist (soft-deleted or not touched)
        assert Supplier.objects.filter(pk=supplier.pk).exists()

    def test_delete_soft_deletes_supplier(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=org)

        resp = client.post(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        assert resp.status_code == 302
        # Soft-deleted: not visible via default manager
        assert not Supplier.objects.filter(pk=supplier.pk).exists()
        # But still in DB via all_objects
        assert Supplier.all_objects.filter(pk=supplier.pk).exists()

    def test_delete_cross_org_returns_404(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        other_org    = OrganizationFactory()
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=other_org)

        resp = client.post(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        assert resp.status_code == 404

    def test_delete_only_accepts_post(self, client):
        user, org, _ = make_member(Membership.Role.ADMIN)
        login(client, user)
        set_active_org(client, org)
        supplier = SupplierFactory(organization=org)

        resp = client.get(reverse("suppliers:supplier_delete", args=[supplier.pk]))
        assert resp.status_code == 405
