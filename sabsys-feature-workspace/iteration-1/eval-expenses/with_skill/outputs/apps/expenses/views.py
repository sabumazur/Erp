import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.views import ERPBaseViewMixin
from apps.core.datatable import DTColumn, DataTableMixin, build_datatable_context

from .filters import ExpenseCategoryFilter, ExpenseFilter
from .forms import ExpenseCategoryForm, ExpenseForm
from .models import Expense, ExpenseCategory


def _org(request):
    return request.organization


# ── Expense Category ──────────────────────────────────────────────────────────

class ExpenseCategoryListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "expenses/expensecategory_list.html"
    required_module = "expenses"
    admin_required = True

    dt_columns = [
        DTColumn("name", _("Nombre"), sortable=True),
    ]
    dt_default_sort = "name"
    dt_page_size = 25
    dt_url = "expenses:category_list"
    dt_row_template = "expenses/partials/expensecategory_row.html"
    dt_filter_template = "expenses/partials/expensecategory_filters.html"
    dt_search_placeholder = _("Buscar categorías…")
    dt_id = "expenses_categories"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        qs = ExpenseCategory.objects.for_org(_org(request))
        f = ExpenseCategoryFilter(request.GET, queryset=qs)
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
        resp["HX-Reswap"] = "innerHTML"
        resp["HX-Trigger"] = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = ExpenseCategory.objects.for_org(_org(self.request))
        f = ExpenseCategoryFilter(self.request.GET, queryset=qs)
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"] = f
        ctx["form"] = ExpenseCategoryForm()
        ctx["create_url"] = reverse("expenses:category_list")
        ctx["submit_label"] = _("Crear")
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Categorías de gasto")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.organization = _org(request)
            category.save()
            if request.htmx:
                return ExpenseCategoryListView.refresh_table(
                    request, _("Categoría creada correctamente.")
                )
            messages.success(request, _("Categoría creada correctamente."))
            return redirect("expenses:category_list")

        if request.htmx:
            resp = render(request, "expenses/partials/expensecategory_modal_form.html", {
                "form": form,
                "action_url": reverse("expenses:category_list"),
                "submit_label": _("Crear"),
            })
            resp["HX-Retarget"] = "#expensecategory-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class ExpenseCategoryUpdateView(ERPBaseViewMixin, View):
    required_module = "expenses"
    admin_required = True

    def get(self, request, pk):
        category = get_object_or_404(ExpenseCategory, pk=pk, organization=_org(request))
        form = ExpenseCategoryForm(instance=category)

        if request.htmx:
            return render(request, "expenses/partials/expensecategory_modal_form.html", {
                "form": form,
                "action_url": reverse("expenses:category_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })

        ctx = self.get_context(
            form=form, category=category,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Categorías de gasto"), "url": reverse("expenses:category_list")},
                {"label": category.name},
            ],
        )
        return render(request, "expenses/expensecategory_form.html", ctx)

    def post(self, request, pk):
        category = get_object_or_404(ExpenseCategory, pk=pk, organization=_org(request))
        form = ExpenseCategoryForm(request.POST, instance=category)

        if form.is_valid():
            form.save()
            if request.htmx:
                return ExpenseCategoryListView.refresh_table(
                    request, _("Categoría actualizada correctamente.")
                )
            messages.success(request, _("Categoría actualizada correctamente."))
            return redirect("expenses:category_list")

        if request.htmx:
            resp = render(request, "expenses/partials/expensecategory_modal_form.html", {
                "form": form,
                "action_url": reverse("expenses:category_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })
            resp["HX-Retarget"] = "#expensecategory-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        ctx = self.get_context(
            form=form, category=category,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Categorías de gasto"), "url": reverse("expenses:category_list")},
                {"label": category.name},
            ],
        )
        return render(request, "expenses/expensecategory_form.html", ctx)


class ExpenseCategoryDeleteView(ERPBaseViewMixin, View):
    required_module = "expenses"
    admin_required = True

    def post(self, request, pk):
        category = get_object_or_404(ExpenseCategory, pk=pk, organization=_org(request))
        name = category.name

        if category.expenses.exists():
            msg = _(f"No se puede eliminar «{name}»: tiene gastos asociados.")
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"] = "none"
                resp["HX-Trigger"] = json.dumps({"showSwal": {
                    "icon": "error",
                    "title": str(_("No se puede eliminar")),
                    "text": str(msg),
                }})
                return resp
            messages.error(request, str(msg))
            return redirect("expenses:category_list")

        category.delete()
        if request.htmx:
            return ExpenseCategoryListView.refresh_table(
                request, _(f"Categoría «{name}» eliminada.")
            )
        messages.success(request, _(f"Categoría «{name}» eliminada."))
        return redirect("expenses:category_list")


# ── Expense ───────────────────────────────────────────────────────────────────

class ExpenseListView(ERPBaseViewMixin, DataTableMixin, TemplateView):
    template_name = "expenses/expense_list.html"
    required_module = "expenses"

    dt_columns = [
        DTColumn("date", _("Fecha"), sortable=True),
        DTColumn("category", _("Categoría"), sortable=True),
        DTColumn("amount", _("Monto"), sortable=True, numeric=True),
        DTColumn("status", _("Estado"), sortable=True),
        DTColumn("description", _("Descripción"), sortable=False),
    ]
    dt_default_sort = "-date"
    dt_page_size = 25
    dt_url = "expenses:expense_list"
    dt_row_template = "expenses/partials/expense_row.html"
    dt_filter_template = "expenses/partials/expense_filters.html"
    dt_search_placeholder = _("Buscar gastos…")
    dt_id = "expenses_list"

    @classmethod
    def refresh_table(cls, request, msg, msg_type="success"):
        qs = Expense.objects.for_org(_org(request)).select_related("category", "approved_by")
        f = ExpenseFilter(request.GET, queryset=qs)
        f.filters["category"].queryset = ExpenseCategory.objects.for_org(_org(request))
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
        resp["HX-Reswap"] = "innerHTML"
        resp["HX-Trigger"] = json.dumps(
            {"showToast": {"message": str(msg), "type": msg_type}}
        )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Expense.objects.for_org(_org(self.request)).select_related("category", "approved_by")
        f = ExpenseFilter(self.request.GET, queryset=qs)
        f.filters["category"].queryset = ExpenseCategory.objects.for_org(_org(self.request))
        ctx.update(self.apply_datatable(f.qs))
        ctx["filter"] = f
        ctx["form"] = ExpenseForm(organization=_org(self.request))
        ctx["create_url"] = reverse("expenses:expense_list")
        ctx["submit_label"] = _("Crear")
        ctx["breadcrumbs"] = [
            {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
            {"label": _("Gastos")},
        ]
        return ctx

    def get(self, request, *args, **kwargs):
        ctx = self.get_context_data(**kwargs)
        if request.htmx:
            return render(request, "components/datatable/results.html", ctx)
        return self.render_to_response(ctx)

    def post(self, request):
        form = ExpenseForm(request.POST, organization=_org(request))
        if form.is_valid():
            expense = form.save(commit=False)
            expense.organization = _org(request)
            expense.save()
            if request.htmx:
                return ExpenseListView.refresh_table(
                    request, _("Gasto creado correctamente.")
                )
            messages.success(request, _("Gasto creado correctamente."))
            return redirect("expenses:expense_list")

        if request.htmx:
            resp = render(request, "expenses/partials/expense_modal_form.html", {
                "form": form,
                "action_url": reverse("expenses:expense_list"),
                "submit_label": _("Crear"),
            })
            resp["HX-Retarget"] = "#expense-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        ctx = self.get_context_data()
        ctx["form"] = form
        return self.render_to_response(ctx)


class ExpenseUpdateView(ERPBaseViewMixin, View):
    required_module = "expenses"
    admin_required = True

    def get(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk, organization=_org(request))
        form = ExpenseForm(instance=expense, organization=_org(request))

        if request.htmx:
            return render(request, "expenses/partials/expense_modal_form.html", {
                "form": form,
                "action_url": reverse("expenses:expense_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })

        ctx = self.get_context(
            form=form, expense=expense,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Gastos"), "url": reverse("expenses:expense_list")},
                {"label": str(expense)},
                {"label": _("Editar")},
            ],
        )
        return render(request, "expenses/expense_form.html", ctx)

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk, organization=_org(request))
        form = ExpenseForm(request.POST, instance=expense, organization=_org(request))

        if form.is_valid():
            form.save()
            if request.htmx:
                return ExpenseListView.refresh_table(
                    request, _("Gasto actualizado correctamente.")
                )
            messages.success(request, _("Gasto actualizado correctamente."))
            return redirect("expenses:expense_list")

        if request.htmx:
            resp = render(request, "expenses/partials/expense_modal_form.html", {
                "form": form,
                "action_url": reverse("expenses:expense_edit", args=[pk]),
                "submit_label": _("Guardar"),
            })
            resp["HX-Retarget"] = "#expense-modal-body"
            resp["HX-Reswap"] = "innerHTML"
            return resp

        ctx = self.get_context(
            form=form, expense=expense,
            breadcrumbs=[
                {"label": _("Dashboard"), "url": reverse("accounts:dashboard")},
                {"label": _("Gastos"), "url": reverse("expenses:expense_list")},
                {"label": str(expense)},
                {"label": _("Editar")},
            ],
        )
        return render(request, "expenses/expense_form.html", ctx)


class ExpenseDeleteView(ERPBaseViewMixin, View):
    required_module = "expenses"
    admin_required = True

    def post(self, request, pk):
        expense = get_object_or_404(Expense, pk=pk, organization=_org(request))
        name = str(expense)

        if expense.status == Expense.Status.APPROVED:
            msg = _("No se puede eliminar un gasto aprobado.")
            if request.htmx:
                resp = HttpResponse()
                resp["HX-Reswap"] = "none"
                resp["HX-Trigger"] = json.dumps({"showSwal": {
                    "icon": "error",
                    "title": str(_("No se puede eliminar")),
                    "text": str(msg),
                }})
                return resp
            messages.error(request, str(msg))
            return redirect("expenses:expense_list")

        expense.delete()
        if request.htmx:
            return ExpenseListView.refresh_table(
                request, _(f"Gasto eliminado.")
            )
        messages.success(request, _("Gasto eliminado."))
        return redirect("expenses:expense_list")
