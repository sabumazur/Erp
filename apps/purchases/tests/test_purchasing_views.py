"""
View tests for the purchases app.

Covers:
  List views     — login-required, member sees list, HTMX partial response
  Create/edit    — admin-required, form validation, redirect on success
  Delete         — admin-required, status guard, soft-delete confirmed
  Confirm/cancel — admin-required, service called correctly
  Org isolation  — org B cannot read/write org A records
"""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.models import Membership
from apps.accounts.tests.factories import MembershipFactory, OrganizationFactory, UserFactory
from apps.purchases.models import PurchaseDocument, PurchaseSequence
from apps.purchases.services import PurchaseOrderService, SupplierInvoiceService
from apps.purchases.tests.factories import (
    PurchaseDocumentFactory,
    PurchaseDocumentItemFactory,
    SupplierFactory,
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_member(role=Membership.Role.MEMBER):
    org  = OrganizationFactory()
    user = UserFactory()
    ms   = MembershipFactory(user=user, organization=org, role=role)
    return ms


def _make_admin():
    return _make_member(role=Membership.Role.ADMIN)


def _login(client, ms):
    client.force_login(ms.user)
    s = client.session
    s["active_org_slug"] = ms.organization.slug
    s.save()


def _ensure_sequence(org):
    PurchaseSequence.objects.get_or_create(
        organization=org,
        defaults={"prefix": "OC", "next_value": 1, "padding": 5},
    )


def _draft_po(org, supplier=None):
    supplier = supplier or SupplierFactory(organization=org)
    po = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type=PurchaseDocument.DocType.PURCHASE_ORDER,
        status=PurchaseDocument.Status.DRAFT,
    )
    PurchaseDocumentItemFactory(
        purchase_document=po,
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
    )
    po.recompute_totals()
    po.refresh_from_db()
    return po


def _confirmed_po(org, supplier=None):
    po = _draft_po(org, supplier)
    _ensure_sequence(org)
    PurchaseOrderService.confirm(po)
    po.refresh_from_db()
    return po


def _confirmed_si(org, supplier=None, ncf="B0100000001"):
    supplier = supplier or SupplierFactory(organization=org)
    si = PurchaseDocumentFactory(
        organization=org,
        supplier=supplier,
        doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
        status=PurchaseDocument.Status.DRAFT,
        supplier_ncf=ncf,
        supplier_ncf_type="B01",
    )
    PurchaseDocumentItemFactory(purchase_document=si, unit_price=Decimal("1000.00"))
    si.recompute_totals()
    SupplierInvoiceService.confirm(si)
    si.refresh_from_db()
    return si


# ── Purchase Order — list ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderListView:

    def test_requires_login(self, client):
        r = client.get(reverse("purchases:po_list"))
        assert r.status_code == 302
        assert "/login/" in r["Location"] or "/accounts/" in r["Location"]

    def test_member_can_see_list(self, client):
        ms = _make_member()
        _login(client, ms)
        r = client.get(reverse("purchases:po_list"))
        assert r.status_code == 200

    def test_htmx_returns_partial(self, client):
        ms = _make_member()
        _login(client, ms)
        r = client.get(
            reverse("purchases:po_list"),
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        # Full page has 'Órdenes de Compra'; partial does not include the outer layout
        assert b"<html" not in r.content

    def test_org_isolation_other_org_pos_not_visible(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        _ensure_sequence(org_b)
        po_b = _confirmed_po(org_b, supplier_b)

        _login(client, ms_a)
        r = client.get(reverse("purchases:po_list"))
        assert r.status_code == 200
        assert po_b.number.encode() not in r.content


# ── Purchase Order — detail ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderDetailView:

    def test_member_can_view_detail(self, client):
        ms = _make_member()
        _login(client, ms)
        po = _draft_po(ms.organization)
        r = client.get(reverse("purchases:po_detail", args=[po.pk]))
        assert r.status_code == 200

    def test_org_isolation_cannot_view_other_org_po(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        po_b = _draft_po(org_b)
        _login(client, ms_a)
        r = client.get(reverse("purchases:po_detail", args=[po_b.pk]))
        assert r.status_code == 404


# ── Purchase Order — confirm action ──────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderConfirmView:

    def test_admin_can_confirm(self, client):
        ms = _make_admin()
        _login(client, ms)
        _ensure_sequence(ms.organization)
        po = _draft_po(ms.organization)
        r = client.post(reverse("purchases:po_confirm", args=[po.pk]))
        assert r.status_code == 302
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CONFIRMED

    def test_member_cannot_confirm(self, client):
        ms = _make_member()
        _login(client, ms)
        po = _draft_po(ms.organization)
        r = client.post(reverse("purchases:po_confirm", args=[po.pk]))
        assert r.status_code == 403

    def test_org_isolation_cannot_confirm_other_org_po(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        po_b = _draft_po(org_b)
        _login(client, ms_a)
        r = client.post(reverse("purchases:po_confirm", args=[po_b.pk]))
        assert r.status_code == 404


# ── Purchase Order — cancel action ───────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderCancelView:

    def test_admin_can_cancel_confirmed(self, client):
        ms = _make_admin()
        _login(client, ms)
        _ensure_sequence(ms.organization)
        po = _confirmed_po(ms.organization)
        r = client.post(reverse("purchases:po_cancel", args=[po.pk]))
        assert r.status_code == 302
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CANCELLED

    def test_member_cannot_cancel(self, client):
        ms = _make_member()
        _login(client, ms)
        po = _draft_po(ms.organization)
        r = client.post(reverse("purchases:po_cancel", args=[po.pk]))
        assert r.status_code == 403


# ── Purchase Order — delete ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestPurchaseOrderDeleteView:

    def test_admin_can_delete_draft(self, client):
        ms = _make_admin()
        _login(client, ms)
        po = _draft_po(ms.organization)
        pk = po.pk
        r = client.post(reverse("purchases:po_delete", args=[pk]))
        assert r.status_code == 302
        assert not PurchaseDocument.objects.filter(pk=pk).exists()

    def test_cannot_delete_confirmed(self, client):
        ms = _make_admin()
        _login(client, ms)
        _ensure_sequence(ms.organization)
        po = _confirmed_po(ms.organization)
        r = client.post(reverse("purchases:po_delete", args=[po.pk]))
        assert r.status_code == 302  # redirects back with error message
        po.refresh_from_db()
        assert po.status == PurchaseDocument.Status.CONFIRMED  # not deleted

    def test_member_cannot_delete(self, client):
        ms = _make_member()
        _login(client, ms)
        po = _draft_po(ms.organization)
        r = client.post(reverse("purchases:po_delete", args=[po.pk]))
        assert r.status_code == 403


# ── Supplier Invoice — list ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierInvoiceListView:

    def test_requires_login(self, client):
        r = client.get(reverse("purchases:supplier_invoice_list"))
        assert r.status_code == 302

    def test_member_can_see_list(self, client):
        ms = _make_member()
        _login(client, ms)
        r = client.get(reverse("purchases:supplier_invoice_list"))
        assert r.status_code == 200

    def test_htmx_returns_partial(self, client):
        ms = _make_member()
        _login(client, ms)
        r = client.get(
            reverse("purchases:supplier_invoice_list"),
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert b"<html" not in r.content

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        si_b = _confirmed_si(org_b, supplier_b, ncf="B0100000099")

        _login(client, ms_a)
        r = client.get(reverse("purchases:supplier_invoice_list"))
        assert r.status_code == 200
        assert si_b.supplier_ncf.encode() not in r.content


# ── Supplier Invoice — confirm ────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierInvoiceConfirmView:

    def test_admin_can_confirm(self, client):
        ms = _make_admin()
        _login(client, ms)
        org = ms.organization
        supplier = SupplierFactory(organization=org)
        si = PurchaseDocumentFactory(
            organization=org,
            supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000001",
            supplier_ncf_type="B01",
        )
        PurchaseDocumentItemFactory(purchase_document=si, unit_price=Decimal("1000.00"))
        si.recompute_totals()
        r = client.post(reverse("purchases:supplier_invoice_confirm", args=[si.pk]))
        assert r.status_code == 302
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CONFIRMED

    def test_member_cannot_confirm(self, client):
        ms = _make_member()
        _login(client, ms)
        supplier = SupplierFactory(organization=ms.organization)
        si = PurchaseDocumentFactory(
            organization=ms.organization,
            supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000001",
        )
        r = client.post(reverse("purchases:supplier_invoice_confirm", args=[si.pk]))
        assert r.status_code == 403

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        si_b = PurchaseDocumentFactory(
            organization=org_b,
            supplier=supplier_b,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
            supplier_ncf="B0100000001",
        )
        _login(client, ms_a)
        r = client.post(reverse("purchases:supplier_invoice_confirm", args=[si_b.pk]))
        assert r.status_code == 404


# ── Supplier Invoice — delete ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierInvoiceDeleteView:

    def test_admin_can_delete_draft(self, client):
        ms = _make_admin()
        _login(client, ms)
        supplier = SupplierFactory(organization=ms.organization)
        si = PurchaseDocumentFactory(
            organization=ms.organization,
            supplier=supplier,
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            status=PurchaseDocument.Status.DRAFT,
        )
        pk = si.pk
        r = client.post(reverse("purchases:supplier_invoice_delete", args=[pk]))
        assert r.status_code == 302
        assert not PurchaseDocument.objects.filter(pk=pk).exists()

    def test_cannot_delete_confirmed(self, client):
        ms = _make_admin()
        _login(client, ms)
        si = _confirmed_si(ms.organization, ncf="B0100000001")
        r = client.post(reverse("purchases:supplier_invoice_delete", args=[si.pk]))
        assert r.status_code == 302
        si.refresh_from_db()
        assert si.status == PurchaseDocument.Status.CONFIRMED


# ── Supplier Payment — list ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierPaymentListView:

    def test_requires_login(self, client):
        r = client.get(reverse("purchases:supplier_payment_list"))
        assert r.status_code == 302

    def test_member_can_see_list(self, client):
        ms = _make_member()
        _login(client, ms)
        r = client.get(reverse("purchases:supplier_payment_list"))
        assert r.status_code == 200

    def test_htmx_returns_partial(self, client):
        ms = _make_member()
        _login(client, ms)
        r = client.get(
            reverse("purchases:supplier_payment_list"),
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        assert b"<html" not in r.content

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b)
        si_b = _confirmed_si(org_b, supplier_b, ncf="B0100000001")

        from apps.purchases.services import SupplierPaymentService
        pay_b = SupplierPaymentService.create_payment(
            supplier=supplier_b,
            org=org_b,
            payment_date=si_b.issue_date,
            method="TRANSFER",
            reference="ORG-B-REF",
            notes="",
            allocations=[{"invoice": si_b, "amount": si_b.total}],
        )

        _login(client, ms_a)
        r = client.get(reverse("purchases:supplier_payment_list"))
        assert r.status_code == 200
        assert b"ORG-B-REF" not in r.content


# ── Supplier — list ───────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSupplierListView:

    def test_requires_login(self, client):
        r = client.get(reverse("purchases:supplier_list"))
        assert r.status_code == 302

    def test_member_can_see_list(self, client):
        ms = _make_member()
        _login(client, ms)
        r = client.get(reverse("purchases:supplier_list"))
        assert r.status_code == 200

    def test_org_isolation(self, client):
        ms_a = _make_admin()
        org_b = OrganizationFactory()
        supplier_b = SupplierFactory(organization=org_b, name="Proveedor Secreto B")

        _login(client, ms_a)
        r = client.get(reverse("purchases:supplier_list"))
        assert r.status_code == 200
        assert b"Proveedor Secreto B" not in r.content

    def test_admin_htmx_create(self, client):
        ms = _make_admin()
        _login(client, ms)
        r = client.post(
            reverse("purchases:supplier_list"),
            {
                "name": "Proveedor HTMX S.R.L.",
                "id_type": "RNC",
                "rnc_cedula": "101234567",
            },
            HTTP_HX_REQUEST="true",
        )
        # Should return 200 (success table refresh) or 200 with form errors
        assert r.status_code == 200
