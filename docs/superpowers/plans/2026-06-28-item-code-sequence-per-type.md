# Item Code Sequence Per Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each `ItemType` (SALE, PURCHASE, BOTH) its own independent auto-code counter per organization, producing type-specific prefixes like `VTA-0001`, `COM-0001`, `ART-0001`.

**Architecture:** Replace the `OneToOneField(organization)` on `ItemCodeSequence` with a `ForeignKey` + `UniqueConstraint(organization, item_type)`, giving up to 3 rows per org. `generate()` accepts `item_type` and picks the default prefix from a type→prefix map. `Item.save()` passes `self.item_type` to `generate()`.

**Tech Stack:** Django ORM, PostgreSQL, pytest-django

---

## File Map

| File | Change |
|------|--------|
| `apps/items/models.py` | Restructure `ItemCodeSequence`; update `Item.save()` |
| `apps/items/migrations/0013_itemcodesequence_per_type.py` | Schema migration |
| `apps/items/admin.py` | Add `item_type` to admin display/fields |
| `apps/items/tests/test_models.py` | Update broken tests; add new type-specific tests |

---

## Task 1: Update `ItemCodeSequence` model and `Item.save()`

**Files:**
- Modify: `apps/items/models.py`

- [ ] **Step 1: Replace `OneToOneField` with `ForeignKey` + add `item_type` field**

In `apps/items/models.py`, replace the entire `ItemCodeSequence` class with:

```python
class ItemCodeSequence(models.Model):
    """
    Atomic auto-increment counter for item codes.
    One row per (organization, item_type).

    Generates codes like "VTA-0001" (SALE), "COM-0001" (PURCHASE), "ART-0001" (BOTH).
    Prefix is editable per row.
    """

    TYPE_PREFIXES = {
        "SALE": "VTA",
        "PURCHASE": "COM",
        "BOTH": "ART",
    }

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="item_code_sequences",
        verbose_name=_("organización"),
    )
    item_type = models.CharField(
        max_length=10,
        verbose_name=_("tipo de artículo"),
    )
    prefix = models.CharField(
        max_length=5,
        verbose_name=_("prefijo"),
        help_text=_("Prefijo del código generado automáticamente (ej. VTA, COM, ART)."),
    )
    current_seq = models.PositiveIntegerField(
        default=0,
        verbose_name=_("secuencia actual"),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("secuencia de códigos de artículo")
        verbose_name_plural = _("secuencias de códigos de artículo")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "item_type"],
                name="unique_item_code_sequence_per_org_type",
            )
        ]

    def __str__(self):
        return f"{self.organization} · {self.item_type} · {self.prefix}-{self.current_seq:04d}"

    @classmethod
    def generate(cls, organization, item_type: str) -> str:
        """
        Atomically reserve and return the next item code for (organization, item_type).

        Uses SELECT FOR UPDATE to prevent duplicates under concurrent saves.
        Format: PREFIX-NNNN  (e.g. VTA-0001)
        Pads to 4 digits; expands naturally beyond 9999 (VTA-10000, etc.).

        Skips any sequence values whose code already exists as a manual entry
        (including soft-deleted rows) to avoid collisions with hand-entered codes.
        """
        default_prefix = cls.TYPE_PREFIXES.get(item_type, "ART")
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                organization=organization,
                item_type=item_type,
                defaults={"prefix": default_prefix, "current_seq": 0},
            )
            while True:
                seq.current_seq += 1
                candidate = f"{seq.prefix}-{seq.current_seq:04d}"
                if not Item.all_objects.filter(
                    organization=organization, code=candidate
                ).exists():
                    break
            seq.save(update_fields=["current_seq", "updated_at"])

        return candidate
```

- [ ] **Step 2: Update `Item.save()` to pass `item_type` to `generate()`**

In `apps/items/models.py`, update `Item.save()`:

```python
def save(self, *args, **kwargs):
    should_generate = (
        self._state.adding
        and not self.code
        and self.item_type in self.AUTO_CODE_TYPES
    )
    if not should_generate:
        return super().save(*args, **kwargs)

    for attempt in range(5):
        try:
            with transaction.atomic():
                self.code = ItemCodeSequence.generate(self.organization, self.item_type)
                return super().save(*args, **kwargs)
        except IntegrityError:
            self.code = ""
            if attempt == 4:
                raise
```

---

## Task 2: Write and run the migration

**Files:**
- Create: `apps/items/migrations/0013_itemcodesequence_per_type.py`

- [ ] **Step 1: Write the migration**

Create `apps/items/migrations/0013_itemcodesequence_per_type.py`:

```python
"""
0013_itemcodesequence_per_type

Replaces the OneToOneField(organization) on ItemCodeSequence with
ForeignKey(organization) + item_type field, allowing one counter row
per (organization, item_type).

Existing rows are migrated to item_type='BOTH' (they used prefix "ART").
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0012_item_item_org_active_idx"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        # 1. Add item_type with a temporary default so existing rows are valid
        migrations.AddField(
            model_name="itemcodesequence",
            name="item_type",
            field=models.CharField(
                max_length=10,
                verbose_name="tipo de artículo",
                default="BOTH",
            ),
            preserve_default=False,
        ),
        # 2. Drop the old OneToOneField and replace with ForeignKey
        migrations.AlterField(
            model_name="itemcodesequence",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="item_code_sequences",
                to="accounts.organization",
                verbose_name="organización",
            ),
        ),
        # 3. Update prefix help_text
        migrations.AlterField(
            model_name="itemcodesequence",
            name="prefix",
            field=models.CharField(
                max_length=5,
                verbose_name="prefijo",
                help_text="Prefijo del código generado automáticamente (ej. VTA, COM, ART).",
            ),
        ),
        # 4. Add unique constraint on (organization, item_type)
        migrations.AddConstraint(
            model_name="itemcodesequence",
            constraint=models.UniqueConstraint(
                fields=["organization", "item_type"],
                name="unique_item_code_sequence_per_org_type",
            ),
        ),
    ]
```

- [ ] **Step 2: Run migration**

```bash
python manage.py migrate items
```

Expected output ends with:
```
Applying items.0013_itemcodesequence_per_type... OK
```

- [ ] **Step 3: Commit**

```bash
git add apps/items/models.py apps/items/migrations/0013_itemcodesequence_per_type.py
git commit -m "feat: ItemCodeSequence — one counter per (org, item_type)

SALE→VTA, PURCHASE→COM, BOTH→ART prefixes. Replaces OneToOneField
with ForeignKey + UniqueConstraint. generate() now takes item_type."
```

---

## Task 3: Update admin

**Files:**
- Modify: `apps/items/admin.py`

- [ ] **Step 1: Add `item_type` to `ItemCodeSequenceAdmin`**

Replace the `ItemCodeSequenceAdmin` class in `apps/items/admin.py`:

```python
@admin.register(ItemCodeSequence)
class ItemCodeSequenceAdmin(admin.ModelAdmin):
    list_display  = ["organization", "item_type", "prefix", "current_seq", "next_code", "updated_at"]
    list_filter   = ["item_type"]
    readonly_fields = ["current_seq", "updated_at", "next_code"]
    fields        = ["organization", "item_type", "prefix", "current_seq", "next_code", "updated_at"]

    def next_code(self, obj):
        return f"{obj.prefix}-{obj.current_seq + 1:04d}"
    next_code.short_description = _("próximo código")
```

- [ ] **Step 2: Commit**

```bash
git add apps/items/admin.py
git commit -m "chore: update ItemCodeSequenceAdmin for per-type rows"
```

---

## Task 4: Update and expand tests

**Files:**
- Modify: `apps/items/tests/test_models.py`

### What breaks

Three existing tests must be updated:

1. `test_purchase_item_no_auto_code` — PURCHASE now gets auto-code; invert assertion.
2. `test_auto_code_skips_manual_code_in_sequence` — `generate(org)` → `generate(org, "SALE")`.
3. `test_auto_code_retries_generated_code_conflict` — same signature fix.

And `TestItemCodeSequence` tests that call `generate(org)` → `generate(org, "SALE")`.

- [ ] **Step 1: Fix `test_purchase_item_no_auto_code`**

```python
def test_purchase_item_gets_auto_code(self):
    org = OrganizationFactory()
    item = Item.objects.create(
        organization=org,
        name="Purchase Auto Code Test",
        item_type=Item.ItemType.PURCHASE,
        unit=Item.Unit.UNIT,
        unit_price=Decimal("0.00"),
        itbis_rate=Item.ITBISRate.RATE_18,
    )
    assert item.code != ""
    assert item.code.startswith("COM-")
```

- [ ] **Step 2: Fix `test_auto_code_skips_manual_code_in_sequence`**

```python
def test_auto_code_skips_manual_code_in_sequence(self):
    org = OrganizationFactory()
    manual = ItemCodeSequence.generate(org, "SALE")
    ItemFactory(organization=org, code=manual)
    item = Item.objects.create(
        organization=org,
        name="Generated",
        item_type=Item.ItemType.SALE,
        unit_price=Decimal("10.00"),
    )
    prefix, seq = manual.split("-", 1)
    expected = f"{prefix}-{int(seq)+1:04d}"
    assert item.code == expected
```

- [ ] **Step 3: Fix `test_auto_code_retries_generated_code_conflict`**

```python
def test_auto_code_retries_generated_code_conflict(self):
    org = OrganizationFactory()
    manual = ItemCodeSequence.generate(org, "SALE")
    ItemFactory(organization=org, code=manual)
    with patch.object(
        ItemCodeSequence,
        "generate",
        side_effect=[manual, f"{manual.split('-')[0]}-{int(manual.split('-')[1])+1:04d}"],
    ):
        item = Item.objects.create(
            organization=org,
            name="Retried",
            item_type=Item.ItemType.SALE,
            unit_price=Decimal("10.00"),
        )
    prefix, seq = manual.split("-", 1)
    expected = f"{prefix}-{int(seq)+1:04d}"
    assert item.code == expected
```

- [ ] **Step 4: Add type-specific prefix tests to `TestItemModel`**

```python
def test_auto_code_sale_uses_vta_prefix(self):
    org = OrganizationFactory()
    item = Item.objects.create(
        organization=org,
        name="Sale Item",
        item_type=Item.ItemType.SALE,
        unit=Item.Unit.UNIT,
        unit_price=Decimal("50.00"),
        itbis_rate=Item.ITBISRate.RATE_18,
    )
    assert item.code.startswith("VTA-")

def test_auto_code_purchase_uses_com_prefix(self):
    org = OrganizationFactory()
    item = Item.objects.create(
        organization=org,
        name="Purchase Item",
        item_type=Item.ItemType.PURCHASE,
        unit=Item.Unit.UNIT,
        unit_price=Decimal("0.00"),
        itbis_rate=Item.ITBISRate.RATE_18,
    )
    assert item.code.startswith("COM-")

def test_auto_code_both_uses_art_prefix(self):
    org = OrganizationFactory()
    item = Item.objects.create(
        organization=org,
        name="Both Item",
        item_type=Item.ItemType.BOTH,
        unit=Item.Unit.UNIT,
        unit_price=Decimal("50.00"),
        itbis_rate=Item.ITBISRate.RATE_18,
    )
    assert item.code.startswith("ART-")

def test_auto_code_sequences_independent_per_type(self):
    """SALE and PURCHASE counters are independent — both start at 0001."""
    org = OrganizationFactory()
    sale_item = Item.objects.create(
        organization=org,
        name="Sale",
        item_type=Item.ItemType.SALE,
        unit_price=Decimal("10.00"),
    )
    purchase_item = Item.objects.create(
        organization=org,
        name="Purchase",
        item_type=Item.ItemType.PURCHASE,
        unit_price=Decimal("0.00"),
    )
    assert sale_item.code == "VTA-0001"
    assert purchase_item.code == "COM-0001"
```

- [ ] **Step 5: Fix `TestItemCodeSequence` — update `generate()` calls**

Replace all `ItemCodeSequence.generate(org)` with `ItemCodeSequence.generate(org, "SALE")` in `TestItemCodeSequence`. Update `test_generate_creates_sequence_on_first_call` to also check `item_type`:

```python
@pytest.mark.django_db
class TestItemCodeSequence:

    def test_generate_creates_sequence_on_first_call(self):
        org = OrganizationFactory()
        code = ItemCodeSequence.generate(org, "SALE")
        assert ItemCodeSequence.objects.filter(organization=org, item_type="SALE").exists()
        assert code.startswith("VTA-")

    def test_generate_returns_formatted_code(self):
        org = OrganizationFactory()
        code = ItemCodeSequence.generate(org, "SALE")
        assert "-" in code
        prefix, seq = code.split("-", 1)
        assert seq.isdigit()

    def test_generate_increments_sequence(self):
        org = OrganizationFactory()
        code1 = ItemCodeSequence.generate(org, "SALE")
        code2 = ItemCodeSequence.generate(org, "SALE")
        assert code1 != code2
        seq = ItemCodeSequence.objects.get(organization=org, item_type="SALE")
        assert seq.current_seq == 2

    def test_generate_isolated_per_org(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        ItemCodeSequence.generate(org1, "SALE")
        ItemCodeSequence.generate(org1, "SALE")
        code2 = ItemCodeSequence.generate(org2, "SALE")
        _, seq_str = code2.split("-", 1)
        assert int(seq_str) == 1

    def test_generate_isolated_per_type(self):
        """SALE and PURCHASE counters within same org are independent."""
        org = OrganizationFactory()
        ItemCodeSequence.generate(org, "SALE")
        ItemCodeSequence.generate(org, "SALE")
        code = ItemCodeSequence.generate(org, "PURCHASE")
        _, seq_str = code.split("-", 1)
        assert int(seq_str) == 1

    def test_generate_purchase_uses_com_prefix(self):
        org = OrganizationFactory()
        code = ItemCodeSequence.generate(org, "PURCHASE")
        assert code.startswith("COM-")

    def test_generate_both_uses_art_prefix(self):
        org = OrganizationFactory()
        code = ItemCodeSequence.generate(org, "BOTH")
        assert code.startswith("ART-")

    def test_str(self):
        org = OrganizationFactory()
        ItemCodeSequence.generate(org, "SALE")
        seq = ItemCodeSequence.objects.get(organization=org, item_type="SALE")
        assert str(seq) != ""
```

- [ ] **Step 6: Run all item tests**

```bash
pytest apps/items/tests/test_models.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Run full test suite**

```bash
pytest
```

Expected: no regressions.

- [ ] **Step 8: Commit**

```bash
git add apps/items/tests/test_models.py
git commit -m "test: update ItemCodeSequence tests for per-type counters"
```
