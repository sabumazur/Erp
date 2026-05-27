import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView, UpdateView

from .forms import ProfileForm, OrganizationForm, InvitationForm, TeamForm, StaffCreateOrganizationForm
from .models import Organization, Membership, Invitation, Team
from .permissions import revoke_org_permissions, can_access_module

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def send_invitation_email(invitation, request):
    accept_url = request.build_absolute_uri(
        reverse("accounts:accept_invitation", args=[invitation.pk])
    )
    subject = render_to_string(
        "account/email/invitation_subject.txt",
        {"organization": invitation.organization},
    ).strip()
    body = render_to_string(
        "account/email/invitation_message.txt",
        {"invitation": invitation, "accept_url": accept_url},
    )
    from_email = settings.DEFAULT_FROM_EMAIL or "noreply@sabsys.com"
    send_mail(subject, body, from_email, [invitation.email], fail_silently=False)


# ── Base mixin ────────────────────────────────────────────────────────────────

class ERPBaseViewMixin(LoginRequiredMixin):
    """
    Base mixin for every ERP view.

    Class attributes:
        required_permission — guardian codename scoped to request.organization
        admin_required      — True to restrict to Owner / Admin roles
        required_module     — module slug; raises 403 if team has no access
    """
    required_permission: str | None = None
    admin_required: bool = False
    required_module: str | None = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.admin_required:
            if not request.organization:
                raise PermissionDenied
            if not request.membership or not request.membership.is_admin:
                raise PermissionDenied

        if self.required_permission:
            if not request.organization:
                raise PermissionDenied
            if not request.user.has_perm(self.required_permission, request.organization):
                raise PermissionDenied

        if self.required_module:
            if not request.organization:
                raise PermissionDenied
            if not can_access_module(request.membership, self.required_module):
                raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["organization"] = self.request.organization
        ctx["membership"] = self.request.membership
        ctx["user_memberships"] = (
            self.request.user.memberships
            .select_related("organization")
            .order_by("created_at")
        )
        return ctx

    def get_context(self, **kwargs):
        """
        Helper for plain View subclasses that call render() directly and
        therefore bypass get_context_data().  Injects the same sidebar
        variables (organization, membership, user_memberships) so that
        {% if user.is_authenticated and organization %} in _sidebar.html
        always evaluates correctly.

        Usage:
            return render(request, self.template_name, self.get_context(item=item))
        """
        return {
            "organization": self.request.organization,
            "membership": self.request.membership,
            "user_memberships": (
                self.request.user.memberships
                .select_related("organization")
                .order_by("created_at")
            ),
            **kwargs,
        }


class SessionKeepaliveView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        return JsonResponse({
            "expires_at": request.session_expires_at.isoformat(),
            "expiry_reason": request.session_expiry_reason,
            "warning_seconds": settings.SESSION_WARNING_SECONDS,
            "server_now": request.session_server_now.isoformat(),
        })


# ── Dashboard & Profile ───────────────────────────────────────────────────────

class DashboardView(ERPBaseViewMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [{"label": _("Dashboard")}]
        ctx["today"] = timezone.localdate()

        org = self.request.organization
        ctx["has_sales_access"] = bool(
            org and can_access_module(self.request.membership, "sales")
        )
        if not org or not ctx["has_sales_access"]:
            return ctx

        from apps.sales.models import SalesDocument, Customer, Payment

        today = ctx["today"]
        _zero = Decimal("0")

        _inv = SalesDocument.invoices.filter(organization=org, deleted_at__isnull=True).with_signed_totals()

        # ── Tables (always fresh — simple selects, limit 6-8) ─────────────────

        ctx["recent_invoices"] = (
            _inv.exclude(status=SalesDocument.Status.DRAFT)
            .select_related("customer")
            .order_by("-issue_date")[:8]
        )

        ctx["overdue_invoices"] = (
            _inv.filter(status=SalesDocument.Status.OVERDUE)
            .select_related("customer")
            .order_by("due_date")[:6]
        )

        ctx["recent_payments"] = (
            Payment.objects.for_org(org)
            .select_related("customer")
            .order_by("-date")[:6]
        )

        # ── KPIs + charts (cached 15 min, invalidated by save/delete signals) ──

        _cache_key = f"dashboard:{org.pk}"
        cached = cache.get(_cache_key)
        if cached is not None:
            ctx.update(cached)
            return ctx

        month_start = today.replace(day=1)
        _quot = SalesDocument.quotations.filter(organization=org, deleted_at__isnull=True)
        _so = SalesDocument.sale_orders.filter(organization=org, deleted_at__isnull=True)

        month_invoiced = (
            _inv.filter(
                issue_date__gte=month_start,
                status__in=[
                    SalesDocument.Status.CONFIRMED,
                    SalesDocument.Status.SENT,
                    SalesDocument.Status.PAID,
                    SalesDocument.Status.OVERDUE,
                ],
            )
            .aggregate(t=Sum("signed_total"))["t"] or _zero
        )

        month_collected = (
            Payment.objects.for_org(org)
            .filter(date__gte=month_start)
            .aggregate(t=Sum("amount"))["t"] or _zero
        )

        outstanding = (
            _inv.filter(
                status__in=[
                    SalesDocument.Status.CONFIRMED,
                    SalesDocument.Status.SENT,
                    SalesDocument.Status.OVERDUE,
                ],
            )
            .aggregate(t=Sum("signed_total"))["t"] or _zero
        )

        overdue_total = (
            _inv.filter(status=SalesDocument.Status.OVERDUE)
            .aggregate(t=Sum("signed_total"))["t"] or _zero
        )

        customer_count = Customer.objects.for_org(org).count()

        pending_quotations = _quot.filter(
            status__in=[SalesDocument.Status.CONFIRMED, SalesDocument.Status.SENT],
        ).count()

        pending_sale_orders = _so.filter(
            status__in=[SalesDocument.Status.CONFIRMED, SalesDocument.Status.DELIVERED],
        ).count()

        overdue_count = _inv.filter(status=SalesDocument.Status.OVERDUE).count()

        # Charts

        from django.db.models.functions import TruncMonth

        _MONTH_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                     "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

        months_list = []
        y, mo = today.year, today.month
        for i in range(5, -1, -1):
            m_off = mo - i
            y_off = y
            while m_off <= 0:
                m_off += 12
                y_off -= 1
            months_list.append(date(y_off, m_off, 1))

        six_months_ago = months_list[0]

        inv_by_month = {
            row["month"]: float(row["total"])
            for row in _inv.filter(
                issue_date__gte=six_months_ago,
                status__in=[
                    SalesDocument.Status.CONFIRMED,
                    SalesDocument.Status.SENT,
                    SalesDocument.Status.PAID,
                    SalesDocument.Status.OVERDUE,
                ],
            )
            .annotate(month=TruncMonth("issue_date"))
            .values("month")
            .annotate(total=Sum("signed_total"))
        }

        pay_by_month = {
            row["month"]: float(row["total"])
            for row in Payment.objects.for_org(org)
            .filter(date__gte=six_months_ago)
            .annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
        }

        chart_months = [f"{_MONTH_ES[m.month - 1]} {m.year}" for m in months_list]
        chart_invoiced = [inv_by_month.get(m, 0.0) for m in months_list]
        chart_collected = [pay_by_month.get(m, 0.0) for m in months_list]

        _STATUS_LABELS = {
            SalesDocument.Status.CONFIRMED: "Confirmada",
            SalesDocument.Status.SENT: "Enviada",
            SalesDocument.Status.PAID: "Pagada",
            SalesDocument.Status.OVERDUE: "Vencida",
            SalesDocument.Status.DRAFT: "Borrador",
        }
        _STATUS_COLORS = {
            SalesDocument.Status.CONFIRMED: "#0d6efd",
            SalesDocument.Status.SENT: "#0dcaf0",
            SalesDocument.Status.PAID: "#198754",
            SalesDocument.Status.OVERDUE: "#dc3545",
            SalesDocument.Status.DRAFT: "#adb5bd",
        }

        status_counts_qs = {
            row["status"]: row["count"]
            for row in _inv.values("status").annotate(count=Count("id"))
        }
        ordered_statuses = [s for s in _STATUS_LABELS if status_counts_qs.get(s, 0) > 0]

        chart_status_labels = [_STATUS_LABELS[s] for s in ordered_statuses]
        chart_status_counts = [status_counts_qs[s] for s in ordered_statuses]
        chart_status_colors = [_STATUS_COLORS[s] for s in ordered_statuses]

        _CUSTOMER_COLORS = [
            "rgba(13,110,253,0.8)",
            "rgba(25,135,84,0.8)",
            "rgba(255,193,7,0.8)",
            "rgba(220,53,69,0.8)",
            "rgba(13,202,240,0.8)",
            "rgba(111,66,193,0.8)",
        ]

        _inv_status_filter = [
            SalesDocument.Status.CONFIRMED,
            SalesDocument.Status.SENT,
            SalesDocument.Status.PAID,
            SalesDocument.Status.OVERDUE,
        ]

        top_customers = list(
            _inv.filter(issue_date__gte=six_months_ago, status__in=_inv_status_filter)
            .values("customer__id", "customer__name")
            .annotate(total=Sum("signed_total"))
            .order_by("-total")[:6]
        )

        if top_customers:
            top_ids = [c["customer__id"] for c in top_customers]

            cust_monthly = (
                _inv.filter(
                    issue_date__gte=six_months_ago,
                    status__in=_inv_status_filter,
                    customer__id__in=top_ids,
                )
                .annotate(month=TruncMonth("issue_date"))
                .values("customer__id", "month")
                .annotate(total=Sum("signed_total"))
            )

            cust_data = {cid: {} for cid in top_ids}
            for row in cust_monthly:
                cust_data[row["customer__id"]][row["month"]] = float(row["total"])

            chart_customer_datasets = [
                {
                    "label": c["customer__name"],
                    "data": [cust_data[c["customer__id"]].get(m, 0.0) for m in months_list],
                    "backgroundColor": _CUSTOMER_COLORS[i % len(_CUSTOMER_COLORS)],
                    "borderRadius": 3,
                }
                for i, c in enumerate(top_customers)
            ]
        else:
            chart_customer_datasets = []

        computed = {
            "month_invoiced": month_invoiced,
            "month_collected": month_collected,
            "outstanding": outstanding,
            "overdue_total": overdue_total,
            "customer_count": customer_count,
            "pending_quotations": pending_quotations,
            "pending_sale_orders": pending_sale_orders,
            "overdue_count": overdue_count,
            "chart_months": chart_months,
            "chart_invoiced": chart_invoiced,
            "chart_collected": chart_collected,
            "chart_status_labels": chart_status_labels,
            "chart_status_counts": chart_status_counts,
            "chart_status_colors": chart_status_colors,
            "chart_customer_datasets": chart_customer_datasets,
        }
        cache.set(_cache_key, computed, timeout=900)
        ctx.update(computed)
        return ctx


class ProfileView(ERPBaseViewMixin, UpdateView):
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Mi perfil")},
        ]
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Perfil actualizado.")
        return super().form_valid(form)


class SwitchOrganizationView(LoginRequiredMixin, TemplateView):
    def post(self, request, slug):
        membership = (
            Membership.objects
            .select_related("organization")
            .filter(
                user=request.user,
                organization__slug=slug,
                organization__is_active=True,
                organization__deleted_at__isnull=True,
            )
            .first()
        )
        if membership:
            request.session["active_org_slug"] = membership.organization.slug
        referer = request.META.get("HTTP_REFERER", "")
        if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
            return redirect(referer)
        return redirect("accounts:dashboard")


# ── Organization settings ─────────────────────────────────────────────────────

class OrganizationSettingsView(ERPBaseViewMixin, UpdateView):
    form_class = OrganizationForm
    template_name = "accounts/org_settings.html"
    success_url = reverse_lazy("accounts:org_settings")
    admin_required = True

    def get_object(self):
        return self.request.organization

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        logo_url = ""
        if self.object and self.object.logo:
            try:
                if self.object.logo.storage.exists(self.object.logo.name):
                    logo_url = self.object.logo.url
            except OSError:
                logo_url = ""
        ctx["organization_logo_url"] = logo_url
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Organización")},
            {"label": _("Configuración")},
        ]
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Configuración de organización guardada.")
        return super().form_valid(form)


# ── Member management ─────────────────────────────────────────────────────────

class MemberListView(ERPBaseViewMixin, TemplateView):
    template_name = "accounts/members.html"
    admin_required = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Organización")},
            {"label": _("Miembros")},
        ]
        ctx["members"] = (
            Membership.objects
            .filter(organization=self.request.organization)
            .select_related("user", "team")
            .order_by("created_at")
        )
        ctx["pending_invitations"] = (
            Invitation.objects
            .filter(
                organization=self.request.organization,
                accepted_at__isnull=True,
            )
            .order_by("-created_at")
        )
        ctx["roles"] = Membership.Role.choices
        ctx["invite_form"] = InvitationForm()
        ctx["teams"] = Team.objects.filter(organization=self.request.organization)
        return ctx


class ChangeMemberRoleView(ERPBaseViewMixin, View):
    admin_required = True

    def post(self, request, pk):
        new_role = request.POST.get("role")
        if new_role not in dict(Membership.Role.choices):
            messages.error(request, "Rol inválido.")
            return redirect("accounts:members")

        with transaction.atomic():
            locked = Membership.objects.select_for_update()
            actor = get_object_or_404(locked, pk=request.membership.pk)
            membership = get_object_or_404(
                locked, pk=pk, organization=request.organization
            )
            if membership.user == request.user:
                messages.error(request, "No puedes cambiar tu propio rol.")
                return redirect("accounts:members")

            if membership.role == Membership.Role.OWNER and actor.role != Membership.Role.OWNER:
                raise PermissionDenied
            if new_role in (Membership.Role.OWNER, Membership.Role.ADMIN) and actor.role != Membership.Role.OWNER:
                raise PermissionDenied
            if membership.role == Membership.Role.OWNER and new_role != Membership.Role.OWNER:
                owner_ids = list(locked.filter(
                    organization=request.organization,
                    role=Membership.Role.OWNER,
                ).values_list("pk", flat=True))
                if len(owner_ids) <= 1:
                    messages.error(request, "No se puede cambiar al último propietario.")
                    return redirect("accounts:members")

            membership.role = new_role
            membership.save(update_fields=["role", "updated_at"])
        messages.success(request, f"El rol de {membership.user.full_name} ha sido actualizado a {membership.get_role_display()}.")
        return redirect("accounts:members")


class RemoveMemberView(ERPBaseViewMixin, View):
    admin_required = True

    def post(self, request, pk):
        with transaction.atomic():
            locked = Membership.objects.select_for_update()
            actor = get_object_or_404(locked, pk=request.membership.pk)
            membership = get_object_or_404(
                locked, pk=pk, organization=request.organization
            )
            if membership.user == request.user:
                messages.error(request, "No puedes eliminarte a ti mismo.")
                return redirect("accounts:members")

            if membership.role == Membership.Role.OWNER:
                if actor.role != Membership.Role.OWNER:
                    raise PermissionDenied
                owner_ids = list(locked.filter(
                    organization=request.organization,
                    role=Membership.Role.OWNER,
                ).values_list("pk", flat=True))
                if len(owner_ids) <= 1:
                    messages.error(request, "No se puede eliminar al último propietario.")
                    return redirect("accounts:members")

            revoke_org_permissions(membership)
            membership.delete()
        messages.success(request, f"{membership.user.full_name} ha sido eliminado.")
        return redirect("accounts:members")


# ── Invitations ───────────────────────────────────────────────────────────────

class InviteMemberView(ERPBaseViewMixin, View):
    admin_required = True

    def post(self, request):
        form = InvitationForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Por favor ingresa un correo electrónico válido.")
            return redirect("accounts:members")

        email = form.cleaned_data["email"]
        role = form.cleaned_data["role"]

        # Only OWNERs may invite at OWNER or ADMIN level.
        if role in (Membership.Role.OWNER, Membership.Role.ADMIN) and request.membership.role != Membership.Role.OWNER:
            raise PermissionDenied

        if Membership.objects.filter(
            user__email__iexact=email,
            organization=request.organization,
        ).exists():
            messages.error(request, f"{email} ya es miembro de esta organización.")
            return redirect("accounts:members")

        if Invitation.objects.filter(
            email__iexact=email,
            organization=request.organization,
            accepted_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            messages.warning(request, f"Ya existe una invitación pendiente para {email}.")
            return redirect("accounts:members")

        try:
            with transaction.atomic():
                invitation = Invitation.create_for(
                    email=email,
                    organization=request.organization,
                    role=role,
                    invited_by=request.user,
                )
        except IntegrityError:
            # Concurrent request already created a pending invitation.
            messages.warning(request, f"Ya existe una invitación pendiente para {email}.")
            return redirect("accounts:members")
        send_invitation_email(invitation, request)
        messages.success(request, f"Invitación enviada a {email}.")
        return redirect("accounts:members")


class ResendInvitationView(ERPBaseViewMixin, View):
    admin_required = True

    def post(self, request, pk):
        invitation = get_object_or_404(
            Invitation, pk=pk, organization=request.organization, accepted_at__isnull=True
        )
        invitation.expires_at = timezone.now() + timedelta(days=7)
        invitation.save(update_fields=["expires_at"])
        send_invitation_email(invitation, request)
        messages.success(request, f"Invitación reenviada a {invitation.email}.")
        return redirect("accounts:members")


class CancelInvitationView(ERPBaseViewMixin, View):
    admin_required = True

    def post(self, request, pk):
        invitation = get_object_or_404(
            Invitation, pk=pk, organization=request.organization, accepted_at__isnull=True
        )
        email = invitation.email
        invitation.delete()
        messages.success(request, f"Invitación para {email} cancelada.")
        return redirect("accounts:members")


class AcceptInvitationView(View):

    def get(self, request, pk):
        invitation = get_object_or_404(Invitation, pk=pk)

        if invitation.accepted_at:
            if request.user.is_authenticated and Membership.objects.filter(
                user=request.user, organization=invitation.organization
            ).exists():
                request.session["active_org_slug"] = invitation.organization.slug
                return redirect("accounts:dashboard")
            return render(request, "accounts/accept_invitation.html", {
                "status": "already_accepted", "invitation": invitation,
            })

        if invitation.is_expired:
            return render(request, "accounts/accept_invitation.html", {
                "status": "expired", "invitation": invitation,
            })

        if not request.user.is_authenticated:
            return render(request, "accounts/accept_invitation.html", {
                "status": "login_required",
                "invitation": invitation,
                "login_url": reverse("account_login") + f"?next={request.path}",
                "signup_url": reverse("account_signup"),
            })

        if request.user.email.lower() != invitation.email.lower():
            return render(request, "accounts/accept_invitation.html", {
                "status": "wrong_email",
                "invitation": invitation,
            })

        self._accept(request, invitation)
        messages.success(request, f"¡Te has unido a {invitation.organization.name}!")
        return redirect("accounts:dashboard")

    def _accept(self, request, invitation):
        with transaction.atomic():
            Membership.objects.get_or_create(
                user=request.user,
                organization=invitation.organization,
                defaults={"role": invitation.role},
            )
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["accepted_at"])
        request.session["active_org_slug"] = invitation.organization.slug


# ── Teams ─────────────────────────────────────────────────────────────────────

class TeamListView(ERPBaseViewMixin, TemplateView):
    template_name = "accounts/teams.html"
    admin_required = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Organización")},
            {"label": _("Equipos")},
        ]
        ctx["teams"] = (
            Team.objects
            .filter(organization=self.request.organization)
            .prefetch_related("memberships__user")
        )
        ctx["form"] = TeamForm()
        return ctx

    def post(self, request):
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save(commit=False)
            team.organization = request.organization
            team.save()
            form.save_m2m()
            messages.success(request, f"Equipo \"{team.name}\" creado.")
        else:
            messages.error(request, "Por favor corrige los errores indicados.")
        return redirect("accounts:teams")


class TeamUpdateView(ERPBaseViewMixin, UpdateView):
    form_class = TeamForm
    template_name = "accounts/team_form.html"
    admin_required = True
    success_url = reverse_lazy("accounts:teams")

    def get_object(self):
        return get_object_or_404(
            Team, pk=self.kwargs["pk"], organization=self.request.organization
        )

    def get_context_data(self, **kwargs):
        from apps.core.models import Module
        ctx = super().get_context_data(**kwargs)
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Organización")},
            {"label": _("Equipos"), "url": reverse("accounts:teams")},
            {"label": self.object.name},
        ]
        ctx["all_modules"] = Module.objects.filter(is_active=True)
        ctx["selected_module_pks"] = set(
            str(pk) for pk in self.object.modules.values_list("pk", flat=True)
        )
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Equipo actualizado.")
        return super().form_valid(form)


class TeamDeleteView(ERPBaseViewMixin, View):
    admin_required = True

    def post(self, request, pk):
        team = get_object_or_404(Team, pk=pk, organization=request.organization)
        name = team.name
        try:
            team.delete()
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("accounts:teams")
        messages.success(request, f"Equipo \"{name}\" eliminado.")
        return redirect("accounts:teams")


class AssignMemberTeamView(ERPBaseViewMixin, View):
    admin_required = True

    def post(self, request, pk):
        membership = get_object_or_404(
            Membership, pk=pk, organization=request.organization
        )
        team_id = request.POST.get("team")
        if team_id:
            membership.team = get_object_or_404(
                Team, pk=team_id, organization=request.organization
            )
        else:
            membership.team = None
        membership.save(update_fields=["team", "updated_at"])
        return redirect("accounts:members")


# ── Multi-org ─────────────────────────────────────────────────────────────────

class CreateOrganizationView(ERPBaseViewMixin, TemplateView):
    template_name = "accounts/create_org.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            messages.error(request, _("No tienes permiso para crear organizaciones."))
            return redirect("accounts:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form", StaffCreateOrganizationForm())
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Plataforma")},
            {"label": _("Nueva organización")},
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        form = StaffCreateOrganizationForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        owner_email = form.cleaned_data["owner_email"]
        name = form.cleaned_data["name"]
        base_slug = slugify(name) or "org"

        with transaction.atomic():
            slug = base_slug
            counter = 1
            while Organization.all_objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            org = form.save(commit=False)
            org.slug = slug
            org.owner = request.user  # technical creator; FK is informational
            try:
                with transaction.atomic():
                    org.save()
            except IntegrityError:
                # Concurrent request claimed this slug between our check and save.
                org.slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
                org.save()
            invitation = Invitation.create_for(
                email=owner_email,
                organization=org,
                role=Membership.Role.OWNER,
                invited_by=request.user,
            )

        try:
            send_invitation_email(invitation, request)
        except Exception:
            logger.exception("Failed to send invitation email for org %s to %s", org.pk, owner_email)
            messages.warning(
                request,
                _('Organización "%(name)s" creada. No se pudo enviar la invitación a %(email)s.') % {
                    "name": org.name,
                    "email": owner_email,
                },
            )
        else:
            messages.success(
                request,
                _('Organización "%(name)s" creada. Invitación enviada a %(email)s.') % {
                    "name": org.name,
                    "email": owner_email,
                },
            )
        return redirect("accounts:dashboard")


class LeaveOrganizationView(LoginRequiredMixin, View):

    def post(self, request):
        org = request.organization

        if not org or not request.membership:
            return redirect("accounts:dashboard")

        with transaction.atomic():
            locked = Membership.objects.select_for_update()
            membership = get_object_or_404(locked, pk=request.membership.pk)

            # Must transfer ownership before leaving if sole owner.
            if membership.role == Membership.Role.OWNER:
                owner_ids = list(locked.filter(
                    organization=org,
                    role=Membership.Role.OWNER,
                ).values_list("pk", flat=True))
                if len(owner_ids) <= 1:
                    messages.error(
                        request,
                        "Eres el único propietario de esta organización. "
                        "Transfiere la propiedad a otro miembro antes de salir.",
                    )
                    return redirect("accounts:members")

            # Must keep at least one organization.
            remaining_count = request.user.memberships.exclude(organization=org).count()
            if remaining_count == 0:
                messages.error(request, "No puedes abandonar tu única organización.")
                return redirect("accounts:dashboard")

            org_name = org.name
            revoke_org_permissions(membership)
            membership.delete()

        next_membership = (
            request.user.memberships
            .select_related("organization")
            .order_by("created_at")
            .first()
        )
        if next_membership:
            request.session["active_org_slug"] = next_membership.organization.slug
        else:
            request.session.pop("active_org_slug", None)

        messages.success(request, f'Has abandonado "{org_name}".')
        return redirect("accounts:dashboard")
