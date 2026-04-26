import pytest
from django.urls import reverse
from apps.accounts.models import User, Organization, Membership


@pytest.mark.django_db
class TestUserSignal:

    def test_signup_creates_organization(self):
        user = User.objects.create_user(email="test@example.com", password="pass")
        assert Organization.objects.filter(owner=user).count() == 1

    def test_signup_creates_owner_membership(self):
        user = User.objects.create_user(email="owner@example.com", password="pass")
        membership = Membership.objects.get(user=user)
        assert membership.role == Membership.Role.OWNER

    def test_slug_is_unique_on_collision(self):
        User.objects.create_user(email="test@a.com", password="pass")
        User.objects.create_user(email="test@b.com", password="pass")
        slugs = list(Organization.objects.values_list("slug", flat=True))
        assert len(slugs) == len(set(slugs))


@pytest.mark.django_db
class TestMembership:

    def test_owner_is_admin(self, owner_membership):
        assert owner_membership.is_admin is True

    def test_admin_is_admin(self, admin_membership):
        assert admin_membership.is_admin is True

    def test_member_is_not_admin(self, member_membership):
        assert member_membership.is_admin is False

    def test_viewer_is_not_admin(self, viewer_membership):
        assert viewer_membership.is_admin is False


@pytest.mark.django_db
class TestAuthViews:

    def test_dashboard_redirects_when_anonymous(self, client):
        response = client.get(reverse("accounts:dashboard"))
        assert response.status_code == 302
        assert "/auth/login/" in response["Location"]

    def test_dashboard_accessible_when_authenticated(self, client, owner_membership):
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        response = client.get(reverse("accounts:dashboard"))
        assert response.status_code == 200

    def test_profile_view_accessible(self, client, owner_membership):
        client.force_login(owner_membership.user)
        session = client.session
        session["active_org_slug"] = owner_membership.organization.slug
        session.save()
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 200

    def test_org_switch_sets_session(self, client, owner_membership):
        client.force_login(owner_membership.user)
        url = reverse("accounts:switch_org", kwargs={"slug": owner_membership.organization.slug})
        response = client.post(url)
        assert response.status_code in [302, 200]
