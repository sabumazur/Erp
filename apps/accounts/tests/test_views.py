import pytest
from django.urls import reverse

from apps.accounts.models import Membership, Team, Invitation
from apps.accounts.tests.factories import (
    MembershipFactory, OrganizationFactory, TeamFactory,
)


def _login(client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_org_slug"] = membership.organization.slug
    session.save()


# ── Profile ───────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestProfileView:

    def test_requires_login(self, client):
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 302

    def test_get_returns_200(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 200

    def test_post_updates_profile(self, client, member_membership):
        _login(client, member_membership)
        response = client.post(reverse("accounts:profile"), {
            "first_name": "Juan",
            "last_name": "Pérez",
        })
        assert response.status_code == 302
        member_membership.user.refresh_from_db()
        assert member_membership.user.first_name == "Juan"
        assert member_membership.user.last_name == "Pérez"


# ── Organization settings ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestOrganizationSettingsView:

    _VALID_DATA = {
        "name": "Nombre Actualizado",
        "tax_id": "101234567",
        "email": "org@example.com",
        "phone": "809-555-1234",
        "website": "https://example.com",
        "address": "Calle Principal 1",
        "city": "Santo Domingo",
        "state": "Distrito Nacional",
        "zip_code": "10100",
        "country": "República Dominicana",
    }

    def test_requires_admin(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("accounts:org_settings"))
        assert response.status_code == 403

    def test_admin_can_view_form(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.get(reverse("accounts:org_settings"))
        assert response.status_code == 200

    def test_post_updates_org_name(self, client, admin_membership):
        _login(client, admin_membership)
        client.post(reverse("accounts:org_settings"), self._VALID_DATA)
        admin_membership.organization.refresh_from_db()
        assert admin_membership.organization.name == "Nombre Actualizado"

    def test_post_valid_redirects(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.post(reverse("accounts:org_settings"), self._VALID_DATA)
        assert response.status_code == 302


# ── Member list ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestMemberListView:

    def test_requires_admin(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("accounts:members"))
        assert response.status_code == 403

    def test_admin_can_view(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.get(reverse("accounts:members"))
        assert response.status_code == 200

    def test_viewer_cannot_view(self, client, viewer_membership):
        _login(client, viewer_membership)
        response = client.get(reverse("accounts:members"))
        assert response.status_code == 403


# ── Change member role ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestChangeMemberRoleView:

    def test_requires_admin(self, client, member_membership):
        _login(client, member_membership)
        other = MembershipFactory(organization=member_membership.organization)
        response = client.post(
            reverse("accounts:member_role", args=[other.pk]),
            {"role": Membership.Role.VIEWER},
        )
        assert response.status_code == 403

    def test_admin_can_change_role(self, client, admin_membership, member_membership):
        _login(client, admin_membership)
        client.post(
            reverse("accounts:member_role", args=[member_membership.pk]),
            {"role": Membership.Role.VIEWER},
        )
        member_membership.refresh_from_db()
        assert member_membership.role == Membership.Role.VIEWER

    def test_cannot_change_own_role(self, client, admin_membership):
        _login(client, admin_membership)
        client.post(
            reverse("accounts:member_role", args=[admin_membership.pk]),
            {"role": Membership.Role.MEMBER},
        )
        admin_membership.refresh_from_db()
        assert admin_membership.role == Membership.Role.ADMIN

    def test_invalid_role_rejected(self, client, admin_membership, member_membership):
        _login(client, admin_membership)
        client.post(
            reverse("accounts:member_role", args=[member_membership.pk]),
            {"role": "superuser"},
        )
        member_membership.refresh_from_db()
        assert member_membership.role == Membership.Role.MEMBER

    def test_non_owner_cannot_assign_owner_role(self, client, admin_membership, member_membership):
        _login(client, admin_membership)
        response = client.post(
            reverse("accounts:member_role", args=[member_membership.pk]),
            {"role": Membership.Role.OWNER},
        )
        assert response.status_code == 403

    def test_non_owner_cannot_assign_admin_role(self, client, admin_membership, member_membership):
        _login(client, admin_membership)
        response = client.post(
            reverse("accounts:member_role", args=[member_membership.pk]),
            {"role": Membership.Role.ADMIN},
        )
        assert response.status_code == 403

    def test_owner_can_assign_admin_role(self, client, owner_membership, member_membership):
        _login(client, owner_membership)
        client.post(
            reverse("accounts:member_role", args=[member_membership.pk]),
            {"role": Membership.Role.ADMIN},
        )
        member_membership.refresh_from_db()
        assert member_membership.role == Membership.Role.ADMIN


# ── Remove member ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRemoveMemberView:

    def test_requires_admin(self, client, member_membership):
        _login(client, member_membership)
        other = MembershipFactory(organization=member_membership.organization)
        response = client.post(reverse("accounts:member_remove", args=[other.pk]))
        assert response.status_code == 403

    def test_admin_can_remove_member(self, client, admin_membership, member_membership):
        _login(client, admin_membership)
        pk = member_membership.pk
        client.post(reverse("accounts:member_remove", args=[pk]))
        assert not Membership.objects.filter(pk=pk).exists()

    def test_cannot_remove_self(self, client, admin_membership):
        _login(client, admin_membership)
        pk = admin_membership.pk
        client.post(reverse("accounts:member_remove", args=[pk]))
        assert Membership.objects.filter(pk=pk).exists()

    def test_cannot_remove_last_owner(self, client, admin_membership, owner_membership):
        _login(client, admin_membership)
        pk = owner_membership.pk
        client.post(reverse("accounts:member_remove", args=[pk]))
        assert Membership.objects.filter(pk=pk).exists()


# ── Resend invitation ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestResendInvitationView:

    def _make_invitation(self, membership):
        return Invitation.create_for(
            email="invitee@example.com",
            organization=membership.organization,
            role=Membership.Role.MEMBER,
            invited_by=membership.user,
        )

    def test_requires_admin(self, client, member_membership):
        invitation = self._make_invitation(member_membership)
        _login(client, member_membership)
        response = client.post(
            reverse("accounts:invitation_resend", args=[invitation.pk])
        )
        assert response.status_code == 403

    def test_resend_sends_email(self, client, owner_membership, mailoutbox):
        invitation = self._make_invitation(owner_membership)
        _login(client, owner_membership)
        client.post(reverse("accounts:invitation_resend", args=[invitation.pk]))
        assert len(mailoutbox) == 1

    def test_resend_extends_expiry(self, client, owner_membership, mailoutbox):
        invitation = self._make_invitation(owner_membership)
        original_expires = invitation.expires_at
        _login(client, owner_membership)
        client.post(reverse("accounts:invitation_resend", args=[invitation.pk]))
        invitation.refresh_from_db()
        assert invitation.expires_at >= original_expires


# ── Cancel invitation ─────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCancelInvitationView:

    def _make_invitation(self, membership):
        return Invitation.create_for(
            email="invitee@example.com",
            organization=membership.organization,
            role=Membership.Role.MEMBER,
            invited_by=membership.user,
        )

    def test_requires_admin(self, client, member_membership):
        invitation = self._make_invitation(member_membership)
        _login(client, member_membership)
        response = client.post(
            reverse("accounts:invitation_cancel", args=[invitation.pk])
        )
        assert response.status_code == 403

    def test_admin_can_cancel(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        _login(client, owner_membership)
        client.post(reverse("accounts:invitation_cancel", args=[invitation.pk]))
        assert not Invitation.objects.filter(pk=invitation.pk).exists()


# ── Switch organization ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSwitchOrganizationView:

    def test_member_can_switch_to_own_org(self, client, member_membership):
        _login(client, member_membership)
        client.post(reverse("accounts:switch_org", args=[member_membership.organization.slug]))
        assert client.session["active_org_slug"] == member_membership.organization.slug

    def test_non_member_cannot_switch_to_other_org(self, client, member_membership):
        other_org = OrganizationFactory()
        _login(client, member_membership)
        client.post(reverse("accounts:switch_org", args=[other_org.slug]))
        assert client.session.get("active_org_slug") != other_org.slug

    def test_requires_login(self, client, member_membership):
        response = client.post(
            reverse("accounts:switch_org", args=[member_membership.organization.slug])
        )
        assert response.status_code == 302


# ── Teams ─────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTeamListView:

    def test_requires_admin(self, client, member_membership):
        _login(client, member_membership)
        response = client.get(reverse("accounts:teams"))
        assert response.status_code == 403

    def test_admin_can_view(self, client, admin_membership):
        _login(client, admin_membership)
        response = client.get(reverse("accounts:teams"))
        assert response.status_code == 200

    def test_post_creates_team(self, client, admin_membership):
        _login(client, admin_membership)
        count_before = Team.objects.filter(organization=admin_membership.organization).count()
        client.post(reverse("accounts:teams"), {"name": "Engineering", "description": ""})
        assert Team.objects.filter(organization=admin_membership.organization).count() == count_before + 1


@pytest.mark.django_db
class TestTeamUpdateView:

    def test_requires_admin(self, client, member_membership):
        team = TeamFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.get(reverse("accounts:team_edit", args=[team.pk]))
        assert response.status_code == 403

    def test_admin_can_view_form(self, client, admin_membership):
        team = TeamFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        response = client.get(reverse("accounts:team_edit", args=[team.pk]))
        assert response.status_code == 200

    def test_post_updates_team_name(self, client, admin_membership):
        team = TeamFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        client.post(reverse("accounts:team_edit", args=[team.pk]), {
            "name": "Updated Name",
            "description": "",
        })
        team.refresh_from_db()
        assert team.name == "Updated Name"

    def test_other_org_team_returns_404(self, client, admin_membership):
        other_team = TeamFactory()
        _login(client, admin_membership)
        response = client.get(reverse("accounts:team_edit", args=[other_team.pk]))
        assert response.status_code == 404


@pytest.mark.django_db
class TestTeamDeleteView:

    def test_requires_admin(self, client, member_membership):
        team = TeamFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(reverse("accounts:team_delete", args=[team.pk]))
        assert response.status_code == 403

    def test_admin_can_delete_empty_team(self, client, admin_membership):
        team = TeamFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        client.post(reverse("accounts:team_delete", args=[team.pk]))
        assert not Team.objects.filter(pk=team.pk).exists()

    def test_cannot_delete_team_with_active_members(self, client, admin_membership):
        team = TeamFactory(organization=admin_membership.organization)
        MembershipFactory(organization=admin_membership.organization, team=team)
        _login(client, admin_membership)
        client.post(reverse("accounts:team_delete", args=[team.pk]))
        assert Team.objects.filter(pk=team.pk).exists()


# ── Assign member to team ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAssignMemberTeamView:

    def test_requires_admin(self, client, member_membership):
        other = MembershipFactory(organization=member_membership.organization)
        team = TeamFactory(organization=member_membership.organization)
        _login(client, member_membership)
        response = client.post(
            reverse("accounts:member_assign_team", args=[other.pk]),
            {"team": str(team.pk)},
        )
        assert response.status_code == 403

    def test_admin_can_assign_team(self, client, admin_membership, member_membership):
        team = TeamFactory(organization=admin_membership.organization)
        _login(client, admin_membership)
        client.post(
            reverse("accounts:member_assign_team", args=[member_membership.pk]),
            {"team": str(team.pk)},
        )
        member_membership.refresh_from_db()
        assert member_membership.team == team

    def test_admin_can_unassign_team(self, client, admin_membership, member_membership):
        team = TeamFactory(organization=admin_membership.organization)
        member_membership.team = team
        member_membership.save()
        _login(client, admin_membership)
        client.post(
            reverse("accounts:member_assign_team", args=[member_membership.pk]),
            {"team": ""},
        )
        member_membership.refresh_from_db()
        assert member_membership.team is None


# ── Leave organization ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLeaveOrganizationView:

    def test_member_can_leave_when_has_another_org(self, client, owner_membership):
        other_org = OrganizationFactory()
        member = MembershipFactory(
            organization=owner_membership.organization,
            role=Membership.Role.MEMBER,
        )
        MembershipFactory(user=member.user, organization=other_org)
        client.force_login(member.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        pk = member.pk
        response = client.post(reverse("accounts:leave_org"))
        assert response.status_code == 302
        assert not Membership.objects.filter(pk=pk).exists()

    def test_sole_owner_cannot_leave(self, client, owner_membership):
        other_org = OrganizationFactory()
        MembershipFactory(
            user=owner_membership.user,
            organization=other_org,
            role=Membership.Role.MEMBER,
        )
        _login(client, owner_membership)
        pk = owner_membership.pk
        client.post(reverse("accounts:leave_org"))
        assert Membership.objects.filter(pk=pk).exists()

    def test_cannot_leave_only_organization(self, client, member_membership):
        # member has exactly one org — leaving is blocked
        _login(client, member_membership)
        pk = member_membership.pk
        client.post(reverse("accounts:leave_org"))
        assert Membership.objects.filter(pk=pk).exists()
