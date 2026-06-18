from datetime import date

from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from apps.accounts.permissions import can_access_module
from apps.accounts.views import ERPBaseViewMixin

_MONTHS_ES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]


class ReportCenterView(ERPBaseViewMixin, TemplateView):
    """Unified report hub spanning Sales + Purchases.

    Access is granted to admins who can reach *either* the sales or the
    purchasing module; each report row is gated individually in the template
    via ``has_sales`` / ``has_purchasing``.
    """

    template_name = "core/reports.html"
    admin_required = True
    required_module = None  # custom dual-module check below

    def dispatch(self, request, *args, **kwargs):
        membership = getattr(request, "membership", None)
        if request.user.is_authenticated and membership:
            if not (
                can_access_module(membership, "sales")
                or can_access_module(membership, "purchasing")
            ):
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        membership = self.request.membership
        today = timezone.now().date()
        next_month = today.month % 12 + 1
        next_year = today.year + (1 if today.month == 12 else 0)

        ctx["today"] = today
        ctx["months"] = _MONTHS_ES
        ctx["dgii_deadline"] = date(next_year, next_month, 15)
        ctx["has_sales"] = can_access_module(membership, "sales")
        ctx["has_purchasing"] = can_access_module(membership, "purchasing")
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Centro de Reportes")},
        ]
        return ctx
