import uuid
from django.db import models
from django.utils import timezone


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

    class Meta:
        abstract = True
        ordering = ["-created_at"]
