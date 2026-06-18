# views.py — dashboard refactor reference

Target: `apps/accounts/views.py`, the dashboard view (`DashboardView` / its
`ERPBaseViewMixin` `get_context_data`) and its `_build_kpi_stats` staticmethod.

The redesign reuses the primitives the view **already computes** and adds three:
two open-invoice counts and the three previous-month flow figures (for deltas).
Then `_build_kpi_stats` is replaced by `_build_dashboard_context`, which emits
`flow_stats` + `worklist` lists (small structures, same pattern as before) plus
a handful of scalars the new partials read directly.

────────────────────────────────────────────────────────────────────────
## 1. Add primitives to the cached `computed` dict
────────────────────────────────────────────────────────────────────────

Alongside the existing aggregates (month_invoiced, outstanding, ap_outstanding,
net_position, overdue_total, overdue_count, month_purchased, …) add:

```python
from dateutil.relativedelta import relativedelta  # already used for chart_months

# ── Open-invoice counts (for the cash band sub-captions) ──
ar_open_count = SalesDocument.invoices.filter(
    organization=org, deleted_at__isnull=True,
    status__in=[SalesDocument.Status.SENT, SalesDocument.Status.OVERDUE],
).count()
ap_open_count = PurchaseDocument.supplier_invoices.filter(
    organization=org, deleted_at__isnull=True,
    status__in=[PurchaseDocument.Status.CONFIRMED],   # adjust to your "open" states
).count()

# ── Previous-month flow figures (for MoM deltas) ──
prev_start = month_start - relativedelta(months=1)
prev_end   = month_start          # exclusive upper bound

prev_invoiced = (SalesDocument.invoices.filter(
    organization=org, deleted_at__isnull=True,
    issue_date__gte=prev_start, issue_date__lt=prev_end,
    status__in=[SalesDocument.Status.SENT, SalesDocument.Status.PAID,
                SalesDocument.Status.OVERDUE],
).aggregate(t=Sum("total"))["t"] or _zero)

prev_collected = (Payment.objects.for_org(org)
    .filter(date__gte=prev_start, date__lt=prev_end)
    .aggregate(t=Sum("amount"))["t"] or _zero)

prev_purchased = (PurchaseDocument.supplier_invoices.filter(
    organization=org, deleted_at__isnull=True,
    issue_date__gte=prev_start, issue_date__lt=prev_end,
    status__in=[PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID],
).aggregate(t=Sum("total"))["t"] or _zero)
```

Add them to `computed = { … }` so they get cached as primitives:

```python
    "ar_open_count": ar_open_count,
    "ap_open_count": ap_open_count,
    "prev_invoiced": prev_invoiced,
    "prev_collected": prev_collected,
    "prev_purchased": prev_purchased,
```

> NOTE on model names: the snippet uses `SalesDocument.invoices` / `Payment` to
> mirror the existing purchases code in this file. Use whatever managers the
> sales side already uses for `month_invoiced` / `month_collected` — copy those
> exact querysets, just swap the date window.

────────────────────────────────────────────────────────────────────────
## 2. Replace `_build_kpi_stats` with `_build_dashboard_context`
────────────────────────────────────────────────────────────────────────

```python
@staticmethod
def _build_dashboard_context(ctx):
    """Package cached primitives into the 3-tier dashboard structures.
    Built per-request so the cache stores only primitives (no pickled
    translations / URLs)."""

    def money0(v):
        return "{:,.0f}".format(v or 0)

    def delta(curr, prev):
        """Return ('8.4%', up_bool) or (None, True) when prev is 0/None."""
        curr = curr or 0
        prev = prev or 0
        if not prev:
            return None, True
        pct = (curr - prev) / prev * 100
        return f"{abs(pct):.1f}%", pct >= 0

    has_purchasing = ctx.get("has_purchasing_access")

    # ── Tier 1 · cash band scalars (read directly by _cash_position.html) ──
    net = ctx.get("net_position") or 0
    npd, npd_up = delta(net, (ctx.get("month_collected") or 0))  # see note*
    # *If you track prior-month net, use it here. Otherwise drop the delta:
    ctx["net_position_delta"] = None        # or "9.2% vs. mayo" when available
    ctx["net_position_up"] = net >= 0
    # ar_outstanding / ap_outstanding / overdue_total / overdue_count /
    # ar_open_count / ap_open_count already in ctx from computed{}.
    ctx["ar_outstanding"] = ctx.get("outstanding")   # alias for the partial

    # ── Tier 2 · flow stats (only when the user has sales access) ──
    di, di_up = delta(ctx.get("month_invoiced"),  ctx.get("prev_invoiced"))
    dc, dc_up = delta(ctx.get("month_collected"), ctx.get("prev_collected"))
    flow = [
        {"label": _("Facturado"), "value": ctx.get("month_invoiced"),
         "delta": di, "delta_up": di_up,
         "foot": _("vs. RD$ %(p)s el mes pasado") % {"p": money0(ctx.get("prev_invoiced"))}},
        {"label": _("Cobrado"), "value": ctx.get("month_collected"),
         "delta": dc, "delta_up": dc_up,
         "foot": _("%(p)s%% de lo facturado") % {
             "p": int((ctx.get("month_collected") or 0) /
                      (ctx.get("month_invoiced") or 1) * 100)}},
    ]
    if has_purchasing:
        dp, dp_up = delta(ctx.get("month_purchased"), ctx.get("prev_purchased"))
        flow.append({"label": _("Comprado"), "value": ctx.get("month_purchased"),
                     "delta": dp, "delta_up": dp_up,
                     "foot": _("vs. RD$ %(p)s el mes pasado") % {"p": money0(ctx.get("prev_purchased"))}})
    ctx["flow_stats"] = flow

    # ── Tier 3 · worklist chips (demoted operational counts) ──
    work = [
        {"label": _("Cotizaciones activas"), "icon": "bi-file-earmark-text",
         "count": ctx.get("pending_quotations") or 0,
         "href": reverse("sales:quotation_list")},
        {"label": _("Órdenes de venta"), "icon": "bi-cart",
         "count": ctx.get("pending_sale_orders") or 0,
         "href": reverse("sales:sale_order_list")},
    ]
    if has_purchasing:
        work.append({"label": _("Órdenes de compra"), "icon": "bi-clipboard-check",
                     "count": ctx.get("pending_purchase_orders") or 0,
                     "href": reverse("purchases:po_list")})
        if ctx.get("ap_overdue"):
            work.append({"label": _("Vencido proveedores"), "icon": "bi-exclamation-triangle",
                         "count": "RD$" + money0(ctx.get("ap_overdue")),
                         "href": reverse("purchases:supplier_invoice_list"),
                         "risk": True})
    else:
        work.append({"label": _("Clientes"), "icon": "bi-people",
                     "count": ctx.get("customer_count") or 0,
                     "href": reverse("sales:customer_list")})
    ctx["worklist"] = work
```

Then swap the call at the end of `get_context_data`:

```python
-        self._build_kpi_stats(ctx)
+        self._build_dashboard_context(ctx)
```

`_build_kpi_stats` (the admin_stats / sales_stats / purchase_stats builder) can
be deleted once no other page depends on it. If list pages still call
`components/_kpi_cards.html`, keep that partial — it is untouched; only the
dashboard stops using it.
