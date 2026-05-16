"""
apps/purchases/models.py

Purchase Order domain models.

Lifecycle:
    DRAFT → CONFIRMED → RECEIVED
                      → CANCELLED
    DRAFT → CANCELLED
"""
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel


# ── Supplier ──────────────────────────────────────────────────────────────────


class Supplier(ERPBaseModel):
    """A vendor/supplier scoped to an organization."""

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="suppliers",
        verbose_name=_("organización"),
    )
    name = models.CharField(max_length=255, verbose_name=_("nombre / razón social"))
    rnc = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("RNC"),
        help_text=_("Registro Nacional de Contribuyente (9 dígitos)."),
    )
    email = models.EmailField(blank=True, verbose_name=_("correo electrónico"))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("teléfono"))
    contact_name = models.CharField(
        max_length=150, blank=True, verbose_name=_("nombre de contacto")
    )
    address = models.CharField(max_length=255, blank=True, verbose_name=_("dirección"))
    notes = models.TextField(blank=True, verbose_name=_("notas"))
    is_active = models.BooleanField(default=True, verbose_name=_("activo"))

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("proveedor")
        verbose_name_plural = _("proveedores")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_supplier_name_per_org",
            )
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.purchase_orders.exists():
            raise ValueError(
                f"No se puede eliminar «{self.name}» porque tiene órdenes de compra asociadas."
            )
        return super().delete(*args, **kwargs)


# ── PurchaseOrder Sequence ────────────────────────────────────────────────────


class PurchaseOrderSequence(models.Model):
    """
    Auto-increment sequence for Purchase Orders.
    One row per organization. Produces: OC-YYYY-NNNN  (e.g. OC-2026-0001)
    """

    organization = models.OneToOneField(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_order_sequence",
        verbose_name=_("organización"),
    )
    current_seq = models.PositiveIntegerField(
        default=0, verbose_name=_("secuencia actual")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("secuencia de orden de compra")
        verbose_name_plural = _("secuencias de órdenes de compra")

    def __str__(self):
        return f"{self.organization} · OC · {self.current_seq:04d}"

    @classmethod
    def generate(cls, organization) -> str:
        """
        Atomically reserve and return the next purchase order number.
        Format: OC-YYYY-NNNN  (e.g. OC-2026-0001)
        Uses SELECT FOR UPDATE to prevent race conditions.
        """
        year = timezone.now().year
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                organization=organization,
            )
            seq.current_seq += 1
            seq.save(update_fields=["current_seq", "updated_at"])

        return f"OC-{year}-{seq.current_seq:04d}"


# ── PurchaseOrder ─────────────────────────────────────────────────────────────


class PurchaseOrder(ERPBaseModel):
    """
    A purchase order issued to a supplier.

    Status lifecycle:
        DRAFT → CONFIRMED → RECEIVED
                          → CANCELLED
        DRAFT → CANCELLED
    """

    class Status(models.TextChoices):
        DRAFT     = "DRAFT",     _("Borrador")
        CONFIRMED = "CONFIRMED", _("Confirmada")
        RECEIVED  = "RECEIVED",  _("Recibida")
        CANCELLED = "CANCELLED", _("Anulada")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="purchase_orders",
        verbose_name=_("organización"),
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
        verbose_name=_("proveedor"),
    )
    number = models.CharField(
        max_length=30,
        blank=True,
        editable=False,
        verbose_name=_("número"),
        help_text=_("Asignado automáticamente al confirmar."),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name=_("estado"),
    )
    issue_date = models.DateField(verbose_name=_("fecha de emisión"))
    expected_date = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("fecha esperada de recepción"),
        help_text=_("Opcional. Fecha en que se espera recibir la mercancía."),
    )
    notes = models.TextField(blank=True, verbose_name=_("notas"))

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("orden de compra")
        verbose_name_plural = _("órdenes de compra")
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "issue_date"]),
        ]

    def __str__(self):
        return self.number or f"OC-Borrador-{str(self.pk)[:8]}"

    @property
    def display_number(self) -> str:
        return self.number or f"Borrador ({str(self.pk)[:8]})"

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.DRAFT
