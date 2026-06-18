"""
Tests for NCFSequence CRUD views — zero coverage before this file.

Gaps covered:
  - NCFSequenceListView requires login + admin
  - NCFSequenceListView POST creates a sequence (HTMX path)
  - NCFSequenceDeleteView: blocks delete after NCF issued, allows delete otherwise
  - Org isolation: sequence from another org returns 404
"""
import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import (
    MembershipFactory,
    OrganizationFactory,
    UserFactory,
)
from apps.sales.models import NCFSequence
from .factories import CustomerFactory, NCFSequenceFactory


# ── helpers ───────────────────────────────────────────────────────────────────

def _login(client, user, org):
    client.force_login(user)
    s = client.session
    s["active_org_slug"] = org.slug
    s.save()


def _make_admin(org=None):
    org = org or OrganizationFactory()
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.ADMIN)
    return user, org


def _make_member(org=None):
    org = org or OrganizationFactory()
    user = UserFactory()
    MembershipFactory(user=user, organization=org, role=Membership.Role.MEMBER)
    return user, org


# ── NCFSequenceListView ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNCFSequenceListView:

    def test_requires_login(self, client):
        resp = client.get(reverse("sales:ncf_sequences"))
        assert resp.status_code in (302, 403)

    def test_member_cannot_access(self, client):
        user, org = _make_member()
        _login(client, user, org)
        resp = client.get(reverse("sales:ncf_sequences"))
        assert resp.status_code in (302, 403)

    def test_admin_gets_200(self, client):
        user, org = _make_admin()
        _login(client, user, org)
        resp = client.get(reverse("sales:ncf_sequences"))
        assert resp.status_code == 200

    def test_only_shows_org_sequences(self, client):
        user, org = _make_admin()
        seq = NCFSequenceFactory(organization=org, ncf_type=31)
        other_org = OrganizationFactory()
        other_seq = NCFSequenceFactory(organization=other_org, ncf_type=32)
        _login(client, user, org)

        resp = client.get(reverse("sales:ncf_sequences"))
        seqs = list(resp.context["sequences"])
        pks = [s.pk for s in seqs]
        assert seq.pk in pks
        assert other_seq.pk not in pks

    def test_post_creates_sequence(self, client):
        user, org = _make_admin()
        _login(client, user, org)

        resp = client.post(
            reverse("sales:ncf_sequences"),
            {
                "ncf_type": 32,
                "series": "E",
                "current_seq": 0,
                "max_seq": 9999999999,
                "is_active": True,
            },
        )
        assert resp.status_code in (200, 302)
        assert NCFSequence.objects.filter(organization=org, ncf_type=32).exists()


# ── NCFSequenceDeleteView ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNCFSequenceDeleteView:

    def test_admin_can_delete_unused_sequence(self, client):
        user, org = _make_admin()
        seq = NCFSequenceFactory(organization=org, ncf_type=32, current_seq=0)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:ncf_sequence_delete", kwargs={"pk": seq.pk})
        )
        assert resp.status_code == 302
        assert not NCFSequence.objects.filter(pk=seq.pk).exists()

    def test_cannot_delete_sequence_after_ncf_issued(self, client):
        user, org = _make_admin()
        # current_seq > 0 means NCFs have been issued
        seq = NCFSequenceFactory(organization=org, ncf_type=33, current_seq=5)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:ncf_sequence_delete", kwargs={"pk": seq.pk})
        )
        # Should redirect with error message, sequence should still exist
        assert NCFSequence.objects.filter(pk=seq.pk).exists()

    def test_member_cannot_delete(self, client):
        user, org = _make_member()
        seq = NCFSequenceFactory(organization=org, ncf_type=31, current_seq=0)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:ncf_sequence_delete", kwargs={"pk": seq.pk})
        )
        assert resp.status_code in (302, 403)
        assert NCFSequence.objects.filter(pk=seq.pk).exists()

    def test_returns_404_for_sequence_in_other_org(self, client):
        user, org = _make_admin()
        other_org = OrganizationFactory()
        other_seq = NCFSequenceFactory(organization=other_org, ncf_type=31, current_seq=0)
        _login(client, user, org)

        resp = client.post(
            reverse("sales:ncf_sequence_delete", kwargs={"pk": other_seq.pk})
        )
        assert resp.status_code == 404
