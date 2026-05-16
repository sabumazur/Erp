from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel


class ExpenseCategory(ERPBaseModel):
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="expense_categories",
        verbose_name=_("organización"),
    )
    name = models.CharField(max_length=150, verbose_name=_("nombre"))

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("categoría de gasto")
        verbose_name_plural = _("categorías de gasto")
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_expense_category_name_per_org",
            ),
        ]

    def __str__(self):
        return self.name


class Expense(ERPBaseModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pendiente")
        APPROVED = "APPROVED", _("Aprobado")
        REJECTED = "REJECTED", _("Rechazado")

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="expenses",
        verbose_name=_("organización"),
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name=_("categoría"),
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name=_("monto"),
    )
    date = models.DateField(verbose_name=_("fecha"))
    description = models.TextField(blank=True, verbose_name=_("descripción"))
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name=_("estado"),
    )
    approved_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_expenses",
        verbose_name=_("aprobado por"),
    )

    class Meta(ERPBaseModel.Meta):
        verbose_name = _("gasto")
        verbose_name_plural = _("gastos")

    def __str__(self):
        return f"{self.category} – {self.amount} ({self.date})"
