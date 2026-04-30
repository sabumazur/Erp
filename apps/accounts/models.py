import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel, SoftDeleteQuerySet


class UserManager(BaseUserManager):
    def get_queryset(self):
        # FIX: filter soft-deleted users so User.objects never leaks deleted rows.
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, ERPBaseModel):
    email = models.EmailField(unique=True, verbose_name=_("email"))
    first_name = models.CharField(max_length=150, blank=True, verbose_name=_("first name"))
    last_name = models.CharField(max_length=150, blank=True, verbose_name=_("last name"))
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True, verbose_name=_("avatar"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))
    is_staff = models.BooleanField(default=False, verbose_name=_("staff status"))

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Organization(ERPBaseModel):
    name = models.CharField(max_length=255, verbose_name=_("name"))
    slug = models.SlugField(unique=True, max_length=255, verbose_name=_("slug"))
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_organizations",
        verbose_name=_("owner"),
    )
    logo = models.ImageField(upload_to="org_logos/", null=True, blank=True, verbose_name=_("logo"))
    is_active = models.BooleanField(default=True, verbose_name=_("active"))

    # Contact & identity
    tax_id = models.CharField(max_length=50, blank=True, verbose_name=_("tax ID"))
    email = models.EmailField(blank=True, verbose_name=_("email"))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("phone"))
    website = models.URLField(blank=True, verbose_name=_("website"))

    # Address
    address = models.CharField(max_length=255, blank=True, verbose_name=_("address"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("city"))
    state = models.CharField(max_length=100, blank=True, verbose_name=_("state"))
    zip_code = models.CharField(max_length=20, blank=True, verbose_name=_("zip code"))
    country = models.CharField(max_length=100, blank=True, verbose_name=_("country"))

    class Meta:
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

    def __str__(self):
        return self.name


class Team(ERPBaseModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    modules = models.ManyToManyField(
        "core.Module",
        blank=True,
        related_name="teams",
        verbose_name=_("module access"),
        help_text=_("Leave empty to grant access to all modules."),
    )

    class Meta:
        # FIX: partial index instead of unique_together so soft-deleted teams
        # don't block re-creating a team with the same name in the same org.
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_team_name_per_org",
            )
        ]
        verbose_name = _("team")
        verbose_name_plural = _("teams")

    def __str__(self):
        return f"{self.organization.name} › {self.name}"


class Membership(ERPBaseModel):
    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        ADMIN = "admin", _("Admin")
        MEMBER = "member", _("Member")
        VIEWER = "viewer", _("Viewer")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    team = models.ForeignKey(
        Team, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        # FIX: partial index so a re-invited user (after soft-delete) is allowed.
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_active_user_org_membership",
            )
        ]
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")

    def __str__(self):
        return f"{self.user.email} @ {self.organization.name} [{self.role}]"

    @property
    def is_admin(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN)


class Invitation(ERPBaseModel):
    email = models.EmailField()
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invitations"
    )
    role = models.CharField(
        max_length=20, choices=Membership.Role.choices, default=Membership.Role.MEMBER
    )
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sent_invitations"
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email", "organization"],
                condition=models.Q(accepted_at__isnull=True, deleted_at__isnull=True),
                name="unique_pending_invitation_per_org",
            )
        ]
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")

    def __str__(self):
        return f"{self.email} → {self.organization.name}"

    @classmethod
    def create_for(cls, email, organization, role, invited_by):
        return cls.objects.create(
            email=email.lower(),
            organization=organization,
            role=role,
            invited_by=invited_by,
            expires_at=timezone.now() + timedelta(days=7),
        )

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_pending(self):
        return self.accepted_at is None and not self.is_expired
