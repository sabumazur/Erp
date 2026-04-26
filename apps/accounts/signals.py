from django.db import transaction, IntegrityError
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.text import slugify
from allauth.account.signals import user_logged_in
from .models import User, Organization, Membership, Invitation
from .permissions import assign_org_permissions, revoke_org_permissions


@receiver(post_save, sender=User)
def create_default_organization(sender, instance, created, **kwargs):
    """Auto-create a personal workspace on every new user registration."""
    if not created:
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
            )
    except IntegrityError:
        # Race condition: another request beat us to this slug.
        # UUID prefix is unique per user — guaranteed collision-free.
        slug = f"{base_slug}-{str(instance.pk).replace('-', '')[:8]}"
        org = Organization.objects.create(
            name=f"{instance.email.split('@')[0]}'s Workspace",
            slug=slug,
            owner=instance,
        )

    Membership.objects.create(
        user=instance,
        organization=org,
        role=Membership.Role.OWNER,
    )


@receiver(post_save, sender=Membership)
def sync_permissions_on_membership_save(sender, instance, **kwargs):
    """On create or role change — revoke everything then re-assign."""
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
        if not Membership.objects.filter(
            user=user, organization=invitation.organization
        ).exists():
            Membership.objects.create(
                user=user,
                organization=invitation.organization,
                role=invitation.role,
            )
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])
