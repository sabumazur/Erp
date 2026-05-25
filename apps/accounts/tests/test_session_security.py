from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from allauth.usersessions.models import UserSession
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import SecurityAuditEvent, User


def _login(client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_org_slug"] = membership.organization.slug
    session.save()


@pytest.mark.django_db
class TestSecurityAuditEvents:
    def test_successful_login_records_security_event(self, client):
        user = User.objects.create_user(email="audit-login@example.com", password="Str0ngP@ss!")

        response = client.post(
            reverse("account_login"),
            {"login": user.email, "password": "Str0ngP@ss!"},
        )

        assert response.status_code == 302
        event = SecurityAuditEvent.objects.get(event_type=SecurityAuditEvent.EventType.LOGIN_SUCCESS)
        assert event.user == user
        assert event.email == user.email
        assert UserSession.objects.filter(user=user).exists()

    def test_failed_login_records_attempt_without_credentials(self, client):
        response = client.post(
            reverse("account_login"),
            {"login": "failed@example.com", "password": "not-the-password"},
            HTTP_USER_AGENT="Test Agent",
            REMOTE_ADDR="192.0.2.1",
        )

        assert response.status_code == 200
        event = SecurityAuditEvent.objects.get(event_type=SecurityAuditEvent.EventType.LOGIN_FAILED)
        assert event.email == "failed@example.com"
        assert event.user is None
        assert event.ip_address == "192.0.2.1"
        assert "not-the-password" not in str(event.metadata)

    def test_explicit_logout_records_logout_event(self, client, owner_membership):
        _login(client, owner_membership)

        response = client.post(reverse("account_logout"))

        assert response.status_code == 302
        event = SecurityAuditEvent.objects.filter(
            event_type=SecurityAuditEvent.EventType.LOGOUT
        ).latest("created_at")
        assert event.user == owner_membership.user
        assert event.organization == owner_membership.organization

    def test_existing_security_event_cannot_be_edited(self):
        event = SecurityAuditEvent.objects.create(
            event_type=SecurityAuditEvent.EventType.LOGIN_FAILED,
            email="immutable@example.com",
        )
        event.email = "edited@example.com"

        with pytest.raises(ValidationError):
            event.save()

    def test_security_events_cannot_be_bulk_edited_or_deleted(self):
        event = SecurityAuditEvent.objects.create(
            event_type=SecurityAuditEvent.EventType.LOGIN_FAILED,
            email="append-only@example.com",
        )

        with pytest.raises(ValidationError):
            SecurityAuditEvent.objects.filter(pk=event.pk).update(email="changed@example.com")
        with pytest.raises(ValidationError):
            SecurityAuditEvent.objects.filter(pk=event.pk).delete()

    def test_audit_failure_does_not_block_explicit_logout(self, client, owner_membership):
        _login(client, owner_membership)

        with patch.object(
            SecurityAuditEvent.objects,
            "create",
            side_effect=RuntimeError("audit store unavailable"),
        ):
            response = client.post(reverse("account_logout"))

        assert response.status_code == 302
        assert "_auth_user_id" not in client.session


@pytest.mark.django_db
class TestSessionTimeout:
    def test_authenticated_request_initializes_deadlines(self, client, owner_membership):
        _login(client, owner_membership)

        response = client.get(reverse("accounts:dashboard"))

        session = client.session
        assert session["session_started_at"]
        assert session["session_last_activity_at"]
        assert response["X-Session-Expires-At"]
        assert response["X-Session-Expiry-Reason"] == "idle"
        assert response["X-Session-Server-Now"]

    def test_normal_request_does_not_refresh_idle_activity(self, client, owner_membership):
        _login(client, owner_membership)
        client.get(reverse("accounts:dashboard"))
        session = client.session
        old_activity = (timezone.now() - timedelta(minutes=5)).isoformat()
        session["session_last_activity_at"] = old_activity
        session.save()

        client.get(reverse("accounts:dashboard"))

        assert client.session["session_last_activity_at"] == old_activity

    def test_keepalive_updates_idle_time_but_not_absolute_start(self, client, owner_membership):
        _login(client, owner_membership)
        client.get(reverse("accounts:dashboard"))
        session = client.session
        started_at = session["session_started_at"]
        old_activity = (timezone.now() - timedelta(minutes=5)).isoformat()
        session["session_last_activity_at"] = old_activity
        session.save()

        response = client.post(reverse("accounts:session_keepalive"))

        assert response.status_code == 200
        updated_session = client.session
        assert updated_session["session_started_at"] == started_at
        assert updated_session["session_last_activity_at"] != old_activity
        assert response.json()["warning_seconds"] == 120
        assert response.json()["server_now"]

    def test_rejected_keepalive_does_not_refresh_idle_activity(self, owner_membership):
        client = Client(enforce_csrf_checks=True)
        _login(client, owner_membership)
        client.get(reverse("accounts:dashboard"))
        session = client.session
        old_activity = (timezone.now() - timedelta(minutes=5)).isoformat()
        session["session_last_activity_at"] = old_activity
        session.save()

        response = client.post(reverse("accounts:session_keepalive"))

        assert response.status_code == 403
        assert client.session["session_last_activity_at"] == old_activity

    def test_idle_expiration_logs_out_once_with_reason(self, client, owner_membership):
        _login(client, owner_membership)
        client.get(reverse("accounts:dashboard"))
        assert UserSession.objects.filter(user=owner_membership.user).exists()
        session = client.session
        session["session_started_at"] = (timezone.now() - timedelta(hours=1)).isoformat()
        session["session_last_activity_at"] = (timezone.now() - timedelta(minutes=21)).isoformat()
        session.save()

        response = client.get(reverse("accounts:dashboard"))

        assert response.status_code == 302
        assert reverse("account_login") in response["Location"]
        assert "_auth_user_id" not in client.session
        assert SecurityAuditEvent.objects.filter(
            event_type=SecurityAuditEvent.EventType.SESSION_IDLE_EXPIRED,
            user=owner_membership.user,
        ).count() == 1
        assert not SecurityAuditEvent.objects.filter(
            event_type=SecurityAuditEvent.EventType.LOGOUT,
            user=owner_membership.user,
        ).exists()
        assert not UserSession.objects.filter(user=owner_membership.user).exists()

    def test_absolute_expiration_wins_even_with_recent_activity(self, client, owner_membership):
        _login(client, owner_membership)
        session = client.session
        session["session_started_at"] = (timezone.now() - timedelta(hours=9)).isoformat()
        session["session_last_activity_at"] = timezone.now().isoformat()
        session.save()

        client.get(reverse("accounts:dashboard"))

        assert SecurityAuditEvent.objects.filter(
            event_type=SecurityAuditEvent.EventType.SESSION_ABSOLUTE_EXPIRED,
            user=owner_membership.user,
        ).count() == 1

    def test_absolute_expiration_starts_at_login_not_first_page_request(self, client):
        user = User.objects.create_user(email="delayed-login@example.com", password="Str0ngP@ss!")
        response = client.post(
            reverse("account_login"),
            {"login": user.email, "password": "Str0ngP@ss!"},
        )
        assert response.status_code == 302
        assert client.session["session_started_at"]

        session = client.session
        session["session_started_at"] = (timezone.now() - timedelta(hours=9)).isoformat()
        session["session_last_activity_at"] = timezone.now().isoformat()
        session.save()

        response = client.get(reverse("accounts:dashboard"))

        assert response.status_code == 302
        assert "_auth_user_id" not in client.session
        assert SecurityAuditEvent.objects.filter(
            event_type=SecurityAuditEvent.EventType.SESSION_ABSOLUTE_EXPIRED,
            user=user,
        ).exists()

    def test_expired_htmx_request_redirects_instead_of_swapping_login_page(self, client, owner_membership):
        _login(client, owner_membership)
        session = client.session
        session["session_started_at"] = (timezone.now() - timedelta(hours=1)).isoformat()
        session["session_last_activity_at"] = (timezone.now() - timedelta(minutes=21)).isoformat()
        session.save()

        response = client.get(reverse("accounts:dashboard"), HTTP_HX_REQUEST="true")

        assert response.status_code == 200
        assert reverse("account_login") in response["HX-Redirect"]

    def test_authenticated_shell_renders_session_timer_and_post_logout(self, client, owner_membership):
        _login(client, owner_membership)

        response = client.get(reverse("accounts:dashboard"))
        content = response.content.decode()

        assert "session-timeout.js" in content
        assert 'id="session-timeout-config"' in content
        assert '"serverNow":' in content
        assert reverse("accounts:session_keepalive") in content
        assert 'id="session-logout-form"' in content
        assert f'action="{reverse("account_logout")}"' in content


@pytest.mark.django_db
class TestSecurityAuditRetention:
    def test_purge_security_audit_events_supports_dry_run_and_deletes_old_rows(self):
        with patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(days=366)):
            old_event = SecurityAuditEvent.objects.create(
                event_type=SecurityAuditEvent.EventType.LOGIN_FAILED,
                email="old@example.com",
            )
        current_event = SecurityAuditEvent.objects.create(
            event_type=SecurityAuditEvent.EventType.LOGIN_FAILED,
            email="current@example.com",
        )

        output = StringIO()
        call_command("purge_security_audit_events", "--dry-run", stdout=output)
        assert SecurityAuditEvent.objects.filter(pk=old_event.pk).exists()

        call_command("purge_security_audit_events", "--no-input", stdout=StringIO())
        assert not SecurityAuditEvent.objects.filter(pk=old_event.pk).exists()
        assert SecurityAuditEvent.objects.filter(pk=current_event.pk).exists()
