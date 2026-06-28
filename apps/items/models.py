from decimal import Decimal

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel
from apps.core.search import fts_search


# ── Item code sequence ────────────────────────────────────────────────────────


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


# ── Item ──────────────────────────────────────────────────────────────────────


class Item(ERPBaseModel):
    """
    Product / service catalog entry per organization.

    ItemType discriminates future use:
      - SALE     → available in invoice / quotation / sale-order line items
      - PURCHASE → available in purchase orders (future)
      - BOTH     → available everywhere (default)

    Codes are auto-generated for SALE, PURCHASE, and BOTH items when left blank.

    The `item` FK on SalesDocumentItem is optional; name, unit_price, and
    itbis_rate are always editable — the FK is a catalog snapshot reference.
    """

    class ItemType(models.TextChoices):
        SALE = "SALE", _("Venta")
        PURCHASE = "PURCHASE", _("Compra")
        BOTH = "BOTH", _("Venta y Compra")

    # Types that trigger auto-code generation
    AUTO_CODE_TYPES = {ItemType.SALE, ItemType.PURCHASE, ItemType.BOTH}

    class Unit(models.TextChoices):
        UNIT = "UNIT", _("Unidad")
        LIB = "LB", _("Libra")
        HOUR = "HOUR", _("Hora")
        KG = "KG", _("Kilogramo")
        BOX = "BOX", _("Caja")
        SERVICE = "SERVICE", _("Servicio")
        METER = "METER", _("Metro")
        LITER = "LITER", _("Litro")
        OTHER = "OTHER", _("Otro")

    class ITBISRate(models.TextChoices):
        EXEMPT = "EXEMPT", _("0%")
        RATE_16 = "RATE_16", _("16%")
        RATE_18 = "RATE_18", _("18%")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("organización"),
    )
    code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("código"),
        help_text=_(
            "Código interno / SKU. Déjelo en blanco para generar automáticamente."
        ),
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_("nombre"),
    )
    item_type = models.CharField(
        max_length=10,
        choices=ItemType.choices,
        default=ItemType.BOTH,
        verbose_name=_("tipo"),
        db_index=True,
    )
    unit = models.CharField(
        max_length=10,
        choices=Unit.choices,
        default=Unit.UNIT,
        verbose_name=_("unidad de medida"),
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("precio de venta"),
    )
    cost_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("precio de costo"),
    )
    itbis_rate = models.CharField(
        max_length=8,
        choices=ITBISRate.choices,
        default=ITBISRate.RATE_18,
        verbose_name=_("tasa ITBIS"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("activo"),
    )
    default_supplier = models.ForeignKey(
        "purchases.Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_items",
        verbose_name=_("proveedor habitual"),
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("notas internas"),
    )

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("artículo")
        verbose_name_plural = _("artículos")
        ordering = ["name"]
        indexes = [
            GinIndex(SearchVector("name", config="spanish"), name="item_name_fts_idx"),
            GinIndex(fields=["name"], opclasses=["gin_trgm_ops"], name="item_name_trgm_idx"),
            GinIndex(fields=["code"], opclasses=["gin_trgm_ops"], name="item_code_trgm_idx"),
            models.Index(fields=["organization", "is_active"], name="item_org_active_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(code=""),
                name="unique_active_item_code_per_org",
            ),
        ]

    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        should_generate = (
            self._state.adding
            and not self.code
            and self.item_type in self.AUTO_CODE_TYPES
        )
        if not should_generate:
            return super().save(*args, **kwargs)

        # A manual code may be inserted after sequence allocation but before
        # INSERT. Reserve a new code and retry that narrow uniqueness race.
        for attempt in range(5):
            try:
                with transaction.atomic():
                    self.code = ItemCodeSequence.generate(self.organization, self.item_type)
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.code = ""
                if attempt == 4:
                    raise

    def delete(self, *args, **kwargs):
        from apps.sales.models import SalesDocumentItem
        from apps.purchases.models import PurchaseDocumentItem
        if SalesDocumentItem.objects.filter(item=self).exists():
            raise ValueError(
                f"No se puede eliminar «{self.name}» porque está en uso en uno o más documentos de venta."
            )
        if PurchaseDocumentItem.objects.filter(item=self).exists():
            raise ValueError(
                f"No se puede eliminar «{self.name}» porque está en uso en uno o más documentos de compra."
            )
        return super().delete(*args, **kwargs)

    @property
    def display_price(self):
        """Price formatted for display."""
        return f"{self.unit_price:,.2f}"

    @property
    def margin(self):
        """Gross margin percentage if cost_price is set."""
        if self.cost_price and self.unit_price and self.unit_price > 0:
            return (
                (self.unit_price - self.cost_price) / self.unit_price * 100
            ).quantize(Decimal("0.01"))
        return None


def item_catalog_search(organization, q, *, sale_only=True, limit=10):
    """
    Org-scoped, FTS+trigram item search used by all picker and autocomplete views.

    Args:
        organization: the active tenant
        q:            raw search string (empty → return top items by name)
        sale_only:    True  → SALE + BOTH only (invoice/quotation/sale-order pickers)
                      False → all item_types (purchase order pickers, future)
        limit:        max rows returned
    """
    qs = Item.objects.for_org(organization).filter(is_active=True)
    if sale_only:
        qs = qs.filter(item_type__in=[Item.ItemType.SALE, Item.ItemType.BOTH])
    if q:
        qs = fts_search(qs, q, fts_fields=["name"], trgm_fields=["code"])
    else:
        qs = qs.order_by("name")
    return qs[:limit]
