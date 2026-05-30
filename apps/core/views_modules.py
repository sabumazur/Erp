import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context
from .filters import ModuleFilter
from .forms import ModuleForm
from .models import Module


class ModuleStaffMixin(ERPBaseViewMixin):
    """Restrict to is_staff; skip org/permission checks from ERPBaseViewMixin."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            raise PermissionDenied
        # Skip ERPBaseViewMixin.dispatch — no org context needed
        return super(ERPBaseViewMixin, self).dispatch(request, *args, **kwargs)


# ── List + Create ─────────────────────────────────────────────────────────────

class ModuleListView(ModuleStaffMixin, DataTableMixin, TemplateView):
    template_name = "core/module_list.html"

    dt_columns = [
        DTColumn("slug",      _("Slug"),   sortable=True),
        DTColumn("name",      _("Nombre"), sortable=True),
        DTColumn("icon",      _("Ícono"),  sortable=False),
        DTColumn("is_active", _("Estado"), sortable=True),
    ]
    dt_default_sort = "name"
    dt_url = "core:module_list"
    dt_row_template = "core/partials/module_row.html"
    dt_filter_template = "core/partials/module_filters.html"
    dt_search_placeholder = _("Nombre o slug…")

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        f = ModuleFilter(request.GET, queryset=Module.objects.all())
        ctx = build_datatable_context(
            request, f.qs, cls.dt_columns,
            default_sort=cls.dt_default_sort,
            page_size=cls.dt_page_size,
            url=cls.dt_url,
            row_template=cls.dt_row_template,
            filter_template=cls.dt_filter_template,
        )
        ctx["filter"] = f
        resp = render(request, "components/datatable/results.html", ctx)
        resp["HX-Retarget"] = "#dt-results"
        resp["HX-Reswap"]   = "innerHTML"
        resp["HX-Trigger"]  = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        f = ModuleFilter(self.request.GET, queryset=Module.objects.all())
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"]      = f
        ctx["form"]        = ModuleForm()
        ctx["create_url"]  = reverse("core:module_list")
        ctx["submit_label"] = _("Crear")
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Módulos")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        form = ModuleForm(request.POST)
        if form.is_valid():
            form.save()
            if request.htmx:
                return ModuleListView.refresh_table(request, _("Módulo creado correctamente."))
            messages.success(request, _("Módulo creado correctamente."))
            return redirect("core:module_list")

        if request.htmx:
            resp = render(request, "core/partials/module_modal_form.html", {
                "form":         form,
                "action_url":   reverse("core:module_list"),
                "submit_label": _("Crear"),
            })
            resp["HX-Retarget"] = "#module-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


# ── Detail ────────────────────────────────────────────────────────────────────

class ModuleDetailView(ModuleStaffMixin, View):
    template_name = "core/module_detail.html"

    def get(self, request, pk):
        module = get_object_or_404(Module, pk=pk)
        return render(request, self.template_name, self.get_context(
            module=module,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Módulos"), "url": reverse("core:module_list")},
                {"label": module.name},
            ],
        ))


# ── Update ────────────────────────────────────────────────────────────────────

class ModuleUpdateView(ModuleStaffMixin, View):

    def get(self, request, pk):
        module = get_object_or_404(Module, pk=pk)
        form = ModuleForm(instance=module)

        if request.htmx:
            return render(request, "core/partials/module_modal_form.html", {
                "form":         form,
                "action_url":   reverse("core:module_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })

        return render(request, "core/module_form.html", self.get_context(
            form=form, module=module,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Módulos"), "url": reverse("core:module_list")},
                {"label": module.name, "url": reverse("core:module_detail", args=[module.pk])},
                {"label": _("Editar")},
            ],
        ))

    def post(self, request, pk):
        module = get_object_or_404(Module, pk=pk)
        form = ModuleForm(request.POST, instance=module)

        if form.is_valid():
            form.save()
            if request.htmx:
                return ModuleListView.refresh_table(request, _("Módulo actualizado correctamente."))
            messages.success(request, _("Módulo actualizado correctamente."))
            return redirect("core:module_detail", pk=module.pk)

        if request.htmx:
            resp = render(request, "core/partials/module_modal_form.html", {
                "form":         form,
                "action_url":   reverse("core:module_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })
            resp["HX-Retarget"] = "#module-modal-body"
            resp["HX-Reswap"]   = "innerHTML"
            return resp

        return render(request, "core/module_form.html", self.get_context(
            form=form, module=module,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Módulos"), "url": reverse("core:module_list")},
                {"label": module.name, "url": reverse("core:module_detail", args=[module.pk])},
                {"label": _("Editar")},
            ],
        ))


# ── Toggle ────────────────────────────────────────────────────────────────────

class ModuleToggleView(ModuleStaffMixin, View):

    def post(self, request, pk):
        module = get_object_or_404(Module, pk=pk)
        module.is_active = not module.is_active
        module.save(update_fields=["is_active"])
        state = _("activado") if module.is_active else _("desactivado")
        msg   = _(f"Módulo {state}.")

        if request.htmx:
            return ModuleListView.refresh_table(request, msg)

        messages.success(request, msg)
        return redirect("core:module_detail", pk=module.pk)


# ── Delete ────────────────────────────────────────────────────────────────────

class ModuleDeleteView(ModuleStaffMixin, View):

    def post(self, request, pk):
        module = get_object_or_404(Module, pk=pk)
        name = module.name
        try:
            module.delete()
        except ValidationError as exc:
            msg = exc.messages[0]
            if request.htmx:
                return ModuleListView.refresh_table(request, msg, "error")
            messages.error(request, msg)
            return redirect("core:module_list")

        if request.htmx:
            return ModuleListView.refresh_table(request, _(f"Módulo «{name}» eliminado."))
        messages.success(request, _(f"Módulo «{name}» eliminado."))
        return redirect("core:module_list")
