import pytest
from django.urls import reverse
from apps.accounts.models import Organization, Membership, Invitation


CREATE_URL = reverse("accounts:create_org")


@pytest.mark.django_db
class TestCreateOrganizationAccess:

    def test_anonymous_redirected(self, client):
        response = client.get(CREATE_URL)
        assert response.status_code == 302
        # Anonymous users have is_staff=False, so the dispatch() is_staff guard
        # fires before LoginRequiredMixin and redirects directly to dashboard.
        assert response["Location"] == reverse("accounts:dashboard")

    def test_non_staff_redirected_to_dashboard(self, client, owner_membership):
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        response = client.get(CREATE_URL)
        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:dashboard")

    def test_staff_can_access(self, client, owner_membership):
        owner_membership.user.is_staff = True
        owner_membership.user.save()
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        response = client.get(CREATE_URL)
        assert response.status_code == 200


@pytest.mark.django_db
class TestCreateOrganizationPost:

    def _staff_client(self, client, owner_membership):
        owner_membership.user.is_staff = True
        owner_membership.user.save()
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        return client

    def test_creates_organization(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        assert Organization.objects.filter(name="Acme S.R.L.").exists()

    def test_creates_owner_invitation(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        org = Organization.objects.get(name="Acme S.R.L.")
        inv = Invitation.objects.get(organization=org)
        assert inv.email == "owner@acme.com"
        assert inv.role == Membership.Role.OWNER

    def test_sends_invitation_email(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        assert len(mailoutbox) == 1
        assert "owner@acme.com" in mailoutbox[0].to

    def test_staff_admin_not_added_as_member(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        org = Organization.objects.get(name="Acme S.R.L.")
        assert not Membership.objects.filter(
            user=owner_membership.user, organization=org
        ).exists()

    def test_active_org_unchanged(self, client, owner_membership, mailoutbox):
        original_slug = owner_membership.organization.slug
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        session = client.session
        assert session.get("active_org_slug") == original_slug

    def test_redirects_to_dashboard(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        response = c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "owner@acme.com"})
        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:dashboard")

    def test_invalid_form_rerenders(self, client, owner_membership):
        c = self._staff_client(client, owner_membership)
        response = c.post(CREATE_URL, {"name": "", "owner_email": "owner@acme.com"})
        assert response.status_code == 200

    def test_owner_email_normalised_to_lowercase(self, client, owner_membership, mailoutbox):
        c = self._staff_client(client, owner_membership)
        c.post(CREATE_URL, {"name": "Acme S.R.L.", "owner_email": "Owner@ACME.com"})
        org = Organization.objects.get(name="Acme S.R.L.")
        inv = Invitation.objects.get(organization=org)
        assert inv.email == "owner@acme.com"
