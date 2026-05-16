from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel


class Supplier(ERPBaseModel):
    """
    Supplier / vendor catalog entry per organization.
    """

    class Status(models.TextChoices):
        ACTIVE   = "ACTIVE",   _("Activo")
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
        help_text=_("Registro Nacional del Contribuyente (opcional, máx. 11 caracteres)."),
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
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "rnc"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(rnc=""),
                name="unique_active_supplier_rnc_per_org",
            ),
        ]

    def __str__(self):
        if self.rnc:
            return f"{self.name} ({self.rnc})"
        return self.name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE
