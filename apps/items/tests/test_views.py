import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse

from apps.items.models import Item
from apps.items.tests.factories import ItemFactory

VALID_DATA = {
    "name": "Nuevo Artículo",
    "item_type": "SALE",
    "unit": "UNIT",
    "unit_price": "150.00",
    "itbis_rate": "RATE_18",
    "is_active": True,
    "code": "",
    "cost_price": "",
    "notes": "",
    "change_reason": "",
}


@pytest.mark.django_db
class TestItemListView:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    # ── List (GET) ────────────────────────────────────────────────────────

    def test_list_requires_login(self, client):
        response = client.get(reverse("items:item_list"))
        assert response.status_code == 302

    def test_list_accessible_to_member(self, client, member_membership):
        self._login(client, member_membership)
        response = client.get(reverse("items:item_list"))
        assert response.status_code == 200

    def test_list_org_scoped(self, client, member_membership):
        own = ItemFactory(organization=member_membership.organization)
        other = ItemFactory()  # different org
        self._login(client, member_membership)
        response = client.get(reverse("items:item_list"))
        content = response.content.decode()
        assert own.name in content
        assert other.name not in content

    def test_list_htmx_returns_partial(self, client, member_membership):
        self._login(client, member_membership)
        response = client.get(
            reverse("items:item_list"),
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        # Partial must not contain full page chrome
        assert b"<!DOCTYPE" not in response.content

    # ── Create (POST) ─────────────────────────────────────────────────────

    def test_create_requires_admin(self, client, member_membership):
        self._login(client, member_membership)
        response = client.post(reverse("items:item_list"), data=VALID_DATA)
        assert response.status_code == 403

    def test_create_valid_data_creates_item(self, client, admin_membership):
        self._login(client, admin_membership)
        count_before = Item.objects.for_org(admin_membership.organization).count()
        response = client.post(reverse("items:item_list"), data=VALID_DATA)
        assert response.status_code == 302
        assert Item.objects.for_org(admin_membership.organization).count() == count_before + 1

    def test_create_invalid_data_returns_form(self, client, admin_membership):
        self._login(client, admin_membership)
        response = client.post(reverse("items:item_list"), data={"name": ""})
        assert response.status_code == 200
        assert b"form" in response.content.lower()


@pytest.mark.django_db
class TestItemDetailView:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    def test_detail_own_org(self, client, member_membership):
        item = ItemFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.get(reverse("items:item_detail", args=[item.pk]))
        assert response.status_code == 200

    def test_detail_requires_login(self, client):
        item = ItemFactory()
        response = client.get(reverse("items:item_detail", args=[item.pk]))
        assert response.status_code == 302

    def test_detail_other_org_returns_404(self, client, member_membership):
        item = ItemFactory()  # different org
        self._login(client, member_membership)
        response = client.get(reverse("items:item_detail", args=[item.pk]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestItemUpdateView:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    # ── GET ───────────────────────────────────────────────────────────────

    def test_edit_requires_admin(self, client, member_membership):
        item = ItemFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.get(reverse("items:item_edit", args=[item.pk]))
        assert response.status_code == 403

    def test_edit_get_returns_form(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.get(reverse("items:item_edit", args=[item.pk]))
        assert response.status_code == 200

    def test_edit_get_other_org_returns_404(self, client, admin_membership):
        item = ItemFactory()  # different org
        self._login(client, admin_membership)
        response = client.get(reverse("items:item_edit", args=[item.pk]))
        assert response.status_code == 404

    # ── POST ──────────────────────────────────────────────────────────────

    def test_edit_post_valid_updates_item(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        data = {**VALID_DATA, "name": "Nombre Actualizado", "code": item.code}
        response = client.post(reverse("items:item_edit", args=[item.pk]), data=data)
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.name == "Nombre Actualizado"

    def test_edit_post_invalid_returns_form(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.post(reverse("items:item_edit", args=[item.pk]), data={"name": ""})
        assert response.status_code == 200

    def test_edit_post_other_org_returns_404(self, client, admin_membership):
        item = ItemFactory()  # different org
        self._login(client, admin_membership)
        response = client.post(reverse("items:item_edit", args=[item.pk]), data=VALID_DATA)
        assert response.status_code == 404


@pytest.mark.django_db
class TestItemToggleView:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    def test_toggle_requires_admin(self, client, member_membership):
        item = ItemFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.post(reverse("items:item_toggle", args=[item.pk]))
        assert response.status_code == 403

    def test_toggle_deactivates_active_item(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization, is_active=True)
        self._login(client, admin_membership)
        client.post(reverse("items:item_toggle", args=[item.pk]))
        item.refresh_from_db()
        assert item.is_active is False

    def test_toggle_activates_inactive_item(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization, is_active=False)
        self._login(client, admin_membership)
        client.post(reverse("items:item_toggle", args=[item.pk]))
        item.refresh_from_db()
        assert item.is_active is True

    def test_toggle_get_not_allowed(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.get(reverse("items:item_toggle", args=[item.pk]))
        assert response.status_code == 405

    def test_toggle_other_org_returns_404(self, client, admin_membership):
        item = ItemFactory()  # different org
        self._login(client, admin_membership)
        response = client.post(reverse("items:item_toggle", args=[item.pk]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestItemDeleteView:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    def test_delete_requires_admin(self, client, member_membership):
        item = ItemFactory(organization=member_membership.organization)
        self._login(client, member_membership)
        response = client.post(reverse("items:item_delete", args=[item.pk]))
        assert response.status_code == 403

    def test_delete_soft_deletes(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        client.post(reverse("items:item_delete", args=[item.pk]))
        item.refresh_from_db()
        assert item.deleted_at is not None

    def test_delete_get_not_allowed(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        response = client.get(reverse("items:item_delete", args=[item.pk]))
        assert response.status_code == 405

    def test_delete_other_org_returns_404(self, client, admin_membership):
        item = ItemFactory()  # different org
        self._login(client, admin_membership)
        response = client.post(reverse("items:item_delete", args=[item.pk]))
        assert response.status_code == 404

    def test_delete_blocked_when_in_use_redirects(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        with patch(
            "apps.invoices.models.InvoiceItem.objects.filter",
            return_value=MagicMock(**{"exists.return_value": True}),
        ):
            response = client.post(reverse("items:item_delete", args=[item.pk]))
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.deleted_at is None  # not deleted

    def test_delete_blocked_htmx_returns_swal_trigger(self, client, admin_membership):
        item = ItemFactory(organization=admin_membership.organization)
        self._login(client, admin_membership)
        with patch(
            "apps.invoices.models.InvoiceItem.objects.filter",
            return_value=MagicMock(**{"exists.return_value": True}),
        ):
            response = client.post(
                reverse("items:item_delete", args=[item.pk]),
                HTTP_HX_REQUEST="true",
            )
        assert "showSwal" in response.get("HX-Trigger", "")


@pytest.mark.django_db
class TestItemSearchView:

    def _login(self, client, membership):
        client.force_login(membership.user)
        session = client.session
        session["active_org_slug"] = membership.organization.slug
        session.save()

    def test_search_requires_login(self, client):
        response = client.get(reverse("items:item_search"), {"q": "art"})
        assert response.status_code == 302

    def test_search_returns_empty_for_short_query(self, client, member_membership):
        self._login(client, member_membership)
        response = client.get(reverse("items:item_search"), {"q": "a"})
        assert response.status_code == 200
        assert response.content == b""

    def test_search_returns_matching_items(self, client, member_membership):
        item = ItemFactory(
            organization=member_membership.organization,
            name="Café Premium",
            item_type=Item.ItemType.SALE,
            is_active=True,
        )
        self._login(client, member_membership)
        response = client.get(reverse("items:item_search"), {"q": "café"})
        assert response.status_code == 200
        assert item.name.encode() in response.content

    def test_search_org_scoped(self, client, member_membership):
        own = ItemFactory(
            organization=member_membership.organization,
            name="Propio Artículo",
            item_type=Item.ItemType.SALE,
            is_active=True,
        )
        other = ItemFactory(name="Propio Artículo", item_type=Item.ItemType.SALE, is_active=True)
        self._login(client, member_membership)
        response = client.get(reverse("items:item_search"), {"q": "Propio"})
        content = response.content.decode()
        assert str(own.pk) in content
        assert str(other.pk) not in content

    def test_search_excludes_inactive_items(self, client, member_membership):
        item = ItemFactory(
            organization=member_membership.organization,
            name="Artículo Inactivo",
            item_type=Item.ItemType.SALE,
            is_active=False,
        )
        self._login(client, member_membership)
        response = client.get(reverse("items:item_search"), {"q": "Inactivo"})
        assert item.name.encode() not in response.content

    def test_search_type_filter_sale_excludes_purchase_only(self, client, member_membership):
        purchase_item = ItemFactory(
            organization=member_membership.organization,
            name="Solo Compra",
            item_type=Item.ItemType.PURCHASE,
            is_active=True,
        )
        self._login(client, member_membership)
        response = client.get(reverse("items:item_search"), {"q": "Solo", "type": "SALE"})
        assert purchase_item.name.encode() not in response.content
