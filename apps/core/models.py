import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from simple_history.models import HistoricalRecords


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ── Soft-delete ───────────────────────────────────────────────────────────────

class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.filter(deleted_at__isnull=False)

    def for_org(self, organization):
        """Scope any queryset to the active organization."""
        return self.filter(organization=organization)

    def delete(self):
        """Soft-delete each object so instance deletion policies are enforced."""
        deleted = {}
        count = 0
        with transaction.atomic(using=self.db):
            for obj in self.iterator():
                obj.delete()
                label = obj._meta.label
                deleted[label] = deleted.get(label, 0) + 1
                count += 1
        return count, deleted

    def hard_delete(self):
        """Physically remove records in an explicit destructive workflow."""
        return super().delete()


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def for_org(self, organization):
        return self.get_queryset().for_org(organization)


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()  # bypasses soft-delete filter

    def delete(self, using=None, keep_parents=False):
        # NOTE: pre_delete / post_delete signals are NOT emitted here.
        # Callers that rely on those signals (e.g. guardian cleanup) must
        # trigger cleanup manually or use hard_delete() instead.
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def hard_delete(self):
        super().delete()

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    class Meta:
        abstract = True


# ── Module registry ───────────────────────────────────────────────────────────

class Module(models.Model):
    """System-level registry of ERP modules available in this installation."""
    PROTECTED_SLUGS = {"sales"}

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True, default="bi-grid")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Module"
        verbose_name_plural = "Modules"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.pk:
            return

        original_slug = (
            type(self).objects.filter(pk=self.pk).values_list("slug", flat=True).first()
        )
        if original_slug == self.slug:
            return

        if original_slug in self.PROTECTED_SLUGS:
            raise ValidationError(
                {"slug": _("The canonical sales module slug cannot be changed.")}
            )
        if self.teams.exists():
            raise ValidationError(
                {"slug": _("An assigned module slug cannot be changed.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        if self.slug in self.PROTECTED_SLUGS:
            raise ValidationError(_("The canonical sales module cannot be deleted."))
        if self.teams.exists():
            raise ValidationError(_("An assigned module cannot be deleted."))
        return super().delete(using=using, keep_parents=keep_parents)


# ── ERPBaseModel ──────────────────────────────────────────────────────────────

class ERPBaseModel(TimeStampedModel, SoftDeleteModel):
    """
    Root abstract model for every SabSys entity.

    Entity models (anything with an org scope) must declare:
        organization = models.ForeignKey("accounts.Organization", ...)

    Identity models (Organization and User) are exempt — they ARE the root.

    Queries are always written as:
        MyModel.objects.for_org(request.organization)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True


# ── Notification ──────────────────────────────────────────────────────────────

class Notification(ERPBaseModel):
    """
    In-app alert generated by business-logic signals, not raw views.
    Fan-out (one row per recipient) happens at creation time.
    Render in the navbar bell; surface as a toast for brand-new unread ones.
    """

    class Level(models.TextChoices):
        INFO    = "info",    "Info"
        SUCCESS = "success", "Success"
        WARNING = "warning", "Warning"
        DANGER  = "danger",  "Danger"

    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    level   = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    verb    = models.CharField(max_length=255)        # e.g. "invited you to Finance team"
    url     = models.CharField(max_length=500, blank=True)  # optional deep-link
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(ERPBaseModel.Meta):
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
        ]

    def mark_read(self):
        if not self.read_at:
            self.read_at = timezone.now()
            self.save(update_fields=["read_at"])

    @property
    def is_read(self):
        return self.read_at is not None


# ── AbstractDocumentLineItem ──────────────────────────────────────────────────


class AbstractDocumentLineItem(models.Model):
    """Shared base for SalesDocumentItem and PurchaseDocumentItem.

    Concrete subclasses must add:
      - A FK to the parent document (e.g. ``document`` or ``purchase_document``)
      - An optional FK to ``items.Item`` (with a subclass-specific related_name)
      - A ``clean()`` that validates item.organization == parent.organization
      - A ``Meta`` with verbose_name, ordering and app-specific constraint names
    """

    class ITBISRate(models.TextChoices):
        EXEMPT = "EXEMPT", _("Exento (0%)")
        RATE_0 = "RATE_0", _("Tasa 0% (exportación)")
        RATE_16 = "RATE_16", _("ITBIS 16%")
        RATE_18 = "RATE_18", _("ITBIS 18%")

    RATE_VALUES = {
        ITBISRate.EXEMPT: Decimal("0.00"),
        ITBISRate.RATE_0: Decimal("0.00"),
        ITBISRate.RATE_16: Decimal("0.16"),
        ITBISRate.RATE_18: Decimal("0.18"),
    }

    description = models.CharField(max_length=500, verbose_name=_("descripción"))
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("1.0000"),
        validators=[MinValueValidator(Decimal("0.0001"))],
        verbose_name=_("cantidad"),
    )
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        verbose_name=_("precio unitario (sin ITBIS)"),
    )
    itbis_rate = models.CharField(
        max_length=8,
        choices=ITBISRate.choices,
        default=ITBISRate.RATE_18,
        verbose_name=_("tasa ITBIS"),
    )

    # Computed fields — stored for report generation
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("total línea (sin ITBIS)"),
    )
    itbis_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("monto ITBIS"),
    )
    line_total_with_itbis = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("total línea con ITBIS"),
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.description} × {self.quantity}"

    def compute(self):
        """Recompute line totals from quantity, unit_price and itbis_rate."""
        rate = self.RATE_VALUES.get(self.itbis_rate, Decimal("0.00"))
        self.line_total = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        self.itbis_amount = (self.line_total * rate).quantize(Decimal("0.01"))
        self.line_total_with_itbis = self.line_total + self.itbis_amount

    def save(self, *args, **kwargs):
        self.full_clean()
        self.compute()
        super().save(*args, **kwargs)
