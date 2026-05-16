from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel


class Supplier(ERPBaseModel):
    """A vendor / supplier scoped to an organization."""

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="suppliers",
        verbose_name=_("organización"),
    )
    name = models.CharField(max_length=255, verbose_name=_("nombre"))
    tax_id = models.CharField(
        max_length=50, blank=True, verbose_name=_("RNC / Cédula")
    )
    email = models.EmailField(blank=True, verbose_name=_("correo electrónico"))
    phone = models.CharField(max_length=30, blank=True, verbose_name=_("teléfono"))
    contact_name = models.CharField(
        max_length=150, blank=True, verbose_name=_("contacto")
    )
    address = models.CharField(max_length=255, blank=True, verbose_name=_("dirección"))
    notes = models.TextField(blank=True, verbose_name=_("notas"))

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("proveedor")
        verbose_name_plural = _("proveedores")
        unique_together = [("organization", "name")]

    def __str__(self):
        return self.name


class PurchaseOrder(ERPBaseModel):
    """A purchase order raised against a supplier."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Borrador")
        CONFIRMED = "CONFIRMED", _("Confirmada")
        RECEIVED = "RECEIVED", _("Recibida")
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
        null=True, blank=True, verbose_name=_("fecha esperada de entrega")
    )
    notes = models.TextField(blank=True, verbose_name=_("notas"))

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("orden de compra")
        verbose_name_plural = _("órdenes de compra")

    def __str__(self):
        return self.number or f"OC-{str(self.pk)[:8].upper()}"
