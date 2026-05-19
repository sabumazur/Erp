import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import ERPBaseModel, SoftDeleteQuerySet
from .validators import validate_image_size


class UserManager(BaseUserManager):
    def get_queryset(self):
        # FIX: filter soft-deleted users so User.objects never leaks deleted rows.
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("El correo electrónico es obligatorio.")
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
    email = models.EmailField(unique=True, verbose_name=_("correo electrónico"))
    first_name = models.CharField(max_length=150, blank=True, verbose_name=_("nombre"))
    last_name = models.CharField(max_length=150, blank=True, verbose_name=_("apellido"))
    avatar = models.ImageField(upload_to="avatars/", null=True, blank=True, verbose_name=_("foto de perfil"), validators=[validate_image_size])
    is_active = models.BooleanField(default=True, verbose_name=_("activo"))
    is_staff = models.BooleanField(default=False, verbose_name=_("estado de staff"))

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("usuario")
        verbose_name_plural = _("usuarios")

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Organization(ERPBaseModel):
    name = models.CharField(max_length=255, verbose_name=_("nombre"))
    slug = models.SlugField(unique=True, max_length=255, verbose_name=_("slug"))
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="owned_organizations",
        verbose_name=_("propietario"),
    )
    logo = models.ImageField(upload_to="org_logos/", null=True, blank=True, verbose_name=_("logotipo"), validators=[validate_image_size])
    is_active = models.BooleanField(default=True, verbose_name=_("activo"))

    # Contact & identity
    tax_id = models.CharField(max_length=50, blank=True, verbose_name=_("RNC/Cédula"))
    email = models.EmailField(blank=True, verbose_name=_("correo electrónico"))
    phone = models.CharField(max_length=20, blank=True, verbose_name=_("teléfono"))
    website = models.URLField(blank=True, verbose_name=_("sitio web"))

    # Address
    address = models.CharField(max_length=255, blank=True, verbose_name=_("dirección"))
    city = models.CharField(max_length=100, blank=True, verbose_name=_("ciudad"))
    state = models.CharField(max_length=100, blank=True, verbose_name=_("provincia"))
    zip_code = models.CharField(max_length=20, blank=True, verbose_name=_("código postal"))
    country = models.CharField(max_length=100, blank=True, verbose_name=_("país"))

    class Meta:
        verbose_name = _("organización")
        verbose_name_plural = _("organizaciones")

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
        verbose_name=_("acceso a módulos"),
        help_text=_("Dejar vacío para conceder acceso a todos los módulos."),
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
        verbose_name = _("equipo")
        verbose_name_plural = _("equipos")

    def __str__(self):
        return f"{self.organization.name} › {self.name}"

    def delete(self, *args, **kwargs):
        active = self.memberships.filter(deleted_at__isnull=True).count()
        if active:
            raise ValueError(
                f"No se puede eliminar el equipo «{self.name}» porque tiene "
                f"{active} miembro(s) activo(s). Reasígnelos primero."
            )
        return super().delete(*args, **kwargs)


class Membership(ERPBaseModel):
    class Role(models.TextChoices):
        OWNER = "owner", _("Propietario")
        ADMIN = "admin", _("Administrador")
        MEMBER = "member", _("Miembro")
        VIEWER = "viewer", _("Observador")

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
        verbose_name = _("membresía")
        verbose_name_plural = _("membresías")

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
        verbose_name = _("invitación")
        verbose_name_plural = _("invitaciones")

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
        return self.accepted_at is None and self.deleted_at is None and not self.is_expired
