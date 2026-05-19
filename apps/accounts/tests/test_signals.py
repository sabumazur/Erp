import pytest
from django.utils import timezone

from apps.accounts.models import User, Organization, Membership, Invitation
from apps.accounts.signals import _remove_ghost_org
from apps.accounts.tests.factories import UserFactory, OrganizationFactory, MembershipFactory


# ── create_default_organization signal ───────────────────────────────────────

@pytest.mark.django_db
class TestCreateDefaultOrganization:

    def test_pending_invitation_blocks_workspace_creation(self):
        org = OrganizationFactory()
        admin = UserFactory()
        Invitation.create_for(
            email="newuser@example.com",
            organization=org,
            role=Membership.Role.MEMBER,
            invited_by=admin,
        )
        user = User.objects.create_user(email="newuser@example.com", password="Str0ng!Pass1")
        assert Organization.objects.filter(owner=user).count() == 0

    def test_expired_invitation_does_not_block_workspace_creation(self):
        org = OrganizationFactory()
        admin = UserFactory()
        invitation = Invitation.create_for(
            email="newuser2@example.com",
            organization=org,
            role=Membership.Role.MEMBER,
            invited_by=admin,
        )
        invitation.expires_at = timezone.now() - timezone.timedelta(hours=1)
        invitation.save(update_fields=["expires_at"])

        user = User.objects.create_user(email="newuser2@example.com", password="Str0ng!Pass1")
        assert Organization.objects.filter(owner=user).count() == 1

    def test_workspace_name_derived_from_email(self):
        user = User.objects.create_user(email="jane@example.com", password="Str0ng!Pass1")
        org = Organization.objects.get(owner=user)
        assert "jane" in org.name.lower()


# ── _remove_ghost_org helper ──────────────────────────────────────────────────

@pytest.mark.django_db
class TestRemoveGhostOrg:

    def test_removes_solo_empty_org(self, owner_membership):
        ghost_user = UserFactory()
        ghost_org = OrganizationFactory(owner=ghost_user)
        MembershipFactory(user=ghost_user, organization=ghost_org, role=Membership.Role.OWNER)

        _remove_ghost_org(ghost_user, owner_membership.organization)

        assert not Organization.all_objects.filter(pk=ghost_org.pk).exists()

    def test_preserves_org_with_customers(self, owner_membership):
        from apps.invoices.tests.factories import CustomerFactory

        ghost_user = UserFactory()
        ghost_org = OrganizationFactory(owner=ghost_user)
        MembershipFactory(user=ghost_user, organization=ghost_org, role=Membership.Role.OWNER)
        CustomerFactory(organization=ghost_org)

        _remove_ghost_org(ghost_user, owner_membership.organization)

        assert Organization.objects.filter(pk=ghost_org.pk).exists()

    def test_preserves_shared_org(self, owner_membership):
        user = UserFactory()
        shared_org = OrganizationFactory(owner=user)
        MembershipFactory(user=user, organization=shared_org, role=Membership.Role.OWNER)
        MembershipFactory(organization=shared_org, role=Membership.Role.MEMBER)

        _remove_ghost_org(user, owner_membership.organization)

        assert Organization.objects.filter(pk=shared_org.pk).exists()

    def test_does_not_remove_invited_org(self, owner_membership):
        user = UserFactory()
        solo_org = owner_membership.organization
        MembershipFactory(user=user, organization=solo_org, role=Membership.Role.MEMBER)

        _remove_ghost_org(user, solo_org)

        assert Organization.objects.filter(pk=solo_org.pk).exists()
