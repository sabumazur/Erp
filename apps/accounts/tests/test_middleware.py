import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from apps.accounts.middleware import OrganizationMiddleware
from apps.accounts.tests.factories import UserFactory, MembershipFactory, OrganizationFactory


def _apply(request):
    OrganizationMiddleware(get_response=lambda r: None)._resolve_org(request)
    return request


def _request(user, session=None):
    req = RequestFactory().get("/")
    req.user = user
    req.session = session if session is not None else {}
    return req


@pytest.mark.django_db
class TestOrganizationMiddleware:

    # ── Anonymous ─────────────────────────────────────────────────────────

    def test_anonymous_gets_no_org(self):
        req = _request(AnonymousUser())
        _apply(req)
        assert req.organization is None
        assert req.membership is None

    # ── Session slug resolves org ─────────────────────────────────────────

    def test_resolves_org_from_session_slug(self):
        m = MembershipFactory()
        req = _request(m.user, session={"active_org_slug": m.organization.slug})
        _apply(req)
        assert req.organization == m.organization
        assert req.membership == m

    # ── Bad slug falls back to first membership ───────────────────────────

    def test_bad_slug_clears_key_and_falls_back(self):
        m = MembershipFactory()
        req = _request(m.user, session={"active_org_slug": "nonexistent-slug-xyz"})
        _apply(req)
        assert req.session.get("active_org_slug") != "nonexistent-slug-xyz"
        assert req.organization == m.organization

    def test_bad_slug_fallback_updates_session(self):
        m = MembershipFactory()
        req = _request(m.user, session={"active_org_slug": "nonexistent-slug-xyz"})
        _apply(req)
        assert req.session.get("active_org_slug") == m.organization.slug

    # ── No slug falls back to first membership ────────────────────────────

    def test_no_slug_resolves_first_membership(self):
        m = MembershipFactory()
        req = _request(m.user, session={})
        _apply(req)
        assert req.organization == m.organization
        assert req.membership == m

    def test_no_slug_sets_session(self):
        m = MembershipFactory()
        req = _request(m.user, session={})
        _apply(req)
        assert req.session.get("active_org_slug") == m.organization.slug

    def test_inactive_selected_org_falls_back_to_usable_membership(self):
        inactive = MembershipFactory()
        fallback = MembershipFactory(user=inactive.user)
        inactive.organization.is_active = False
        inactive.organization.save(update_fields=["is_active", "updated_at"])
        req = _request(inactive.user, session={"active_org_slug": inactive.organization.slug})
        _apply(req)
        assert req.organization == fallback.organization
        assert req.session["active_org_slug"] == fallback.organization.slug

    def test_deleted_org_is_not_resolved(self):
        membership = MembershipFactory()
        membership.organization.delete()
        req = _request(membership.user, session={"active_org_slug": membership.organization.slug})
        _apply(req)
        assert req.organization is None
        assert "active_org_slug" not in req.session

    # ── User with no memberships ──────────────────────────────────────────

    def test_user_with_no_membership_gets_no_org(self):
        user = UserFactory()
        req = _request(user, session={})
        _apply(req)
        assert req.organization is None
        assert req.membership is None
