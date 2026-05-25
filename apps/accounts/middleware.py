from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from allauth.usersessions.models import UserSession

from .models import Membership, SecurityAuditEvent


class OrganizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._resolve_org(request)
        return self.get_response(request)

    def _resolve_org(self, request):
        request.organization = None
        request.membership = None

        if not request.user.is_authenticated:
            return

        usable_memberships = (
            Membership.objects
            .select_related("organization")
            .filter(
                user=request.user,
                organization__is_active=True,
                organization__deleted_at__isnull=True,
            )
        )
        slug = request.session.get("active_org_slug")

        if slug:
            try:
                membership = usable_memberships.get(organization__slug=slug)
                request.organization = membership.organization
                request.membership = membership
                return
            except Membership.DoesNotExist:
                request.session.pop("active_org_slug", None)

        membership = (
            usable_memberships
            .order_by("created_at")
            .first()
        )
        if membership:
            request.organization = membership.organization
            request.membership = membership
            request.session["active_org_slug"] = membership.organization.slug


class SessionTimeoutMiddleware:
    STARTED_KEY = "session_started_at"
    ACTIVITY_KEY = "session_last_activity_at"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        now = timezone.now()
        started_at = self._read_timestamp(request.session.get(self.STARTED_KEY)) or now
        activity_at = self._read_timestamp(request.session.get(self.ACTIVITY_KEY)) or now
        absolute_deadline = started_at + timedelta(seconds=settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS)
        idle_deadline = activity_at + timedelta(seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS)

        reason = None
        if now >= absolute_deadline:
            reason = SecurityAuditEvent.EventType.SESSION_ABSOLUTE_EXPIRED
        elif now >= idle_deadline:
            reason = SecurityAuditEvent.EventType.SESSION_IDLE_EXPIRED

        if reason:
            request._security_logout_reason = reason
            session_key = request.session.session_key
            if session_key:
                UserSession.objects.filter(session_key=session_key).delete()
            logout(request)
            messages.info(request, "Tu sesión expiró por seguridad. Inicia sesión nuevamente.")
            if request.path == reverse("accounts:session_keepalive"):
                return JsonResponse({"detail": "session_expired", "reason": reason}, status=401)
            if getattr(request, "htmx", False):
                response = HttpResponse()
                response["HX-Redirect"] = reverse("account_login")
                return response
            return redirect("account_login")

        is_keepalive = (
            request.method == "POST"
            and request.path == reverse("accounts:session_keepalive")
        )
        is_new_session = not request.session.get(self.ACTIVITY_KEY)
        stored_activity_at = activity_at
        candidate_activity_at = now if is_keepalive or is_new_session else activity_at
        candidate_idle_deadline = candidate_activity_at + timedelta(
            seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS
        )
        effective_deadline = min(candidate_idle_deadline, absolute_deadline)
        expiry_reason = (
            "absolute" if absolute_deadline <= candidate_idle_deadline else "idle"
        )

        request.session[self.STARTED_KEY] = started_at.isoformat()
        if is_new_session:
            request.session[self.ACTIVITY_KEY] = candidate_activity_at.isoformat()
        request.session.set_expiry(max(1, int((absolute_deadline - now).total_seconds())))
        request.session_expires_at = effective_deadline
        request.session_expiry_reason = expiry_reason
        request.session_warning_seconds = settings.SESSION_WARNING_SECONDS
        request.session_server_now = now

        response = self.get_response(request)

        if is_keepalive and 200 <= response.status_code < 300:
            request.session[self.ACTIVITY_KEY] = candidate_activity_at.isoformat()
            final_idle_deadline = candidate_idle_deadline
        elif is_new_session:
            final_idle_deadline = candidate_idle_deadline
        else:
            request.session[self.ACTIVITY_KEY] = stored_activity_at.isoformat()
            final_idle_deadline = stored_activity_at + timedelta(
                seconds=settings.SESSION_IDLE_TIMEOUT_SECONDS
            )

        effective_deadline = min(final_idle_deadline, absolute_deadline)
        expiry_reason = "absolute" if absolute_deadline <= final_idle_deadline else "idle"
        if request.user.is_authenticated:
            response["X-Session-Expires-At"] = effective_deadline.isoformat()
            response["X-Session-Expiry-Reason"] = expiry_reason
            response["X-Session-Server-Now"] = now.isoformat()
        return response

    @staticmethod
    def _read_timestamp(value):
        if not value:
            return None
        try:
            return timezone.datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
