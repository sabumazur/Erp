from importlib import import_module
from io import StringIO

import pytest
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.accounts.tests.factories import TeamFactory, UserFactory
from apps.core.models import Module


def module_data(slug, name="Module", is_active=True):
    return {
        "slug": slug,
        "name": name,
        "icon": "bi-grid",
        "description": "",
        "is_active": "on" if is_active else "",
    }


@pytest.mark.django_db
class TestModuleMutations:
    def staff_client(self, client):
        staff = UserFactory(is_staff=True)
        client.force_login(staff)
        return client

    def test_sales_slug_cannot_be_renamed(self, client):
        module = Module.objects.create(slug="sales", name="Sales")
        client = self.staff_client(client)

        response = client.post(
            reverse("core:module_edit", args=[module.pk]),
            module_data("billing", "Sales"),
        )

        module.refresh_from_db()
        assert response.status_code == 200
        assert module.slug == "sales"
        assert b"canonical sales module slug" in response.content

    def test_sales_module_cannot_be_deleted_and_htmx_returns_error(self, client):
        module = Module.objects.create(slug="sales", name="Sales")
        client = self.staff_client(client)

        response = client.post(
            reverse("core:module_delete", args=[module.pk]),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert Module.objects.filter(pk=module.pk).exists()
        assert "canonical sales module cannot be deleted" in response["HX-Trigger"]

    def test_assigned_module_cannot_be_renamed_or_deleted(self):
        module = Module.objects.create(slug="inventory", name="Inventory")
        team = TeamFactory()
        team.modules.add(module)

        module.slug = "warehouse"
        with pytest.raises(ValidationError):
            module.save()
        with pytest.raises(ValidationError):
            module.delete()

    def test_sales_metadata_and_active_status_can_be_changed(self):
        module = Module.objects.create(slug="sales", name="Sales")
        module.name = "Sales Documents"
        module.is_active = False
        module.save()

        module.refresh_from_db()
        assert module.name == "Sales Documents"
        assert module.is_active is False

    def test_unassigned_custom_module_can_be_renamed_and_deleted(self):
        module = Module.objects.create(slug="reports", name="Reports")
        module.slug = "analytics"
        module.save()
        assert module.slug == "analytics"

        module.delete()
        assert not Module.objects.filter(pk=module.pk).exists()


@pytest.mark.django_db
class TestModuleAudit:
    def test_audit_reports_findings_without_modifying_assignments(self):
        Module.objects.create(slug="sales", name="Sales")
        unrestricted = TeamFactory()
        inactive = Module.objects.create(slug="reports", name="Reports", is_active=False)
        assigned = TeamFactory()
        assigned.modules.add(inactive)
        output = StringIO()

        call_command("audit_module_access", stdout=output)

        text = output.getvalue()
        assert "[UNRESTRICTED]" in text
        assert unrestricted.name in text
        assert "[INACTIVE]" in text
        assert assigned.modules.filter(pk=inactive.pk).exists()

    def test_audit_strict_fails_when_canonical_sales_is_missing(self):
        with pytest.raises(CommandError):
            call_command("audit_module_access", "--strict", stdout=StringIO())


@pytest.mark.django_db
def test_rename_migration_merges_existing_sales_assignments():
    invoices = Module.objects.create(slug="invoices", name="Invoices")
    sales = Module.objects.create(slug="sales", name="Existing Sales")
    invoice_team = TeamFactory()
    sales_team = TeamFactory()
    invoice_team.modules.add(invoices)
    sales_team.modules.add(sales)

    migration = import_module("apps.core.migrations.0005_rename_invoices_module_slug")
    migration.rename_slug(django_apps, None)

    sales.refresh_from_db()
    assert not Module.objects.filter(slug="invoices").exists()
    assert set(sales.teams.values_list("pk", flat=True)) == {
        invoice_team.pk,
        sales_team.pk,
    }
    assert sales.name == "Ventas"
