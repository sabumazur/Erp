import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Invitation, Membership
from apps.accounts.tests.factories import UserFactory, MembershipFactory


def _org_client(client, membership):
    """Log in as membership.user with the org active in session."""
    client.force_login(membership.user)
    session = client.session
    session["active_org_slug"] = membership.organization.slug
    session.save()
    return client


# ── Sending invitations ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestInviteMemberView:

    def test_admin_can_invite(self, client, owner_membership, mailoutbox):
        c = _org_client(client, owner_membership)
        response = c.post(reverse("accounts:invite_member"), {
            "email": "newmember@example.com",
            "role": Membership.Role.MEMBER,
        })
        assert response.status_code == 302
        assert Invitation.objects.filter(
            email="newmember@example.com",
            organization=owner_membership.organization,
            accepted_at__isnull=True,
        ).exists()

    def test_invite_sends_email(self, client, owner_membership, mailoutbox):
        c = _org_client(client, owner_membership)
        c.post(reverse("accounts:invite_member"), {
            "email": "newmember@example.com",
            "role": Membership.Role.MEMBER,
        })
        assert len(mailoutbox) == 1
        assert "newmember@example.com" in mailoutbox[0].to

    def test_invite_normalises_email_to_lowercase(self, client, owner_membership, mailoutbox):
        c = _org_client(client, owner_membership)
        c.post(reverse("accounts:invite_member"), {
            "email": "NewMember@Example.COM",
            "role": Membership.Role.MEMBER,
        })
        assert Invitation.objects.filter(email="newmember@example.com").exists()

    def test_non_admin_cannot_invite(self, client, member_membership):
        c = _org_client(client, member_membership)
        response = c.post(reverse("accounts:invite_member"), {
            "email": "someone@example.com",
            "role": Membership.Role.MEMBER,
        })
        assert response.status_code == 403

    def test_duplicate_invite_rejected(self, client, owner_membership, mailoutbox):
        c = _org_client(client, owner_membership)
        c.post(reverse("accounts:invite_member"), {
            "email": "dup@example.com",
            "role": Membership.Role.MEMBER,
        })
        response = c.post(reverse("accounts:invite_member"), {
            "email": "dup@example.com",
            "role": Membership.Role.MEMBER,
        })
        assert response.status_code == 302
        assert Invitation.objects.filter(email="dup@example.com").count() == 1

    def test_existing_member_cannot_be_invited(self, client, owner_membership, member_membership, mailoutbox):
        c = _org_client(client, owner_membership)
        response = c.post(reverse("accounts:invite_member"), {
            "email": member_membership.user.email,
            "role": Membership.Role.MEMBER,
        })
        assert response.status_code == 302
        assert not Invitation.objects.filter(
            email=member_membership.user.email,
            organization=owner_membership.organization,
        ).exists()


# ── Accepting invitations ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAcceptInvitationView:

    def _make_invitation(self, owner_membership, email="invitee@example.com", role=Membership.Role.MEMBER):
        return Invitation.create_for(
            email=email,
            organization=owner_membership.organization,
            role=role,
            invited_by=owner_membership.user,
        )

    # ── Happy path ────────────────────────────────────────────────────────────

    def test_accept_creates_membership(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        invitee = UserFactory(email="invitee@example.com")

        client.force_login(invitee)
        response = client.get(
            reverse("accounts:accept_invitation", args=[invitation.pk])
        )

        assert response.status_code == 302
        assert Membership.objects.filter(
            user=invitee,
            organization=owner_membership.organization,
            role=Membership.Role.MEMBER,
        ).exists()

    def test_accept_marks_invitation_used(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        invitee = UserFactory(email="invitee@example.com")

        client.force_login(invitee)
        client.get(reverse("accounts:accept_invitation", args=[invitation.pk]))

        invitation.refresh_from_db()
        assert invitation.accepted_at is not None

    def test_accept_sets_active_org_in_session(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        invitee = UserFactory(email="invitee@example.com")

        client.force_login(invitee)
        client.get(reverse("accounts:accept_invitation", args=[invitation.pk]))

        assert client.session["active_org_slug"] == owner_membership.organization.slug

    def test_accept_with_owner_role(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership, role=Membership.Role.OWNER)
        invitee = UserFactory(email="invitee@example.com")

        client.force_login(invitee)
        client.get(reverse("accounts:accept_invitation", args=[invitation.pk]))

        membership = Membership.objects.get(
            user=invitee, organization=owner_membership.organization
        )
        assert membership.role == Membership.Role.OWNER

    # ── Wrong account ─────────────────────────────────────────────────────────

    def test_wrong_email_shows_error(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership, email="right@example.com")
        wrong_user = UserFactory(email="wrong@example.com")

        client.force_login(wrong_user)
        response = client.get(
            reverse("accounts:accept_invitation", args=[invitation.pk])
        )

        assert response.status_code == 200
        assert b"Cuenta incorrecta" in response.content

    def test_wrong_email_does_not_create_membership(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership, email="right@example.com")
        wrong_user = UserFactory(email="wrong@example.com")

        client.force_login(wrong_user)
        client.get(reverse("accounts:accept_invitation", args=[invitation.pk]))

        assert not Membership.objects.filter(
            user=wrong_user, organization=owner_membership.organization
        ).exists()

    def test_wrong_email_does_not_consume_token(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership, email="right@example.com")
        wrong_user = UserFactory(email="wrong@example.com")

        client.force_login(wrong_user)
        client.get(reverse("accounts:accept_invitation", args=[invitation.pk]))

        invitation.refresh_from_db()
        assert invitation.accepted_at is None

    # ── Unauthenticated ───────────────────────────────────────────────────────

    def test_unauthenticated_shows_login_prompt(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        response = client.get(
            reverse("accounts:accept_invitation", args=[invitation.pk])
        )
        assert response.status_code == 200
        assert b"login_required" not in response.content  # status value not rendered
        assert b"Ya tengo una cuenta" in response.content

    def test_unauthenticated_login_url_preserves_next(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        response = client.get(
            reverse("accounts:accept_invitation", args=[invitation.pk])
        )
        accept_path = reverse("accounts:accept_invitation", args=[invitation.pk])
        assert accept_path.encode() in response.content

    # ── Already accepted ──────────────────────────────────────────────────────

    def test_already_accepted_redirects_if_user_is_member(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        invitee = UserFactory(email="invitee@example.com")
        # Accept it first
        client.force_login(invitee)
        client.get(reverse("accounts:accept_invitation", args=[invitation.pk]))
        # Visit again
        response = client.get(
            reverse("accounts:accept_invitation", args=[invitation.pk])
        )
        assert response.status_code == 302
        assert reverse("accounts:dashboard") in response["Location"]

    def test_already_accepted_shows_screen_for_non_member(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        invitee = UserFactory(email="invitee@example.com")
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=["accepted_at"])

        other_user = UserFactory(email="other@example.com")
        client.force_login(other_user)
        response = client.get(
            reverse("accounts:accept_invitation", args=[invitation.pk])
        )
        assert response.status_code == 200
        assert owner_membership.organization.name.encode() in response.content

    # ── Expired ───────────────────────────────────────────────────────────────

    def test_expired_invitation_shows_error(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        invitation.expires_at = timezone.now() - timezone.timedelta(days=1)
        invitation.save(update_fields=["expires_at"])

        invitee = UserFactory(email="invitee@example.com")
        client.force_login(invitee)
        response = client.get(
            reverse("accounts:accept_invitation", args=[invitation.pk])
        )
        assert response.status_code == 200
        assert "expirada".encode() in response.content  # Spanish: "Invitación expirada"

    def test_expired_invitation_does_not_create_membership(self, client, owner_membership):
        invitation = self._make_invitation(owner_membership)
        invitation.expires_at = timezone.now() - timezone.timedelta(days=1)
        invitation.save(update_fields=["expires_at"])

        invitee = UserFactory(email="invitee@example.com")
        client.force_login(invitee)
        client.get(reverse("accounts:accept_invitation", args=[invitation.pk]))

        assert not Membership.objects.filter(
            user=invitee, organization=owner_membership.organization
        ).exists()


# ── Signal: auto-accept on login ──────────────────────────────────────────────

@pytest.mark.django_db
class TestAcceptPendingInvitationSignal:

    def test_login_auto_accepts_pending_invitation(self, client, owner_membership):
        Invitation.create_for(
            email="auto@example.com",
            organization=owner_membership.organization,
            role=Membership.Role.MEMBER,
            invited_by=owner_membership.user,
        )
        # Register user AFTER invitation was created
        invitee = UserFactory(email="auto@example.com")

        # Simulate allauth login (fires user_logged_in signal)
        client.force_login(invitee)
        # Signal fires on force_login in allauth? No — use the login view.
        # Trigger via the allauth login endpoint instead:
        invitee.set_password("Str0ngP@ss!")
        invitee.save()
        client.logout()
        client.post(
            reverse("account_login"),
            {"login": "auto@example.com", "password": "Str0ngP@ss!"},
        )

        assert Membership.objects.filter(
            user=invitee,
            organization=owner_membership.organization,
        ).exists()

    def test_login_auto_accept_marks_invitation_used(self, client, owner_membership):
        invitation = Invitation.create_for(
            email="auto2@example.com",
            organization=owner_membership.organization,
            role=Membership.Role.MEMBER,
            invited_by=owner_membership.user,
        )
        invitee = UserFactory(email="auto2@example.com")
        invitee.set_password("Str0ngP@ss!")
        invitee.save()

        client.post(
            reverse("account_login"),
            {"login": "auto2@example.com", "password": "Str0ngP@ss!"},
        )

        invitation.refresh_from_db()
        assert invitation.accepted_at is not None

    def test_login_does_not_accept_expired_invitation(self, client, owner_membership):
        invitation = Invitation.create_for(
            email="expired@example.com",
            organization=owner_membership.organization,
            role=Membership.Role.MEMBER,
            invited_by=owner_membership.user,
        )
        invitation.expires_at = timezone.now() - timezone.timedelta(days=1)
        invitation.save(update_fields=["expires_at"])

        invitee = UserFactory(email="expired@example.com")
        invitee.set_password("Str0ngP@ss!")
        invitee.save()

        client.post(
            reverse("account_login"),
            {"login": "expired@example.com", "password": "Str0ngP@ss!"},
        )

        assert not Membership.objects.filter(
            user=invitee, organization=owner_membership.organization
        ).exists()
