"""
Tests for invoices models, NCFService, signals, DGII validation rules
and RNC/Cédula format validators.
"""
from decimal import Decimal
import threading

import pytest
from django.core.exceptions import ValidationError

from apps.sales.models import CustomerDepartment, SalesDocument, SalesDocumentItem, NCFSequence
from apps.accounts.tests.factories import OrganizationFactory
from apps.sales.services import NCFService
from apps.sales.validators import validate_rnc, validate_cedula, validate_rnc_cedula
from .factories import (
    CustomerFactory, SalesDocumentFactory, SalesDocumentItemFactory,
    NCFSequenceFactory, PaymentFactory,
)


# ── NCFSequence ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNCFSequence:

    def test_generate_increments_sequence(self):
        seq = NCFSequenceFactory(ncf_type=31, current_seq=0)
        encf = NCFSequence.generate(seq.organization, 31)
        assert encf == "E310000000001"
        seq.refresh_from_db()
        assert seq.current_seq == 1

    def test_generate_formats_correctly(self):
        seq = NCFSequenceFactory(ncf_type=32, current_seq=99, series="E")
        encf = NCFSequence.generate(seq.organization, 32)
        assert encf == "E320000000100"
        assert len(encf) == 13

    def test_generate_raises_when_no_active_sequence(self):
        seq = NCFSequenceFactory(ncf_type=31, is_active=False)
        with pytest.raises(ValueError, match="No hay una secuencia NCF activa"):
            NCFSequence.generate(seq.organization, 31)

    def test_generate_raises_when_exhausted(self):
        seq = NCFSequenceFactory(ncf_type=31, current_seq=5, max_seq=5)
        with pytest.raises(ValueError, match="agotada"):
            NCFSequence.generate(seq.organization, 31)

    def test_cannot_lower_current_sequence(self):
        seq = NCFSequenceFactory(ncf_type=31, current_seq=3)
        seq.current_seq = 2
        with pytest.raises(ValidationError):
            seq.save()

    def test_cannot_delete_sequence_after_ncf_issued(self):
        seq = NCFSequenceFactory(ncf_type=31)
        invoice = SalesDocumentFactory(organization=seq.organization, ncf_type=31)
        invoice.encf = "E310000000001"
        invoice.save()
        with pytest.raises(ValidationError):
            seq.delete()


@pytest.mark.django_db(transaction=True)
class TestNCFConcurrency:

    def test_concurrent_generation_produces_unique_encfs(self):
        """Two threads must never get the same e-NCF."""
        seq = NCFSequenceFactory(ncf_type=31, current_seq=0, max_seq=100)
        org = seq.organization
        results = []
        errors = []

        def generate():
            try:
                results.append(NCFSequence.generate(org, 31))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=generate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == len(set(results)), "Duplicate e-NCFs generated!"


# ── InvoiceItem signals ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestInvoiceItemSignals:

    def test_invoice_totals_updated_on_item_save(self):
        invoice = SalesDocumentFactory()
        SalesDocumentItemFactory(
            document=invoice,
            quantity=Decimal("2"),
            unit_price=Decimal("1000.00"),
            itbis_rate=SalesDocumentItem.ITBISRate.RATE_18,
        )
        invoice.refresh_from_db()
        assert invoice.subtotal  == Decimal("2000.00")
        assert invoice.itbis_18  == Decimal("360.00")
        assert invoice.itbis_16  == Decimal("0.00")
        assert invoice.total     == Decimal("2360.00")

    def test_itbis_16_computed_separately(self):
        invoice = SalesDocumentFactory()
        SalesDocumentItemFactory(
            document=invoice,
            quantity=Decimal("1"),
            unit_price=Decimal("500.00"),
            itbis_rate=SalesDocumentItem.ITBISRate.RATE_16,
        )
        invoice.refresh_from_db()
        assert invoice.itbis_16 == Decimal("80.00")
        assert invoice.itbis_18 == Decimal("0.00")

    def test_exempt_item_contributes_zero_itbis(self):
        invoice = SalesDocumentFactory()
        SalesDocumentItemFactory(
            document=invoice,
            quantity=Decimal("1"),
            unit_price=Decimal("200.00"),
            itbis_rate=SalesDocumentItem.ITBISRate.EXEMPT,
        )
        invoice.refresh_from_db()
        assert invoice.itbis_18 == Decimal("0.00")
        assert invoice.itbis_16 == Decimal("0.00")
        assert invoice.subtotal == Decimal("200.00")
        assert invoice.total    == Decimal("200.00")

    def test_totals_recalculated_on_item_delete(self):
        invoice = SalesDocumentFactory()
        item = SalesDocumentItemFactory(
            document=invoice,
            quantity=Decimal("1"),
            unit_price=Decimal("1000.00"),
            itbis_rate=SalesDocumentItem.ITBISRate.RATE_18,
        )
        invoice.refresh_from_db()
        assert invoice.total == Decimal("1180.00")

        item.delete()
        invoice.refresh_from_db()
        assert invoice.total     == Decimal("0.00")
        assert invoice.subtotal  == Decimal("0.00")


@pytest.mark.django_db
class TestSalesDocumentSoftDeleteManagers:

    @pytest.mark.parametrize(
        ("doc_type", "manager_name"),
        [
            (SalesDocument.DocType.INVOICE, "invoices"),
            (SalesDocument.DocType.QUOTATION, "quotations"),
            (SalesDocument.DocType.SALE_ORDER, "sale_orders"),
        ],
    )
    def test_soft_deleted_documents_are_hidden_from_normal_managers(
        self, doc_type, manager_name
    ):
        document = SalesDocumentFactory(doc_type=doc_type)
        document.delete()

        assert not SalesDocument.objects.filter(pk=document.pk).exists()
        assert not getattr(SalesDocument, manager_name).filter(pk=document.pk).exists()
        assert SalesDocument.all_objects.filter(pk=document.pk).exists()


# ── NCFService ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNCFService:

    def _invoice_with_item(self):
        seq = NCFSequenceFactory(ncf_type=31)
        invoice = SalesDocumentFactory(
            organization=seq.organization,
            customer=CustomerFactory(organization=seq.organization, rnc_cedula="101123456"),
            ncf_type=31,
        )
        SalesDocumentItemFactory(document=invoice)
        return invoice

    def test_confirm_assigns_encf(self):
        invoice = self._invoice_with_item()
        NCFService.confirm(invoice)
        assert invoice.encf == "E310000000001"
        assert invoice.status == SalesDocument.Status.CONFIRMED

    def test_confirm_raises_if_not_draft(self):
        invoice = self._invoice_with_item()
        NCFService.confirm(invoice)
        with pytest.raises(ValueError, match="Borrador"):
            NCFService.confirm(invoice)

    def test_mark_paid_transitions_status(self):
        invoice = self._invoice_with_item()
        NCFService.confirm(invoice)
        NCFService.mark_sent(invoice)
        NCFService.mark_paid(invoice)
        assert invoice.status == SalesDocument.Status.PAID

    def test_cancel_sets_cancelled_status(self):
        invoice = self._invoice_with_item()
        NCFService.confirm(invoice)
        NCFService.cancel(invoice)
        assert invoice.status == SalesDocument.Status.CANCELLED

    def test_cannot_cancel_paid_invoice(self):
        invoice = self._invoice_with_item()
        NCFService.confirm(invoice)
        NCFService.mark_sent(invoice)
        NCFService.mark_paid(invoice)
        with pytest.raises(ValueError, match="Nota de Crédito"):
            NCFService.cancel(invoice)


# ── DGII validation rules ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDGIIValidation:

    def test_credito_fiscal_requires_rnc(self):
        """Tipo 31 must have buyer RNC."""
        customer = CustomerFactory(rnc_cedula="")  # no RNC
        invoice = SalesDocumentFactory.build(
            organization=customer.organization,
            customer=customer,
            ncf_type=31,
        )
        with pytest.raises(ValidationError):
            invoice.clean()

    def test_nota_credito_requires_encf_modified(self):
        """Tipo 34 must reference another invoice."""
        invoice = SalesDocumentFactory.build(ncf_type=34, encf_modified=None)
        with pytest.raises(ValidationError):
            invoice.clean()

    def test_consumo_without_rnc_is_valid(self):
        """Tipo 32 with no RNC should pass validation."""
        customer = CustomerFactory(rnc_cedula="")
        invoice = SalesDocumentFactory(
            organization=customer.organization,
            customer=customer,
            ncf_type=32,
        )
        invoice.clean()  # should not raise

    def test_rejects_customer_from_another_organization(self):
        org = OrganizationFactory()
        invoice = SalesDocumentFactory.build(organization=org, customer=CustomerFactory())
        with pytest.raises(ValidationError):
            invoice.clean()

    def test_rejects_cross_organization_department(self):
        customer = CustomerFactory()
        other_customer = CustomerFactory()
        department = CustomerDepartment(
            organization=other_customer.organization,
            customer=other_customer,
            name="Other branch",
        )
        department.save()
        order = SalesDocumentFactory.build(
            organization=customer.organization,
            customer=customer,
            doc_type=SalesDocument.DocType.SALE_ORDER,
            department=department,
        )
        with pytest.raises(ValidationError):
            order.clean()


# ── RNC / Cédula validators ───────────────────────────────────────────────────

class TestRNCValidator:

    def test_valid_rnc(self):
        ok, msg = validate_rnc("130461554")  # Café Tropical Mazur SRL
        assert ok, msg

    def test_rnc_does_not_validate_check_digit(self):
        ok, msg = validate_rnc("130461550")  # last digit changed
        assert ok, msg

    def test_rnc_wrong_length(self):
        ok, msg = validate_rnc("12345678")  # 8 digits
        assert not ok
        assert "9" in msg

    def test_rnc_with_dashes_stripped(self):
        ok, msg = validate_rnc("1-30-46155-4")  # 130461554 with dashes
        assert ok, msg

    def test_rnc_field_validator_allows_repeated_digits(self):
        validate_rnc_cedula("000000000", id_type="RNC")

    def test_rnc_field_validator_passes_on_valid(self):
        validate_rnc_cedula("130461554", id_type="RNC")  # must not raise


class TestCedulaValidator:

    def test_valid_cedula(self):
        ok, msg = validate_cedula("00113918205")
        assert ok, msg

    def test_cedula_does_not_validate_check_digit(self):
        ok, msg = validate_cedula("00113918200")  # last digit changed
        assert ok, msg

    def test_cedula_wrong_length(self):
        ok, msg = validate_cedula("0011391820")  # 10 digits
        assert not ok
        assert "11" in msg

    def test_cedula_with_dashes_stripped(self):
        ok, msg = validate_cedula("001-1391820-5")
        assert ok, msg

    def test_cedula_field_validator_allows_repeated_digits(self):
        validate_rnc_cedula("00000000000", id_type="CED")

    def test_cedula_field_validator_passes_on_valid(self):
        validate_rnc_cedula("00113918205", id_type="CED")  # must not raise

    def test_unsupported_id_type_is_rejected(self):
        with pytest.raises(ValidationError):
            validate_rnc_cedula("AB123456", id_type="PAS")

    @pytest.mark.django_db
    def test_customer_model_rejects_unsupported_id_type(self):
        customer = CustomerFactory.build(
            organization=OrganizationFactory(),
            id_type="PAS",
            rnc_cedula="AB123456",
        )

        with pytest.raises(ValidationError):
            customer.full_clean()

    def test_auto_detect_rnc_by_length(self):
        """9-digit string auto-detected as RNC."""
        ok, _ = validate_rnc("130461554")
        assert ok

    def test_auto_detect_cedula_by_length(self):
        """11-digit string auto-detected as Cédula."""
        ok, _ = validate_cedula("00113918205")
        assert ok
