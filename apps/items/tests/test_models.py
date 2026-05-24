import uuid
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.core.exceptions import ValidationError

from apps.accounts.tests.factories import OrganizationFactory
from apps.items.models import Item, ItemCodeSequence
from apps.items.tests.factories import ItemFactory


@pytest.mark.django_db
class TestItemModel:

    # ── __str__ ───────────────────────────────────────────────────────────

    def test_str_with_code(self):
        item = ItemFactory(code="ART-001")
        assert str(item) == f"[ART-001] {item.name}"

    def test_str_without_code(self):
        item = ItemFactory(code="", item_type=Item.ItemType.PURCHASE)
        assert str(item) == item.name

    # ── ERPBaseModel fields ───────────────────────────────────────────────

    def test_uuid_pk(self):
        item = ItemFactory()
        assert isinstance(item.pk, uuid.UUID)

    def test_timestamps_set_on_save(self):
        item = ItemFactory()
        assert item.created_at is not None
        assert item.updated_at is not None

    # ── Soft delete ───────────────────────────────────────────────────────

    def test_soft_delete_sets_deleted_at(self):
        item = ItemFactory()
        item.delete()
        item.refresh_from_db()
        assert item.deleted_at is not None

    def test_soft_deleted_excluded_from_objects(self):
        item = ItemFactory()
        pk = item.pk
        item.delete()
        assert not Item.objects.filter(pk=pk).exists()

    def test_soft_deleted_visible_in_all_objects(self):
        item = ItemFactory()
        pk = item.pk
        item.delete()
        assert Item.all_objects.filter(pk=pk).exists()

    def test_soft_deleted_code_does_not_block_reuse(self):
        org = OrganizationFactory()
        item = ItemFactory(code="DUPE-001", item_type=Item.ItemType.PURCHASE, organization=org)
        item.delete()
        # UniqueConstraint has condition deleted_at__isnull=True — soft-deleted code is free
        duplicate = ItemFactory(code="DUPE-001", item_type=Item.ItemType.PURCHASE, organization=org)
        assert duplicate.pk != item.pk

    # ── Properties ────────────────────────────────────────────────────────

    def test_display_price_formatted(self):
        item = ItemFactory(unit_price=Decimal("1234.50"))
        assert item.display_price == "1,234.50"

    def test_margin_computed_correctly(self):
        item = ItemFactory(unit_price=Decimal("100.00"), cost_price=Decimal("60.00"))
        assert item.margin == Decimal("40.00")

    def test_margin_none_when_cost_price_not_set(self):
        item = ItemFactory(cost_price=None)
        assert item.margin is None

    def test_margin_none_when_unit_price_is_zero(self):
        item = ItemFactory(unit_price=Decimal("0.00"), cost_price=Decimal("10.00"))
        assert item.margin is None

    # ── Auto-code generation ──────────────────────────────────────────────

    def test_auto_code_generated_for_sale_item(self):
        # Bypass factory's pre-set code to trigger auto-generation
        org = OrganizationFactory()
        item = Item.objects.create(
            organization=org,
            name="Auto Code Test",
            item_type=Item.ItemType.SALE,
            unit=Item.Unit.UNIT,
            unit_price=Decimal("50.00"),
            itbis_rate=Item.ITBISRate.RATE_18,
        )
        assert item.code != ""
        assert "-" in item.code

    def test_auto_code_generated_for_both_item(self):
        org = OrganizationFactory()
        item = Item.objects.create(
            organization=org,
            name="Both Type Test",
            item_type=Item.ItemType.BOTH,
            unit=Item.Unit.UNIT,
            unit_price=Decimal("50.00"),
            itbis_rate=Item.ITBISRate.RATE_18,
        )
        assert item.code != ""

    def test_purchase_item_no_auto_code(self):
        item = ItemFactory(code="", item_type=Item.ItemType.PURCHASE)
        item.refresh_from_db()
        assert item.code == ""

    def test_existing_code_not_overwritten_on_resave(self):
        item = ItemFactory(code="MANUAL-01")
        item.name = "Updated Name"
        item.save()
        item.refresh_from_db()
        assert item.code == "MANUAL-01"

    def test_auto_code_skips_manual_code_in_sequence(self):
        org = OrganizationFactory()
        ItemFactory(organization=org, code="ART-0001")
        item = Item.objects.create(
            organization=org,
            name="Generated",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("10.00"),
        )
        assert item.code == "ART-0002"

    def test_auto_code_retries_generated_code_conflict(self):
        org = OrganizationFactory()
        ItemFactory(organization=org, code="ART-0001")
        with patch.object(
            ItemCodeSequence,
            "generate",
            side_effect=["ART-0001", "ART-0002"],
        ):
            item = Item.objects.create(
                organization=org,
                name="Retried",
                item_type=Item.ItemType.SALE,
                unit_price=Decimal("10.00"),
            )
        assert item.code == "ART-0002"

    @pytest.mark.parametrize("field", ["unit_price", "cost_price"])
    def test_negative_price_fails_model_validation(self, field):
        item = ItemFactory(**{field: Decimal("-0.01")})
        with pytest.raises(ValidationError):
            item.full_clean()

    # ── Delete guard ──────────────────────────────────────────────────────

    def test_delete_raises_when_item_in_invoice_item(self):
        item = ItemFactory()
        with patch(
            "apps.sales.models.SalesDocumentItem.objects.filter",
            return_value=MagicMock(**{"exists.return_value": True}),
        ):
            with pytest.raises(ValueError, match="está en uso"):
                item.delete()


@pytest.mark.django_db
class TestItemCodeSequence:

    def test_generate_creates_sequence_on_first_call(self):
        org = OrganizationFactory()
        code = ItemCodeSequence.generate(org)
        assert ItemCodeSequence.objects.filter(organization=org).exists()
        assert code.startswith("ART-")

    def test_generate_returns_formatted_code(self):
        org = OrganizationFactory()
        code = ItemCodeSequence.generate(org)
        assert "-" in code
        prefix, seq = code.split("-", 1)
        assert seq.isdigit()

    def test_generate_increments_sequence(self):
        org = OrganizationFactory()
        code1 = ItemCodeSequence.generate(org)
        code2 = ItemCodeSequence.generate(org)
        assert code1 != code2
        seq = ItemCodeSequence.objects.get(organization=org)
        assert seq.current_seq == 2

    def test_generate_isolated_per_org(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        ItemCodeSequence.generate(org1)
        ItemCodeSequence.generate(org1)
        code2 = ItemCodeSequence.generate(org2)
        _, seq_str = code2.split("-", 1)
        assert int(seq_str) == 1

    def test_str(self):
        org = OrganizationFactory()
        ItemCodeSequence.generate(org)
        seq = ItemCodeSequence.objects.get(organization=org)
        assert str(seq) != ""
