import uuid
import pytest
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import User, Organization, Membership, Team, Invitation
from apps.accounts.tests.factories import (
    UserFactory, OrganizationFactory, MembershipFactory, TeamFactory,
)


@pytest.mark.django_db
class TestUserModel:

    # ── __str__ / full_name ───────────────────────────────────────────────

    def test_str_returns_email(self):
        user = UserFactory(email="jane@example.com")
        assert str(user) == "jane@example.com"

    def test_full_name_with_first_and_last(self):
        user = UserFactory(first_name="Jane", last_name="Doe")
        assert user.full_name == "Jane Doe"

    def test_full_name_fallback_to_email(self):
        user = UserFactory(first_name="", last_name="")
        assert user.full_name == user.email

    def test_full_name_strips_whitespace(self):
        user = UserFactory(first_name="Jane", last_name="")
        assert user.full_name == "Jane"

    # ── UUID PK / timestamps ──────────────────────────────────────────────

    def test_uuid_pk(self):
        user = UserFactory()
        assert isinstance(user.pk, uuid.UUID)

    def test_timestamps_set(self):
        user = UserFactory()
        assert user.created_at is not None
        assert user.updated_at is not None

    # ── Soft delete ───────────────────────────────────────────────────────

    def test_soft_delete_sets_deleted_at(self):
        user = UserFactory()
        user.delete()
        user.refresh_from_db()
        assert user.deleted_at is not None

    def test_soft_deleted_excluded_from_objects(self):
        user = UserFactory()
        pk = user.pk
        user.delete()
        assert not User.objects.filter(pk=pk).exists()

    def test_soft_deleted_visible_in_all_objects(self):
        user = UserFactory()
        pk = user.pk
        user.delete()
        assert User.all_objects.filter(pk=pk).exists()

    # ── UserManager ───────────────────────────────────────────────────────

    def test_create_user_requires_email(self):
        with pytest.raises(ValueError):
            User.objects.create_user(email="", password="pass")

    def test_create_superuser_sets_is_staff_and_superuser(self):
        user = User.objects.create_superuser(email="super@example.com", password="Str0ng!Pass1")
        assert user.is_staff is True
        assert user.is_superuser is True


@pytest.mark.django_db
class TestOrganizationModel:

    def test_str_returns_name(self):
        org = OrganizationFactory(name="Acme Corp")
        assert str(org) == "Acme Corp"

    def test_uuid_pk(self):
        org = OrganizationFactory()
        assert isinstance(org.pk, uuid.UUID)

    def test_soft_delete_sets_deleted_at(self):
        org = OrganizationFactory()
        org.delete()
        org.refresh_from_db()
        assert org.deleted_at is not None

    def test_soft_deleted_excluded_from_objects(self):
        org = OrganizationFactory()
        pk = org.pk
        org.delete()
        assert not Organization.objects.filter(pk=pk).exists()

    def test_soft_deleted_visible_in_all_objects(self):
        org = OrganizationFactory()
        pk = org.pk
        org.delete()
        assert Organization.all_objects.filter(pk=pk).exists()

    def test_slug_used_for_all_objects_uniqueness_check(self):
        org = OrganizationFactory(slug="my-org")
        org.delete()
        # Slug is still in all_objects so we can detect collision
        assert Organization.all_objects.filter(slug="my-org").exists()


@pytest.mark.django_db
class TestTeamModel:

    def test_str_contains_org_and_team_name(self):
        team = TeamFactory(name="Dev Team")
        s = str(team)
        assert "Dev Team" in s
        assert team.organization.name in s

    def test_uuid_pk(self):
        team = TeamFactory()
        assert isinstance(team.pk, uuid.UUID)

    def test_delete_raises_when_has_active_members(self):
        team = TeamFactory()
        MembershipFactory(organization=team.organization, team=team)
        with pytest.raises(ValueError, match="miembro"):
            team.delete()

    def test_delete_succeeds_when_no_active_members(self):
        team = TeamFactory()
        pk = team.pk
        team.delete()
        assert not Team.objects.filter(pk=pk).exists()

    def test_soft_deleted_team_name_can_be_reused_in_same_org(self):
        org = OrganizationFactory()
        team = TeamFactory(organization=org, name="Recycled")
        team.delete()
        new_team = TeamFactory(organization=org, name="Recycled")
        assert new_team.pk != team.pk


@pytest.mark.django_db
class TestMembershipModel:

    def test_str_contains_email_and_org(self):
        m = MembershipFactory()
        s = str(m)
        assert m.user.email in s
        assert m.organization.name in s

    def test_is_admin_owner(self):
        m = MembershipFactory(role=Membership.Role.OWNER)
        assert m.is_admin is True

    def test_is_admin_admin(self):
        m = MembershipFactory(role=Membership.Role.ADMIN)
        assert m.is_admin is True

    def test_is_admin_member(self):
        m = MembershipFactory(role=Membership.Role.MEMBER)
        assert m.is_admin is False

    def test_is_admin_viewer(self):
        m = MembershipFactory(role=Membership.Role.VIEWER)
        assert m.is_admin is False


@pytest.mark.django_db
class TestInvitationModel:

    def _make_invitation(self, email="test@example.com"):
        org = OrganizationFactory()
        user = UserFactory()
        return Invitation.create_for(
            email=email,
            organization=org,
            role=Membership.Role.MEMBER,
            invited_by=user,
        )

    def test_str_contains_email_and_org_name(self):
        inv = self._make_invitation()
        assert "test@example.com" in str(inv)
        assert inv.organization.name in str(inv)

    def test_create_for_sets_expires_at_in_future(self):
        inv = self._make_invitation()
        assert inv.expires_at > timezone.now()

    def test_create_for_normalises_email_to_lowercase(self):
        org = OrganizationFactory()
        user = UserFactory()
        inv = Invitation.create_for(
            email="Test@EXAMPLE.COM",
            organization=org,
            role=Membership.Role.MEMBER,
            invited_by=user,
        )
        assert inv.email == "test@example.com"

    def test_is_expired_false_when_active(self):
        inv = self._make_invitation()
        assert inv.is_expired is False

    def test_is_expired_true_when_past_expires_at(self):
        inv = self._make_invitation()
        inv.expires_at = timezone.now() - timedelta(hours=1)
        inv.save(update_fields=["expires_at"])
        assert inv.is_expired is True

    def test_is_pending_true_when_not_accepted_and_not_expired(self):
        inv = self._make_invitation()
        assert inv.is_pending is True

    def test_is_pending_false_when_accepted(self):
        inv = self._make_invitation()
        inv.accepted_at = timezone.now()
        inv.save(update_fields=["accepted_at"])
        assert inv.is_pending is False

    def test_is_pending_false_when_expired(self):
        inv = self._make_invitation()
        inv.expires_at = timezone.now() - timedelta(hours=1)
        inv.save(update_fields=["expires_at"])
        assert inv.is_pending is False
