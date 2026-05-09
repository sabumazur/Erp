from dataclasses import dataclass

from django.core.paginator import Paginator


@dataclass
class DTColumn:
    """
    Column definition for DataTableMixin.

    key       – model field name used for ORDER BY and data-col CSS targeting.
    label     – display text in <th>.
    sortable  – whether the user can click the column header to sort.
    visible   – initial client-side visibility (toggleable via Alpine dropdown).
    numeric   – right-aligns the header and cells (add text-end class).
    """

    key: str
    label: str
    sortable: bool = True
    visible: bool = True
    numeric: bool = False
    classes: str = ""


# ── Internal helpers ───────────────────────────────────────────────────────────


def _resolve_sort(request, columns, default_sort):
    """Return (sort_expr, is_explicit).  Validates against allowed column keys."""
    raw = request.GET.get("sort", "").strip()
    explicit = bool(raw)
    if raw:
        key = raw.lstrip("-")
        allowed = {c.key for c in columns if c.sortable}
        if key not in allowed:
            raw = default_sort
            explicit = False
    else:
        raw = default_sort
    return raw, explicit


def _page_range(page_obj):
    """
    Compact page range with ellipsis markers (None = draw "…").

    Always includes first, last, and a window of ±2 around the current page.
    Returns a list of ints and Nones.
    """
    num = page_obj.paginator.num_pages
    if num <= 9:
        return list(range(1, num + 1))

    current = page_obj.number
    pages = {1, num} | set(range(max(1, current - 2), min(num + 1, current + 3)))

    result = []
    prev = None
    for n in sorted(pages):
        if prev is not None and n > prev + 1:
            result.append(None)
        result.append(n)
        prev = n
    return result


# ── Public API ─────────────────────────────────────────────────────────────────


def build_datatable_context(
    request,
    qs,
    columns,
    *,
    default_sort="",
    page_size=25,
    url="",
    row_template="",
    filter_template="",
    search_placeholder="Buscar…",
    dt_id="main",
):
    """
    Standalone function that applies sort + pagination to *qs* and returns
    the context dict expected by the datatable templates.

    Used by both DataTableMixin.apply_datatable() and action-view helpers
    that need to refresh the table after a CRUD operation.
    """
    sort, explicit_sort = _resolve_sort(request, columns, default_sort)
    q = request.GET.get("q", "").strip()

    # When FTS is active and no explicit sort was requested, preserve the
    # search-rank ordering that fts_search already applied.
    if sort and (explicit_sort or not q):
        qs = qs.order_by(sort)

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    skip = {"q", "page", "sort", "csrfmiddlewaretoken"}
    active_filter_count = sum(
        1 for k, v in request.GET.items() if k not in skip and v.strip()
    )

    return {
        "dt_columns": columns,
        "dt_sort": sort if (explicit_sort or not q) else "",
        "dt_page_obj": page_obj,
        "dt_total": paginator.count,
        "dt_page_range": _page_range(page_obj),
        "dt_url": url,
        "dt_row_template": row_template,
        "dt_filter_template": filter_template,
        "dt_search_placeholder": search_placeholder,
        "dt_id": dt_id,
        "dt_q": q,
        "active_filter_count": active_filter_count,
    }


class DataTableMixin:
    """
    View mixin that adds sort + pagination to list views.

    Set on the view class
    ─────────────────────
    dt_columns          list[DTColumn]  column definitions
    dt_default_sort     str             e.g. "name" or "-created_at"
    dt_page_size        int             rows per page (default 25)
    dt_url              str             URL name for HTMX GETs (e.g. "items:item_list")
    dt_row_template     str             template path for one <tr> — uses 'row' variable
    dt_filter_template  str             template path for filter offcanvas body (optional)
    dt_search_placeholder str           placeholder for the search input
    dt_id               str             unique ID for localStorage col-visibility key

    Use in get_context_data()
    ─────────────────────────
    ctx.update(self.apply_datatable(filtered_qs))

    Use in get()
    ────────────
    if request.htmx:
        return render(request, "components/datatable/results.html", ctx)
    """

    dt_columns: list = []
    dt_default_sort: str = ""
    dt_page_size: int = 25
    dt_url: str = ""
    dt_row_template: str = ""
    dt_filter_template: str = ""
    dt_search_placeholder: str = "Buscar…"
    dt_id: str = "main"

    def apply_datatable(self, qs) -> dict:
        """Apply sort + pagination to *qs*. Merge the returned dict into ctx."""
        return build_datatable_context(
            self.request,
            qs,
            self.dt_columns,
            default_sort=self.dt_default_sort,
            page_size=self.dt_page_size,
            url=self.dt_url,
            row_template=self.dt_row_template,
            filter_template=self.dt_filter_template,
            search_placeholder=self.dt_search_placeholder,
            dt_id=self.dt_id,
        )
