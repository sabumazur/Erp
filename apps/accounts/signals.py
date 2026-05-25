import logging

from django.contrib import messages
from django.contrib.auth.signals import (
    user_logged_in as django_user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db import transaction, IntegrityError
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from allauth.account.signals import user_logged_in
from .models import User, Organization, Membership, Invitation, SecurityAuditEvent
from .permissions import assign_org_permissions, revoke_org_permissions

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_default_organization(sender, instance, created, **kwargs):
    """Auto-create a personal workspace on every new user registration."""
    if not created:
        return

    # Users with a pending invitation join an existing org — no personal
    # workspace needed.  Use iexact + expiry check so an expired invitation
    # does not permanently block workspace creation on re-registration.
    if Invitation.objects.filter(
        email__iexact=instance.email,
        accepted_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists():
        return

    base_slug = slugify(instance.email.split("@")[0]) or "org"
    slug = base_slug
    counter = 1
    # FIX: use all_objects (bypasses soft-delete filter) so restored orgs with
    # the same slug are counted and we never collide on DB restore.
    while Organization.all_objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    try:
        # FIX: wrap in atomic savepoint so a concurrent signup that claimed
        # the same slug triggers IntegrityError here, not at request level.
        with transaction.atomic():
            org = Organization.objects.create(
                name=f"{instance.email.split('@')[0]}'s Workspace",
                slug=slug,
                owner=instance,
                is_auto_created_workspace=True,
            )
    except IntegrityError:
        # Race condition: another request beat us to this slug.
        # UUID prefix is unique per user — guaranteed collision-free.
        slug = f"{base_slug}-{str(instance.pk).replace('-', '')[:8]}"
        org = Organization.objects.create(
            name=f"{instance.email.split('@')[0]}'s Workspace",
            slug=slug,
            owner=instance,
            is_auto_created_workspace=True,
        )

    Membership.objects.create(
        user=instance,
        organization=org,
        role=Membership.Role.OWNER,
    )


@receiver(post_save, sender=Membership)
def sync_permissions_on_membership_save(sender, instance, created, **kwargs):
    """On create or role change — revoke everything then re-assign."""
    update_fields = kwargs.get("update_fields")
    if not created and update_fields is not None and "role" not in update_fields:
        return
    revoke_org_permissions(instance)
    assign_org_permissions(instance)


@receiver(pre_delete, sender=Membership)
def revoke_permissions_on_membership_delete(sender, instance, **kwargs):
    """Clean up guardian rows when a membership is hard-deleted."""
    revoke_org_permissions(instance)


@receiver(user_logged_in)
def accept_pending_invitation(sender, request, user, **kwargs):
    """Auto-accept any pending invitations for this email on login."""
    pending = Invitation.objects.filter(
        email__iexact=user.email,
        accepted_at__isnull=True,
        expires_at__gt=timezone.now(),
    )
    for invitation in pending:
        with transaction.atomic():
            _, created = Membership.objects.get_or_create(
                user=user,
                organization=invitation.organization,
                defaults={"role": invitation.role},
            )
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["accepted_at"])
        if created:
            messages.success(request, f"¡Te has unido a {invitation.organization.name}!")
        request.session["active_org_slug"] = invitation.organization.slug


def _security_event_request_fields(request):
    if request is None:
        return {"ip_address": None, "user_agent": ""}
    return {
        "ip_address": request.META.get("REMOTE_ADDR") or None,
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
    }


def _record_security_event(**fields):
    try:
        SecurityAuditEvent.objects.create(**fields)
    except Exception:
        logger.exception("Unable to record security audit event '%s'.", fields["event_type"])


@receiver(django_user_logged_in)
def record_login_success(sender, request, user, **kwargs):
    if request is not None:
        logged_in_at = timezone.now().isoformat()
        request.session.setdefault("session_started_at", logged_in_at)
        request.session["session_last_activity_at"] = logged_in_at
    _record_security_event(
        event_type=SecurityAuditEvent.EventType.LOGIN_SUCCESS,
        user=user,
        email=user.email,
        organization=getattr(request, "organization", None),
        **_security_event_request_fields(request),
    )


@receiver(user_login_failed)
def record_login_failure(sender, credentials, request, **kwargs):
    attempted_email = (
        credentials.get("login")
        or credentials.get("email")
        or credentials.get("username")
        or ""
    ).lower()
    user = User.objects.filter(email__iexact=attempted_email).first() if attempted_email else None
    _record_security_event(
        event_type=SecurityAuditEvent.EventType.LOGIN_FAILED,
        user=user,
        email=attempted_email,
        **_security_event_request_fields(request),
    )


@receiver(user_logged_out)
def record_logout(sender, request, user, **kwargs):
    if user is None:
        return
    event_type = getattr(request, "_security_logout_reason", SecurityAuditEvent.EventType.LOGOUT)
    _record_security_event(
        event_type=event_type,
        user=user,
        email=user.email,
        organization=getattr(request, "organization", None),
        **_security_event_request_fields(request),
    )
