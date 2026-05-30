"""
Tests for DashboardView context: KPIs, counts, tables, charts, org isolation.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import TeamFactory
from apps.core.models import Module
from apps.sales.models import SalesDocument
from apps.sales.tests.factories import (
    CustomerFactory,
    SalesDocumentFactory,
    SalesDocumentItemFactory,
    PaymentFactory,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _login(client, membership):
    client.force_login(membership.user)
    s = client.session
    s["active_org_slug"] = membership.organization.slug
    s.save()


def _dashboard(client, membership):
    _login(client, membership)
    return client.get(reverse("accounts:dashboard"))


def _topbar_quick_menu(content):
    topbar = content[content.index('<header id="topbar"'):content.index("</header>")]
    marker = 'aria-label="Crear nuevo"'
    menu_start = topbar.index(marker)
    menu_start = topbar.index('<ul class="dropdown-menu">', menu_start)
    return topbar[menu_start:topbar.index("</ul>", menu_start)]


def _href(url):
    return f'href="{url}"'


def _make_invoice(org, status, amount, issue_date=None, due_date=None, doc_type=SalesDocument.DocType.INVOICE):
    """Create a confirmed invoice with one line item totalling `amount` (pre-ITBIS)."""
    if issue_date is None:
        issue_date = timezone.localdate()
    customer = CustomerFactory(organization=org)
    inv = SalesDocumentFactory(
        organization=org,
        customer=customer,
        status=status,
        issue_date=issue_date,
        due_date=due_date,
        doc_type=doc_type,
    )
    SalesDocumentItemFactory(document=inv, unit_price=amount, itbis_rate="EXEMPT")
    inv.recompute_totals()
    return inv


def _prev_month_date():
    today = timezone.localdate()
    first = today.replace(day=1)
    prev_last = first - timedelta(days=1)
    return prev_last.replace(day=1)


# ── KPI cards ──────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardKPIs:

    def test_month_invoiced_includes_confirmed(self, client, owner_membership):
        org = owner_membership.organization
        inv = _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("5000.00"))
        ctx = _dashboard(client, owner_membership).context
        assert ctx["month_invoiced"] == inv.total

    def test_dashboard_subnav_includes_suppliers_link(self, client, owner_membership):
        response = _dashboard(client, owner_membership)
        content = response.content.decode()
        subnav = content[content.index('<nav id="subnav"'):content.index("</nav>", content.index('<nav id="subnav"'))]

        assert response.status_code == 200
        assert reverse("purchases:supplier_list") in subnav

    def test_dashboard_subnav_excludes_payment_terms_link(self, client, owner_membership):
        response = _dashboard(client, owner_membership)
        content = response.content.decode()
        subnav = content[content.index('<nav id="subnav"'):content.index("</nav>", content.index('<nav id="subnav"'))]

        assert response.status_code == 200
        assert reverse("sales:payment_term_list") not in subnav

    def test_topbar_quick_menu_includes_purchasing_create_links_except_suppliers(self, client, owner_membership):
        response = _dashboard(client, owner_membership)
        quick_menu = _topbar_quick_menu(response.content.decode())

        assert response.status_code == 200
        assert _href(reverse("purchases:po_create")) in quick_menu
        assert _href(reverse("purchases:supplier_invoice_create")) in quick_menu
        assert _href(reverse("purchases:supplier_payment_create")) in quick_menu
        assert _href(reverse("purchases:po_list")) not in quick_menu
        assert _href(reverse("purchases:supplier_invoice_list")) not in quick_menu
        assert _href(reverse("purchases:supplier_payment_list")) not in quick_menu
        assert _href(reverse("purchases:supplier_list")) not in quick_menu
        assert _href(reverse("purchases:supplier_create")) not in quick_menu

    def test_topbar_quick_menu_hides_purchasing_links_without_purchasing_access(self, client, member_membership):
        team = TeamFactory(organization=member_membership.organization)
        team.modules.add(Module.objects.create(name="Sales", slug="sales"))
        member_membership.team = team
        member_membership.save(update_fields=["team", "updated_at"])

        response = _dashboard(client, member_membership)
        quick_menu = _topbar_quick_menu(response.content.decode())

        assert response.status_code == 200
        assert _href(reverse("purchases:po_create")) not in quick_menu
        assert _href(reverse("purchases:supplier_invoice_create")) not in quick_menu
        assert _href(reverse("purchases:supplier_payment_create")) not in quick_menu

    def test_month_invoiced_includes_paid(self, client, owner_membership):
        org = owner_membership.organization
        inv = _make_invoice(org, SalesDocument.Status.PAID, Decimal("2000.00"))
        ctx = _dashboard(client, owner_membership).context
        assert ctx["month_invoiced"] == inv.total

    def test_month_invoiced_excludes_draft(self, client, owner_membership):
        org = owner_membership.organization
        _make_invoice(org, SalesDocument.Status.DRAFT, Decimal("9999.00"))
        ctx = _dashboard(client, owner_membership).context
        assert ctx["month_invoiced"] == Decimal("0")

    def test_month_invoiced_excludes_previous_month(self, client, owner_membership):
        org = owner_membership.organization
        _make_invoice(
            org, SalesDocument.Status.CONFIRMED, Decimal("5000.00"),
            issue_date=_prev_month_date(),
        )
        ctx = _dashboard(client, owner_membership).context
        assert ctx["month_invoiced"] == Decimal("0")

    def test_month_collected_sums_current_month_payments(self, client, owner_membership):
        org = owner_membership.organization
        customer = CustomerFactory(organization=org)
        PaymentFactory(organization=org, customer=customer, amount=Decimal("3000.00"), date=timezone.localdate())
        ctx = _dashboard(client, owner_membership).context
        assert ctx["month_collected"] == Decimal("3000.00")

    def test_month_collected_excludes_previous_month(self, client, owner_membership):
        org = owner_membership.organization
        customer = CustomerFactory(organization=org)
        PaymentFactory(organization=org, customer=customer, amount=Decimal("3000.00"), date=_prev_month_date())
        ctx = _dashboard(client, owner_membership).context
        assert ctx["month_collected"] == Decimal("0")

    def test_outstanding_sums_confirmed_sent_overdue(self, client, owner_membership):
        org = owner_membership.organization
        inv1 = _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("1000.00"))
        inv2 = _make_invoice(org, SalesDocument.Status.SENT, Decimal("2000.00"))
        inv3 = _make_invoice(org, SalesDocument.Status.OVERDUE, Decimal("500.00"))
        ctx = _dashboard(client, owner_membership).context
        assert ctx["outstanding"] == inv1.total + inv2.total + inv3.total

    def test_outstanding_excludes_paid(self, client, owner_membership):
        org = owner_membership.organization
        _make_invoice(org, SalesDocument.Status.PAID, Decimal("9000.00"))
        ctx = _dashboard(client, owner_membership).context
        assert ctx["outstanding"] == Decimal("0")

    def test_overdue_total_and_count(self, client, owner_membership):
        org = owner_membership.organization
        inv1 = _make_invoice(org, SalesDocument.Status.OVERDUE, Decimal("600.00"))
        inv2 = _make_invoice(org, SalesDocument.Status.OVERDUE, Decimal("400.00"))
        ctx = _dashboard(client, owner_membership).context
        assert ctx["overdue_total"] == inv1.total + inv2.total
        assert ctx["overdue_count"] == 2

    def test_kpis_are_org_isolated(self, client, owner_membership):
        """Invoices from another org must not appear in KPIs."""
        from apps.accounts.tests.factories import OrganizationFactory, MembershipFactory
        from apps.accounts.models import Membership
        other_org = OrganizationFactory()
        _make_invoice(other_org, SalesDocument.Status.CONFIRMED, Decimal("99999.00"))
        ctx = _dashboard(client, owner_membership).context
        assert ctx["month_invoiced"] == Decimal("0")
        assert ctx["outstanding"] == Decimal("0")


# ── Stat pills ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardCounts:

    def test_customer_count(self, client, owner_membership):
        org = owner_membership.organization
        CustomerFactory.create_batch(3, organization=org)
        ctx = _dashboard(client, owner_membership).context
        assert ctx["customer_count"] == 3

    def test_pending_quotations_counts_confirmed_and_sent(self, client, owner_membership):
        org = owner_membership.organization
        customer = CustomerFactory(organization=org)
        SalesDocumentFactory(organization=org, customer=customer, status=SalesDocument.Status.CONFIRMED, doc_type=SalesDocument.DocType.QUOTATION)
        SalesDocumentFactory(organization=org, customer=customer, status=SalesDocument.Status.SENT, doc_type=SalesDocument.DocType.QUOTATION)
        SalesDocumentFactory(organization=org, customer=customer, status=SalesDocument.Status.DRAFT, doc_type=SalesDocument.DocType.QUOTATION)
        ctx = _dashboard(client, owner_membership).context
        assert ctx["pending_quotations"] == 2

    def test_pending_sale_orders_counts_confirmed_and_delivered(self, client, owner_membership):
        org = owner_membership.organization
        customer = CustomerFactory(organization=org)
        SalesDocumentFactory(organization=org, customer=customer, status=SalesDocument.Status.CONFIRMED, doc_type=SalesDocument.DocType.SALE_ORDER)
        SalesDocumentFactory(organization=org, customer=customer, status=SalesDocument.Status.DELIVERED, doc_type=SalesDocument.DocType.SALE_ORDER)
        SalesDocumentFactory(organization=org, customer=customer, status=SalesDocument.Status.DRAFT, doc_type=SalesDocument.DocType.SALE_ORDER)
        ctx = _dashboard(client, owner_membership).context
        assert ctx["pending_sale_orders"] == 2

    def test_counts_zero_when_empty_org(self, client, owner_membership):
        ctx = _dashboard(client, owner_membership).context
        assert ctx["customer_count"] == 0
        assert ctx["pending_quotations"] == 0
        assert ctx["pending_sale_orders"] == 0


# ── Tables ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardTables:

    def test_recent_invoices_excludes_draft(self, client, owner_membership):
        org = owner_membership.organization
        _make_invoice(org, SalesDocument.Status.DRAFT, Decimal("100.00"))
        _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("200.00"))
        ctx = _dashboard(client, owner_membership).context
        for inv in ctx["recent_invoices"]:
            assert inv.status != SalesDocument.Status.DRAFT

    def test_recent_invoices_capped_at_8(self, client, owner_membership):
        org = owner_membership.organization
        for _ in range(10):
            _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("100.00"))
        ctx = _dashboard(client, owner_membership).context
        assert len(ctx["recent_invoices"]) <= 8

    def test_recent_invoices_ordered_by_issue_date_desc(self, client, owner_membership):
        org = owner_membership.organization
        today = timezone.localdate()
        inv_old = _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("100.00"), issue_date=today - timedelta(days=5))
        inv_new = _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("200.00"), issue_date=today)
        ctx = _dashboard(client, owner_membership).context
        ids = [str(i.pk) for i in ctx["recent_invoices"]]
        assert ids.index(str(inv_new.pk)) < ids.index(str(inv_old.pk))

    def test_overdue_invoices_capped_at_6(self, client, owner_membership):
        org = owner_membership.organization
        for _ in range(8):
            _make_invoice(org, SalesDocument.Status.OVERDUE, Decimal("100.00"))
        ctx = _dashboard(client, owner_membership).context
        assert len(ctx["overdue_invoices"]) <= 6

    def test_overdue_invoices_only_contains_overdue(self, client, owner_membership):
        org = owner_membership.organization
        _make_invoice(org, SalesDocument.Status.OVERDUE, Decimal("100.00"))
        _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("200.00"))
        ctx = _dashboard(client, owner_membership).context
        for inv in ctx["overdue_invoices"]:
            assert inv.status == SalesDocument.Status.OVERDUE

    def test_recent_payments_capped_at_6(self, client, owner_membership):
        org = owner_membership.organization
        customer = CustomerFactory(organization=org)
        for _ in range(8):
            PaymentFactory(organization=org, customer=customer, amount=Decimal("100.00"))
        ctx = _dashboard(client, owner_membership).context
        assert len(ctx["recent_payments"]) <= 6

    def test_recent_payments_ordered_by_date_desc(self, client, owner_membership):
        org = owner_membership.organization
        customer = CustomerFactory(organization=org)
        today = timezone.localdate()
        old = PaymentFactory(organization=org, customer=customer, amount=Decimal("100.00"), date=today - timedelta(days=3))
        new = PaymentFactory(organization=org, customer=customer, amount=Decimal("200.00"), date=today)
        ctx = _dashboard(client, owner_membership).context
        ids = [str(p.pk) for p in ctx["recent_payments"]]
        assert ids.index(str(new.pk)) < ids.index(str(old.pk))


# ── Charts ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardCharts:

    def test_chart_months_has_6_entries(self, client, owner_membership):
        ctx = _dashboard(client, owner_membership).context
        assert len(ctx["chart_months"]) == 6

    def test_chart_invoiced_and_collected_have_6_entries(self, client, owner_membership):
        ctx = _dashboard(client, owner_membership).context
        assert len(ctx["chart_invoiced"]) == 6
        assert len(ctx["chart_collected"]) == 6

    def test_chart_invoiced_reflects_current_month(self, client, owner_membership):
        org = owner_membership.organization
        inv = _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("4000.00"))
        ctx = _dashboard(client, owner_membership).context
        # Last entry in chart_invoiced is current month
        assert ctx["chart_invoiced"][-1] == float(inv.total)

    def test_chart_collected_reflects_current_month(self, client, owner_membership):
        org = owner_membership.organization
        customer = CustomerFactory(organization=org)
        PaymentFactory(organization=org, customer=customer, amount=Decimal("1500.00"), date=timezone.localdate())
        ctx = _dashboard(client, owner_membership).context
        assert ctx["chart_collected"][-1] == 1500.0

    def test_chart_status_empty_when_no_invoices(self, client, owner_membership):
        ctx = _dashboard(client, owner_membership).context
        assert ctx["chart_status_labels"] == []
        assert ctx["chart_status_counts"] == []
        assert ctx["chart_status_colors"] == []

    def test_chart_status_populated_from_invoices(self, client, owner_membership):
        org = owner_membership.organization
        _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("1000.00"))
        _make_invoice(org, SalesDocument.Status.PAID, Decimal("2000.00"))
        ctx = _dashboard(client, owner_membership).context
        assert len(ctx["chart_status_labels"]) == 2
        assert len(ctx["chart_status_counts"]) == 2
        assert sum(ctx["chart_status_counts"]) == 2

    def test_customer_datasets_empty_when_no_invoices(self, client, owner_membership):
        ctx = _dashboard(client, owner_membership).context
        assert ctx["chart_customer_datasets"] == []

    def test_customer_datasets_capped_at_6(self, client, owner_membership):
        org = owner_membership.organization
        for _ in range(8):
            _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("1000.00"))
        ctx = _dashboard(client, owner_membership).context
        assert len(ctx["chart_customer_datasets"]) <= 6

    def test_customer_datasets_have_monthly_data(self, client, owner_membership):
        org = owner_membership.organization
        _make_invoice(org, SalesDocument.Status.CONFIRMED, Decimal("1000.00"))
        ctx = _dashboard(client, owner_membership).context
        dataset = ctx["chart_customer_datasets"][0]
        assert "label" in dataset
        assert "data" in dataset
        assert len(dataset["data"]) == 6


# ── Edge cases ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDashboardEdgeCases:

    def test_no_org_returns_empty_context(self, client, user):
        """User with no org session set still gets 200 with zero KPIs."""
        # Don't set active_org_slug — middleware falls back to first membership
        client.force_login(user)
        # The auto-created personal org from signal exists but has no invoices
        response = client.get(reverse("accounts:dashboard"))
        assert response.status_code == 200

    def test_today_in_context(self, client, owner_membership):
        ctx = _dashboard(client, owner_membership).context
        assert ctx["today"] == timezone.localdate()

    def test_sales_denied_member_sees_no_sales_context_or_values(self, client, member_membership):
        team = TeamFactory(organization=member_membership.organization)
        team.modules.add(Module.objects.create(name="Inventory", slug="inventory"))
        member_membership.team = team
        member_membership.save(update_fields=["team", "updated_at"])
        _make_invoice(
            member_membership.organization,
            SalesDocument.Status.CONFIRMED,
            Decimal("98765.43"),
        )

        response = _dashboard(client, member_membership)

        assert response.status_code == 200
        assert response.context["has_sales_access"] is False
        assert "month_invoiced" not in response.context
        assert "98765.43" not in response.content.decode()
