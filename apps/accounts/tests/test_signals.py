import pytest
from django.utils import timezone

from apps.accounts.models import User, Organization, Membership, Invitation
from apps.accounts.tests.factories import UserFactory, OrganizationFactory


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

    def test_personal_workspace_is_marked_as_auto_created(self):
        user = User.objects.create_user(email="personal@example.com", password="Str0ng!Pass1")
        org = Organization.objects.get(owner=user)
        assert org.is_auto_created_workspace is True
