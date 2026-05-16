from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel


class Supplier(ERPBaseModel):
    """
    Supplier / vendor catalog entry per organization.

    Suppliers are org-scoped and soft-deleted. RNC is the Dominican
    tax ID (up to 11 digits, optional for foreign suppliers).
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", _("Activo")
        INACTIVE = "INACTIVE", _("Inactivo")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="suppliers",
        verbose_name=_("organización"),
    )
    name = models.CharField(
        max_length=200,
        verbose_name=_("nombre"),
    )
    rnc = models.CharField(
        max_length=11,
        blank=True,
        verbose_name=_("RNC"),
        help_text=_("Número de registro fiscal (hasta 11 dígitos). Opcional."),
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name=_("teléfono"),
    )
    email = models.EmailField(
        blank=True,
        verbose_name=_("correo electrónico"),
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
        verbose_name=_("estado"),
    )

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("proveedor")
        verbose_name_plural = _("proveedores")
        ordering = ["name"]

    def __str__(self):
        return self.name
