import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
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
