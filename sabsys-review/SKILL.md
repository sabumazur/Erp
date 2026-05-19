---
name: sabsys-review
description: >
  Use when reviewing code in the sabsys Django ERP project — any view, model,
  service, form, template, or test file written for sabsys. Triggers include:
  "review this", "check my code", "is this correct?", "audit this view/service",
  "code review", "does this follow the patterns?", "does this follow sabsys patterns?",
  "is this ready to merge?", "what's wrong with this", or any request to verify that
  newly written sabsys code is architecturally correct. Pairs with sabsys-feature,
  which generates the code this skill reviews.
---

# sabsys Code Review

You are reviewing code for **sabsys** — a multi-tenant Django ERP for Dominican
businesses. Apply the checklist below to every file submitted. Group findings by
severity. Be specific: include file path, line reference, and a concrete fix for
every finding.

---

## How to run a review

1. Read every file in scope fully before flagging anything.
2. Work through the checklist section by section.
3. Output findings grouped by severity (Critical → Warning → Template → JavaScript → Suggestion).
4. End with a **Passed** list for categories that are clean — silence is ambiguous.

---

## Checklist

### 🔴 Critical — must fix before merge

| # | What to check | Why it matters |
|---|---------------|----------------|
| C1 | Every view class inherits `ERPBaseViewMixin` | Without it: no login gate, no org middleware, no permission checks |
| C2 | Every queryset is scoped with `.for_org(request.organization)` | Missing scope = cross-tenant data leak |
| C3 | Uniqueness checks use `.all_objects`, not `.objects` | `.objects` excludes soft-deleted rows → collisions allowed on reuse |
| C4 | No raw SQL or unparameterized string formatting in queries | SQL injection vector |
| C5 | HTMX POST endpoints have `{% csrf_token %}` in template and/or `hx-headers` with `X-CSRFToken` | CSRF bypass |
| C6 | Write operations (create/update/delete) have `admin_required=True` or `required_permission` set | Any authenticated member could mutate data |
| C7 | Multi-step state mutations live in a service class, not inline in the view | No atomicity, logic duplication, untestable |
| C8 | Service methods that touch multiple rows/models use `@transaction.atomic` | Partial writes on error |
| C9 | `model.hard_delete()` is not used unless explicitly justified | Hard-delete where soft is expected loses audit trail |
| C10 | No `pre_delete`/`post_delete` signal assumed to fire on soft-delete | `model.delete()` sets `deleted_at`; signals are NOT emitted |

### 🟡 Warning — should fix, may cause bugs or drift

| # | What to check | Why it matters |
|---|---------------|----------------|
| W1 | QuerySets with related model access use `select_related` / `prefetch_related` | N+1 in templates/serializers |
| W2 | Plain `View` subclasses use `self.get_context(...)`, not `get_context_data()` | `get_context_data()` on a plain `View` skips sidebar vars |
| W3 | `TemplateView` subclasses use `super().get_context_data(**kwargs)`, not `self.get_context()` | `self.get_context()` on a TemplateView bypasses DataTableMixin chain |
| W4 | Service methods raise `ValueError` for business-rule violations, not `Http404` or `PermissionDenied` | HTTP concerns leak into services; callers can't handle cleanly |
| W5 | URL path converters use `<uuid:pk>`, not `<int:pk>` or `<str:pk>` | PKs are UUIDs; wrong converter returns 404 on valid requests |
| W6 | Status/state fields use `models.TextChoices` inner class | Raw strings scatter magic values across the codebase |
| W7 | HTMX success responses trigger `showToast`, blocked responses trigger `showSwal` | UI gives no feedback if trigger is missing or wrong |
| W8 | Views that should be module-gated have `required_module` set | Feature access unguarded even if module is disabled for the org |
| W9 | All UI-facing strings are wrapped with `gettext_lazy` / `{% trans %}` | Strings hard-coded in English break Spanish-first UI |
| W10 | Modal form's `FormHelper` has `form_tag = False` | Crispy renders a nested `<form>` inside the modal's `<form>` |
| W11 | Delete views are POST-only (no GET handler that mutates) | GET-based deletes are triggerable from `<img src>` etc. |
| W12 | Sequences and shared counters use `select_for_update()` before read-modify-write | Without it, concurrent requests produce duplicate numbers (invoice #, order #, etc.) |

### 🟠 Template — HTMX, Alpine.js, Bootstrap 5

| # | What to check | Why it matters |
|---|---------------|----------------|
| T1 | HTMX action buttons include `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` | POST/DELETE buttons without it will 403 |
| T2 | `hx-target` points to a valid, existing DOM ID | Wrong target silently swaps into nothing |
| T3 | `hx-swap` is appropriate for the context (`innerHTML` for modal body, `outerHTML` for row replacement) | Wrong swap leaves stale or duplicated content |
| T4 | `hx-trigger` is explicit when not using the default (click for buttons, submit for forms) | Implicit triggers cause unexpected firing |
| T5 | Row partials (`*_row.html`) render a single `<tr>` with no wrapper element | Extra wrapper breaks the datatable DOM |
| T6 | Modal structure has `modal fade` class, `tabindex="-1"`, and a unique `id` | Bootstrap modal won't open without these |
| T7 | Modal body target ID matches `hx-target` on the triggering button | Mismatch means HTMX loads into the wrong element |
| T8 | Edit buttons use `hx-get` to load the form into the modal body before opening | Opening an empty modal then loading is a race condition |
| T9 | Delete buttons use `hx-confirm` before `hx-post` | No confirmation = accidental deletes |
| T10 | Alpine.js `x-data` is scoped to the smallest possible element | Global scope causes state bleed between components |
| T11 | Alpine.js reactive vars bound with `x-model` are initialized in `x-data` | Uninitialized vars throw silent JS errors |
| T12 | Bootstrap offcanvas filter panels have a unique `id` and matching `data-bs-target` on the trigger button | Offcanvas won't open without the correct linkage |
| T13 | Bootstrap Icons use the `bi bi-*` double-class pattern | Single class `bi-*` without `bi` renders nothing |
| T14 | `{% url %}` tags use the correct `app_name:view_name` namespace | Unnamespaced URLs break in multi-app projects |
| T15 | Partials do not extend `base.html` | Partials returned via HTMX must be fragment-only |

### 🟣 JavaScript — app.js conventions and inline scripts

#### Architecture rules (app.js pattern)

| # | What to check | Why it matters |
|---|---------------|----------------|
| J1 | New functions added to app.js are inside the IIFE, not in global scope directly | Variables outside the IIFE pollute the global namespace |
| J2 | Public functions are explicitly exported at the bottom via `window.fnName = fnName` | Functions not exported there are inaccessible to Alpine and templates |
| J3 | All DOM init is called inside `ready()` at the bottom, not at parse time | Early execution fails when DOM isn't ready |

#### Configuration and URLs

| # | What to check | Why it matters |
|---|---------------|----------------|
| J4 | Configurable strings and labels use `getConfig("key", "fallback")` from `window.SabSysConfig` | Hardcoded Spanish strings can't be overridden per deployment |
| J5 | URLs for `fetch()` calls are passed as named globals (`window.MY_URL`) set in the template, not hardcoded | Hardcoded URLs break when URL structure changes |
| J6 | Django data passed to JS uses `{{ data\|json_script:"element-id" }}` + `parseJsonScript("element-id", fallback)` — never `var x = {{ data\|safe }}` | `\|safe` bypasses escaping and opens XSS; `json_script` is safe by design |

#### Alpine.js

| # | What to check | Why it matters |
|---|---------------|----------------|
| J7 | New Alpine components are factory functions returning plain objects, exported via `window.fnName = fnName` | Inline `x-data="{...}"` for complex logic is hard to test and maintain |
| J8 | After an HTMX swap that injects Alpine components, `Alpine.initTree(target)` is called | Alpine doesn't auto-initialize elements swapped in by HTMX |
| J9 | After an HTMX swap that injects HTMX attributes, `htmx.process(target)` is called | HTMX doesn't auto-process attributes on swapped content |
| J10 | `Alpine.evaluate()` calls are wrapped in `try/catch` | Reactive state mismatch throws silently in some Alpine versions |

#### HTMX events

| # | What to check | Why it matters |
|---|---------------|----------------|
| J11 | Custom HTMX event listeners use `document.body.addEventListener("eventName", fn)` not `htmx.on()` | Consistent with existing `showToast`, `showSwal`, `rncFound`, `rncNotFound`, `closeDeptModal` handlers |
| J12 | New custom event names are documented in a comment near the listener | Event names are stringly-typed; undocumented ones are invisible to reviewers |
| J13 | One-time event listeners (e.g. `shown.bs.modal`) remove themselves after firing | Accumulating listeners on long-lived elements cause memory leaks and duplicate callbacks |

#### Security

| # | What to check | Why it matters |
|---|---------------|----------------|
| J14 | Dynamic content inserted via `innerHTML` is passed through `escapeHtml()` | Unescaped user data in innerHTML is an XSS vector |
| J15 | `fetch()` POST calls read CSRF from `document.querySelector("[name=csrfmiddlewaretoken]")` and pass it as `X-CSRFToken` header | Django rejects POST without valid CSRF |
| J16 | `fetch()` calls handle both success and error paths (`.catch()` present) | Silent failures on network errors confuse users |

#### Inline `<script>` blocks in templates

| # | What to check | Why it matters |
|---|---------------|----------------|
| J17 | Inline scripts only set `window.MY_URL` or `window.SabSysConfig` values — no logic | Logic in inline scripts is untestable and duplicates app.js |
| J18 | `<script>` blocks are in `{% block scripts %}` or at the bottom of the template | Mid-template scripts block rendering |
| J19 | No `console.log` or `console.warn` left in committed code | Leaks internal data; use only for temporary debugging |

### 🔵 Suggestion — code quality and consistency

| # | What to check |
|---|---------------|
| S1 | View contains logic that could move to a model method or service (fat view) |
| S2 | Complex service methods have a one-line docstring explaining the transition/rule |
| S3 | Repeated queryset filter expressions that could be a manager method |
| S4 | Templates load `{% load i18n humanize %}` at the top |
| S5 | Breadcrumbs present and correctly formed: last entry has no `url` key |
| S6 | New view has at least: login-required test + happy-path test |
| S7 | New factory decorated with `@mute_signals(post_save)` |
| S8 | `admin.py` registration exists for any new model |

---

## Output format

```
## sabsys Review — <scope (file or app)>

### 🔴 Critical (N found)
- **C2** `apps/invoices/views.py:42` — Queryset not org-scoped.
  Fix: `Invoice.objects.for_org(request.organization).filter(...)`

### 🟡 Warning (N found)
- **W1** `apps/invoices/views.py:38` — `invoice.items.all()` in template loop.
  Fix: Add `.prefetch_related("items")` to the list queryset.

### 🔵 Suggestion (N found)
- **S5** `apps/invoices/templates/invoice_detail.html:8` — Last breadcrumb has `url`.
  Fix: Remove the `url` key from the final breadcrumb dict.

### 🟠 Template (N found)
- **T5** `templates/invoices/partials/invoice_row.html:1` — Row partial wrapped in `<div>`.
  Fix: Remove the `<div>` wrapper — partial must be a bare `<tr>`.

### 🟣 JavaScript (N found)
- **J6** `templates/invoices/invoice_form.html:12` — Data passed as `var data = {{ items|safe }}`.
  Fix: Use `{{ items|json_script:"invoice-items-data" }}` and read with `parseJsonScript("invoice-items-data", [])`.
- **J8** `static/js/app.js:892` — HTMX swap injects Alpine component but `Alpine.initTree()` not called.
  Fix: Add `if (typeof Alpine !== "undefined") Alpine.initTree(e.detail.target);` in the `htmx:afterSwap` handler.

### ✅ Passed
- Org scoping: all querysets scoped with `.for_org()`
- Auth: all views inherit `ERPBaseViewMixin`
- CSRF: HTMX forms include `X-CSRFToken` header
- Service layer: mutations in `InvoiceService`, not views
- Translations: all UI strings use `gettext_lazy`
- Templates: row partials are bare `<tr>`, HTMX targets valid, CSRF headers present
- JavaScript: CSRF present on all fetch calls, escapeHtml used on innerHTML, Alpine components follow factory pattern
```

**Rules for findings:**
- Include checklist ID (C1, W3, S5) so authors can cross-reference.
- Include file + line reference for every finding.
- State the concrete fix, not just the problem.
- If a finding is debatable, mark it with `(?)`.
- Passed list must cover every Critical and Warning category — don't omit clean ones.

---

## Quick-reference conventions

| Topic | Expected pattern |
|-------|-----------------|
| View base class | `ERPBaseViewMixin` on every view |
| Write ops | `admin_required = True` or `required_permission` |
| Org scoping | `Model.objects.for_org(request.organization)` |
| Uniqueness | `Model.all_objects.filter(...)` |
| Context — plain `View` | `self.get_context(...)` |
| Context — `TemplateView` | `super().get_context_data(**kwargs)` |
| HTMX success | `HX-Trigger: {"showToast": {...}}` |
| HTMX blocked | `HX-Trigger: {"showSwal": {"type": "error", ...}}` |
| Service violations | `raise ValueError(...)`, never Http404/PermissionDenied |
| Atomicity | `@transaction.atomic` on multi-step service methods |
| Soft-delete | `model.delete()` — signals NOT emitted |
| Modal forms | `form_tag = False` in `FormHelper` |
| URL PKs | `<uuid:pk>` path converter |
| Status fields | `models.TextChoices` inner class |
| Test login | `client.force_login(m.user)` + `session["active_org_slug"] = m.organization.slug` |
| Factory signal guard | `@mute_signals(post_save)` on every factory |
