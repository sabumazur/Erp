from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.core.models import Module
from apps.items.models import Item
from apps.items.tests.factories import ItemFactory
from apps.sales.models import SalesDocument
from apps.sales.tests.factories import SalesDocumentFactory, SalesDocumentItemFactory


@pytest.mark.django_db
class TestSoftDeleteQuerySet:
    def test_queryset_delete_soft_deletes_erp_records(self):
        item = ItemFactory()

        Item.objects.filter(pk=item.pk).delete()

        assert not Item.objects.filter(pk=item.pk).exists()
        assert Item.all_objects.get(pk=item.pk).deleted_at is not None

    def test_queryset_delete_respects_item_reference_guard(self):
        item = ItemFactory()
        document = SalesDocumentFactory(organization=item.organization)
        SalesDocumentItemFactory(document=document, item=item)

        with pytest.raises(ValueError):
            Item.objects.filter(pk=item.pk).delete()

        assert Item.objects.filter(pk=item.pk).exists()

    def test_queryset_hard_delete_is_explicitly_available(self):
        item = ItemFactory()

        Item.objects.filter(pk=item.pk).hard_delete()

        assert not Item.all_objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_empty_sales_doc_physically_deletes_active_and_soft_deleted_documents():
    active = SalesDocumentFactory()
    deleted = SalesDocumentFactory()
    deleted.delete()
    assert SalesDocument.all_objects.filter(pk__in=[active.pk, deleted.pk]).count() == 2

    call_command("empty_sales_doc", "--no-input", stdout=StringIO())

    assert not SalesDocument.all_objects.filter(pk__in=[active.pk, deleted.pk]).exists()


@pytest.mark.django_db(transaction=True)
def test_reset_db_succeeds_without_obsolete_schema_patch_and_clears_modules():
    Module.objects.create(slug="inventory", name="Inventory")
    output = StringIO()

    call_command("reset_db", "--no-input", stdout=output)

    assert User.objects.filter(is_superuser=True).exists()
    assert not Module.objects.exists()
    assert "seed_modules" in output.getvalue()
