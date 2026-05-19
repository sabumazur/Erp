import pytest

from apps.accounts.models import Membership
from apps.accounts.permissions import can_access_module
from apps.accounts.tests.factories import MembershipFactory, TeamFactory
from apps.core.models import Module


@pytest.mark.django_db
class TestCanAccessModule:

    # ── No membership ─────────────────────────────────────────────────────

    def test_none_membership_returns_false(self):
        assert can_access_module(None, "invoices") is False

    # ── Owner / Admin → always True ───────────────────────────────────────

    def test_owner_always_true(self):
        m = MembershipFactory(role=Membership.Role.OWNER)
        assert can_access_module(m, "invoices") is True

    def test_admin_always_true(self):
        m = MembershipFactory(role=Membership.Role.ADMIN)
        assert can_access_module(m, "invoices") is True

    def test_owner_true_even_for_unknown_module(self):
        m = MembershipFactory(role=Membership.Role.OWNER)
        assert can_access_module(m, "nonexistent-module") is True

    # ── Member / Viewer with no team → True (unrestricted) ───────────────

    def test_member_no_team_returns_true(self):
        m = MembershipFactory(role=Membership.Role.MEMBER, team=None)
        assert can_access_module(m, "invoices") is True

    def test_viewer_no_team_returns_true(self):
        m = MembershipFactory(role=Membership.Role.VIEWER, team=None)
        assert can_access_module(m, "invoices") is True

    # ── Team with no modules → True (empty = unrestricted) ───────────────

    def test_member_on_team_with_no_modules_returns_true(self):
        team = TeamFactory()
        m = MembershipFactory(role=Membership.Role.MEMBER, organization=team.organization, team=team)
        assert can_access_module(m, "invoices") is True

    # ── Team with modules → only allowed slugs pass ───────────────────────

    def test_member_on_team_with_matching_module_returns_true(self):
        module = Module.objects.create(name="Invoices", slug="invoices", is_active=True)
        team = TeamFactory()
        team.modules.add(module)
        m = MembershipFactory(role=Membership.Role.MEMBER, organization=team.organization, team=team)
        assert can_access_module(m, "invoices") is True

    def test_member_on_team_with_disallowed_module_returns_false(self):
        module = Module.objects.create(name="Invoices", slug="invoices", is_active=True)
        team = TeamFactory()
        team.modules.add(module)
        m = MembershipFactory(role=Membership.Role.MEMBER, organization=team.organization, team=team)
        assert can_access_module(m, "reports") is False

    def test_viewer_on_team_with_allowed_module_returns_true(self):
        module = Module.objects.create(name="Reports", slug="reports", is_active=True)
        team = TeamFactory()
        team.modules.add(module)
        m = MembershipFactory(role=Membership.Role.VIEWER, organization=team.organization, team=team)
        assert can_access_module(m, "reports") is True

    def test_viewer_on_team_missing_module_returns_false(self):
        module = Module.objects.create(name="Reports", slug="reports", is_active=True)
        team = TeamFactory()
        team.modules.add(module)
        m = MembershipFactory(role=Membership.Role.VIEWER, organization=team.organization, team=team)
        assert can_access_module(m, "invoices") is False
