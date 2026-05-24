"""
apps/invoices/services.py
Business-logic services for the invoices app.

All public functions assume they are called from within a request/view context
where request.organization is already set.
"""
import logging
from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from decimal import Decimal as _Decimal

from django.db.models import Sum as _Sum
from django.db.models.functions import Coalesce as _Coalesce
from django.db.models import DecimalField as _DecimalField

from .models import DocumentSequence, SalesDocument, SalesDocumentItem, NCFSequence, Payment, PaymentAllocation

logger = logging.getLogger(__name__)


# ── NCFService ────────────────────────────────────────────────────────────────

class NCFService:
    """
    Handles the atomic assignment of an e-NCF to a confirmed SalesDocument.

    Usage (inside a view POST handler):
        try:
            NCFService.confirm(invoice)
        except ValueError as exc:
            messages.error(request, str(exc))
    """

    @staticmethod
    @transaction.atomic
    def confirm(invoice: SalesDocument) -> SalesDocument:
        """
        Transition a SalesDocument from DRAFT → CONFIRMED by assigning the next
        e-NCF from the organization's active sequence for the invoice's NCF type.

        Raises:
            ValueError      — if the invoice is not in DRAFT status, if no active
                              sequence exists for this NCF type, or if the sequence
                              is exhausted.
            ValidationError — if the invoice fails DGII business-rule validation
                              (e.g. missing RNC for Crédito Fiscal).
        """
        if invoice.doc_type != SalesDocument.DocType.INVOICE:
            raise ValueError(_("Solo se pueden confirmar facturas fiscales con este servicio."))

        if invoice.status != SalesDocument.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden confirmar facturas en estado Borrador. "
                f"Estado actual: {invoice.get_status_display()}."
            )

        # Run DGII field-level validation
        invoice.full_clean()

        # Assign the next authorized fiscal number atomically.
        encf = NCFSequence.generate(invoice.organization, invoice.ncf_type)

        invoice.encf = encf
        invoice.status = SalesDocument.Status.CONFIRMED
        try:
            invoice.save(update_fields=["encf", "status", "updated_at"])
        except IntegrityError as exc:
            raise ValueError(_("El NCF generado ya esta registrado; revise la secuencia activa.")) from exc

        return invoice

    @staticmethod
    def mark_sent(invoice: SalesDocument) -> SalesDocument:
        """Transition CONFIRMED → SENT."""
        if invoice.doc_type != SalesDocument.DocType.INVOICE:
            raise ValueError(_("Este documento no es una factura."))
        if invoice.status != SalesDocument.Status.CONFIRMED:
            raise ValueError("Solo se pueden enviar facturas confirmadas.")
        invoice.status = SalesDocument.Status.SENT
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    def mark_paid(invoice: SalesDocument) -> SalesDocument:
        """
        Transition CONFIRMED / SENT / OVERDUE → PAID.
        Called automatically by PaymentService when the sum of allocations
        covers the invoice total.
        """
        if invoice.doc_type != SalesDocument.DocType.INVOICE or invoice.ncf_type in SalesDocument.NOTE_TYPES:
            raise ValueError(_("Solo las facturas ordinarias pueden marcarse como pagadas."))
        allowed = (SalesDocument.Status.CONFIRMED, SalesDocument.Status.SENT, SalesDocument.Status.OVERDUE)
        if invoice.status not in allowed:
            raise ValueError("La factura no puede marcarse como pagada en su estado actual.")
        invoice.status = SalesDocument.Status.PAID
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    def reopen(invoice: SalesDocument) -> SalesDocument:
        """
        Reverse PAID → SENT.
        Called by PaymentService.delete() when a payment that fully covered
        this invoice is deleted.
        """
        if invoice.doc_type != SalesDocument.DocType.INVOICE or invoice.ncf_type in SalesDocument.NOTE_TYPES:
            raise ValueError(_("Solo las facturas ordinarias pueden reabrirse."))
        if invoice.status != SalesDocument.Status.PAID:
            raise ValueError("Solo se pueden reabrir facturas en estado Pagada.")
        invoice.status = SalesDocument.Status.SENT
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    def cancel(invoice: SalesDocument) -> SalesDocument:
        """
        Cancel a confirmed/sent/overdue invoice.
        The e-NCF is retained (to appear in format 608) and the invoice is
        soft-deleted after status change.
        DRAFT invoices are just hard-deleted (no e-NCF was assigned).
        """
        if invoice.doc_type != SalesDocument.DocType.INVOICE:
            raise ValueError(_("Este documento no es una factura."))
        if invoice.status == SalesDocument.Status.PAID:
            raise ValueError(
                "No se puede anular una factura pagada. "
                "Emita una Nota de Crédito en su lugar."
            )
        if invoice.status == SalesDocument.Status.CANCELLED:
            raise ValueError("La factura ya está anulada.")

        invoice.status = SalesDocument.Status.CANCELLED
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    def mark_overdue_bulk(organization) -> int:
        """
        Mark all SENT invoices with a past due_date as OVERDUE.
        Intended to be called from a management command or Celery beat task.
        Returns the count of invoices updated.
        """
        today = timezone.now().date()
        updated = (
            SalesDocument.invoices
            .filter(
                organization=organization,
                status=SalesDocument.Status.SENT,
                due_date__lt=today,
            )
            .update(status=SalesDocument.Status.OVERDUE)
        )
        return updated


# ── QuotationService ──────────────────────────────────────────────────────────

class QuotationService:
    """
    State-machine transitions for Quotation documents.

    Lifecycle:
        DRAFT → CONFIRMED → SENT → ACCEPTED → CONVERTED (→ new Invoice)
                                 → REJECTED
                                 → EXPIRED
    """

    @staticmethod
    @transaction.atomic
    def confirm(quotation: SalesDocument) -> SalesDocument:
        """DRAFT → CONFIRMED. Assigns doc_number from DocumentSequence."""
        if quotation.doc_type != SalesDocument.DocType.QUOTATION:
            raise ValueError(_("Este documento no es una cotización."))
        if quotation.status != SalesDocument.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden confirmar cotizaciones en Borrador. "
                f"Estado actual: {quotation.get_status_display()}."
            )

        doc_number = DocumentSequence.generate(
            quotation.organization, DocumentSequence.DocType.QUOTATION
        )
        quotation.doc_number = doc_number
        quotation.status = SalesDocument.Status.CONFIRMED
        quotation.save(update_fields=["doc_number", "status", "updated_at"])
        return quotation

    @staticmethod
    def send(quotation: SalesDocument) -> SalesDocument:
        """CONFIRMED → SENT."""
        if quotation.status != SalesDocument.Status.CONFIRMED:
            raise ValueError(_("Solo se pueden enviar cotizaciones confirmadas."))
        quotation.status = SalesDocument.Status.SENT
        quotation.save(update_fields=["status", "updated_at"])
        return quotation

    @staticmethod
    def accept(quotation: SalesDocument) -> SalesDocument:
        """SENT → ACCEPTED."""
        if quotation.status != SalesDocument.Status.SENT:
            raise ValueError(_("Solo se pueden aceptar cotizaciones enviadas."))
        quotation.status = SalesDocument.Status.ACCEPTED
        quotation.save(update_fields=["status", "updated_at"])
        return quotation

    @staticmethod
    def reject(quotation: SalesDocument) -> SalesDocument:
        """SENT → REJECTED."""
        if quotation.status != SalesDocument.Status.SENT:
            raise ValueError(_("Solo se pueden rechazar cotizaciones enviadas."))
        quotation.status = SalesDocument.Status.REJECTED
        quotation.save(update_fields=["status", "updated_at"])
        return quotation

    @staticmethod
    def expire(quotation: SalesDocument) -> SalesDocument:
        """Any non-terminal status → EXPIRED."""
        terminal = (
            SalesDocument.Status.CONVERTED,
            SalesDocument.Status.REJECTED,
            SalesDocument.Status.CANCELLED,
            SalesDocument.Status.EXPIRED,
        )
        if quotation.status in terminal:
            raise ValueError(_("Esta cotización ya está en un estado terminal."))
        quotation.status = SalesDocument.Status.EXPIRED
        quotation.save(update_fields=["status", "updated_at"])
        return quotation

    @staticmethod
    @transaction.atomic
    def convert_to_invoice(quotation: SalesDocument, ncf_type: int) -> SalesDocument:
        """
        ACCEPTED → CONVERTED.

        Creates a new DRAFT SalesDocument copying customer, items, totals, currency
        and notes from the quotation. The NCF type is provided by the user.
        Returns the new SalesDocument.
        """
        if quotation.doc_type != SalesDocument.DocType.QUOTATION:
            raise ValueError(_("Este documento no es una cotización."))
        if quotation.status != SalesDocument.Status.ACCEPTED:
            raise ValueError(_("Solo se pueden convertir cotizaciones aceptadas."))

        invoice = SalesDocument.objects.create(
            doc_type=SalesDocument.DocType.INVOICE,
            organization=quotation.organization,
            customer=quotation.customer,
            ncf_type=ncf_type,
            issue_date=date.today(),
            due_date=quotation.due_date,
            payment_condition=quotation.payment_condition,
            currency=quotation.currency,
            exchange_rate=quotation.exchange_rate,
            notes=quotation.notes,
            terms=quotation.terms,
            status=SalesDocument.Status.DRAFT,
        )

        # Copy line items
        for item in quotation.items.all():
            SalesDocumentItem.objects.create(
                document=invoice,
                item=item.item,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                itbis_rate=item.itbis_rate,
            )

        # Mark quotation as converted
        quotation.status = SalesDocument.Status.CONVERTED
        quotation.save(update_fields=["status", "updated_at"])

        return invoice

    @staticmethod
    def expire_bulk(organization) -> int:
        """
        Mark all SENT quotations whose valid_until has passed as EXPIRED.
        Intended for a scheduled task. Returns count updated.
        """
        today = timezone.now().date()
        updated = (
            SalesDocument.quotations
            .filter(
                organization=organization,
                status__in=[SalesDocument.Status.CONFIRMED, SalesDocument.Status.SENT],
                valid_until__lt=today,
            )
            .update(status=SalesDocument.Status.EXPIRED)
        )
        return updated


# ── SaleOrderService ──────────────────────────────────────────────────────────

class SaleOrderService:
    """
    State-machine transitions for Sale Order documents.

    Lifecycle:
        DRAFT → CONFIRMED → DELIVERED → INVOICED
                          → CANCELLED
    """

    @staticmethod
    @transaction.atomic
    def confirm(order: SalesDocument) -> SalesDocument:
        """DRAFT → CONFIRMED. Assigns doc_number from DocumentSequence."""
        if order.doc_type != SalesDocument.DocType.SALE_ORDER:
            raise ValueError(_("Este documento no es una orden de venta."))
        if order.status != SalesDocument.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden confirmar órdenes en Borrador. "
                f"Estado actual: {order.get_status_display()}."
            )

        doc_number = DocumentSequence.generate(
            order.organization, DocumentSequence.DocType.SALE_ORDER
        )
        order.doc_number = doc_number
        order.status = SalesDocument.Status.CONFIRMED
        order.save(update_fields=["doc_number", "status", "updated_at"])
        return order

    @staticmethod
    def mark_delivered(order: SalesDocument, signed_by: str) -> SalesDocument:
        """CONFIRMED → DELIVERED. Records who signed the delivery."""
        if order.doc_type != SalesDocument.DocType.SALE_ORDER:
            raise ValueError(_("Este documento no es una orden de venta."))
        if order.status != SalesDocument.Status.CONFIRMED:
            raise ValueError(_("Solo se pueden marcar como entregadas órdenes confirmadas."))
        if not signed_by or not signed_by.strip():
            raise ValueError(_("Debe indicar el nombre de quien recibe la entrega."))

        order.signed_by = signed_by.strip()
        order.status = SalesDocument.Status.DELIVERED
        order.save(update_fields=["signed_by", "status", "updated_at"])
        return order

    @staticmethod
    def cancel(order: SalesDocument) -> SalesDocument:
        """DRAFT / CONFIRMED → CANCELLED."""
        if order.doc_type != SalesDocument.DocType.SALE_ORDER:
            raise ValueError(_("Este documento no es una orden de venta."))
        if order.status in (SalesDocument.Status.DELIVERED, SalesDocument.Status.INVOICED):
            raise ValueError(
                _("No se puede anular una orden entregada o facturada.")
            )
        if order.status == SalesDocument.Status.CANCELLED:
            raise ValueError(_("La orden ya está anulada."))

        order.status = SalesDocument.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        return order

    @staticmethod
    @transaction.atomic
    def consolidate_and_invoice(
        organization,
        customer,
        period_start: date,
        period_end: date,
        ncf_type: int,
        department=None,
    ) -> SalesDocument:
        """
        Consolidate all DELIVERED sale orders for a customer within a date range
        into a single new DRAFT Invoice.

        Each sale order becomes one invoice line:
          description = "Entrega {doc_number} – {delivery_date}"
          quantity    = 1
          unit_price  = order.subtotal  (pre-ITBIS)
          itbis_rate  = dominant rate from the order's items (or EXEMPT if mixed)

        If `department` is given, only orders assigned to that department are
        included. Pass None to include all departments.

        The new Invoice is returned in DRAFT status so the user can review it
        and then call NCFService.confirm() to assign the e-NCF.

        Raises ValueError if no eligible orders are found.
        """
        if customer.organization_id != organization.pk:
            raise ValueError(_("El cliente no pertenece a esta organizacion."))
        if department and (
            department.organization_id != organization.pk
            or department.customer_id != customer.pk
        ):
            raise ValueError(_("El departamento no pertenece al cliente y organizacion indicados."))

        qs = (
            SalesDocument.sale_orders
            .select_related("customer")
            .prefetch_related("items")
            .filter(
                organization=organization,
                customer=customer,
                status=SalesDocument.Status.DELIVERED,
                consolidated_into__isnull=True,
                delivery_date__gte=period_start,
                delivery_date__lte=period_end,
            )
        )
        if department is not None:
            qs = qs.filter(department=department)

        orders = list(qs.order_by("delivery_date", "doc_number"))

        if not orders:
            scope = (
                _("para el departamento «%(dept)s»") % {"dept": department.name}
                if department
                else _("para este cliente")
            )
            raise ValueError(
                _("No hay órdenes de venta entregadas pendientes de facturar "
                  "%(scope)s en el período indicado.") % {"scope": scope}
            )

        # Use the currency/exchange_rate of the first order (all should match)
        first = orders[0]

        dept_label = f" · Depto.: {department.name}" if department else ""
        invoice = SalesDocument.objects.create(
            doc_type=SalesDocument.DocType.INVOICE,
            organization=organization,
            customer=customer,
            ncf_type=ncf_type,
            issue_date=date.today(),
            payment_condition=SalesDocument.PaymentCondition.CREDIT,
            currency=first.currency,
            exchange_rate=first.exchange_rate,
            notes=_(
                f"Consolidación de {len(orders)} orden(es) de venta. "
                f"Período: {period_start} – {period_end}.{dept_label}"
            ),
            status=SalesDocument.Status.DRAFT,
        )

        for order in orders:
            # Determine the dominant ITBIS rate for this order's items
            rates = [item.itbis_rate for item in order.items.all()]
            dominant_rate = _dominant_itbis_rate(rates)

            date_str = order.delivery_date.strftime("%d/%m/%Y") if order.delivery_date else ""
            ref = order.doc_number or str(order.pk)[:8]

            SalesDocumentItem.objects.create(
                document=invoice,
                description=f"Entrega {ref} – {date_str}",
                quantity=1,
                unit_price=order.subtotal,
                itbis_rate=dominant_rate,
            )

            order.consolidated_into = invoice
            order.status = SalesDocument.Status.INVOICED
            order.save(update_fields=["consolidated_into", "status", "updated_at"])

        # Recompute invoice totals now that all items exist
        invoice.recompute_totals()

        return invoice


# ── PaymentService ────────────────────────────────────────────────────────────

class PaymentService:
    """
    Handles creation and deletion of multi-invoice payments.

    A Payment covers one or more invoices via PaymentAllocation rows.
    Accepted methods: TRANSFER and CHECK only.
    """

    _ZERO = _Decimal("0.00")
    _DEC  = _DecimalField(max_digits=14, decimal_places=2)

    @classmethod
    def _outstanding(cls, invoice: SalesDocument) -> _Decimal:
        """Return the current outstanding balance for an invoice."""
        paid = invoice.allocations.aggregate(
            t=_Coalesce(_Sum("amount"), cls._ZERO, output_field=cls._DEC)
        )["t"]
        return invoice.total - paid

    @staticmethod
    @transaction.atomic
    def register(
        organization,
        customer,
        payment_date,
        method: str,
        reference: str,
        notes: str,
        allocations: list,          # [{"invoice": Invoice, "amount": Decimal}, …]
    ) -> Payment:
        """
        Create a Payment header + PaymentAllocation rows atomically.

        Validates:
          - At least one allocation with amount > 0
          - Each allocation amount ≤ invoice outstanding balance
          - Invoice belongs to the same organization

        Auto-marks each invoice as PAID when its allocations fully cover its total.
        Returns the saved Payment instance.
        """
        if customer.organization_id != organization.pk:
            raise ValueError(_("El cliente no pertenece a esta organizacion."))
        if not allocations:
            raise ValueError(_("Debe aplicar el pago a al menos una factura."))

        supplied_ids = [a["invoice"].pk for a in allocations]
        if len(supplied_ids) != len(set(supplied_ids)):
            raise ValueError(_("Una factura no puede repetirse en el mismo pago."))
        locked = {
            inv.pk: inv
            for inv in SalesDocument.invoices.select_for_update().filter(pk__in=supplied_ids)
        }
        if set(locked) != set(supplied_ids):
            raise ValueError(_("Una de las facturas seleccionadas no existe o no esta disponible."))
        allocations = [
            {"invoice": locked[a["invoice"].pk], "amount": a["amount"]}
            for a in allocations
        ]

        total = sum(a["amount"] for a in allocations)
        if total <= 0:
            raise ValueError(_("El monto total del pago debe ser mayor a cero."))

        _zero = _Decimal("0.00")
        _dec = _DecimalField(max_digits=14, decimal_places=2)
        _agg = lambda inv: inv.allocations.aggregate(
            t=_Coalesce(_Sum("amount"), _zero, output_field=_dec)
        )["t"]

        # Validate all allocations and cache each invoice's current balance.
        for alloc in allocations:
            inv = alloc["invoice"]
            amt = alloc["amount"]

            if inv.organization_id != organization.pk:
                raise ValueError(_(f"La factura {inv.display_number} no pertenece a esta organización."))

            if inv.customer_id != customer.pk:
                raise ValueError(_(f"La factura {inv.display_number} no pertenece al cliente seleccionado."))

            if inv.ncf_type in SalesDocument.NOTE_TYPES:
                raise ValueError(_("Los pagos no pueden aplicarse a notas de credito o debito."))

            if inv.status not in (
                SalesDocument.Status.CONFIRMED,
                SalesDocument.Status.SENT,
                SalesDocument.Status.OVERDUE,
            ):
                raise ValueError(_(f"La factura {inv.display_number} no esta pendiente de cobro."))

            if amt <= _zero:
                raise ValueError(_(f"El monto para {inv.display_number} debe ser mayor a cero."))

            already_paid = _agg(inv)
            balance = inv.total - already_paid
            alloc["_balance"] = balance  # carry forward — avoids a second DB query

            if amt > balance:
                raise ValueError(
                    _(f"El monto {amt} excede el saldo pendiente ({balance:.2f}) "
                      f"de la factura {inv.display_number}.")
                )

        payment = Payment.objects.create(
            organization=organization,
            customer=customer,
            amount=total,
            date=payment_date,
            method=method,
            reference=reference,
            notes=notes,
        )

        for alloc in allocations:
            inv = alloc["invoice"]
            amt = alloc["amount"]

            PaymentAllocation.objects.create(
                payment=payment,
                invoice=inv,
                amount=amt,
            )

            # Use the cached balance; subtract the amount just applied.
            remaining = alloc["_balance"] - amt
            if remaining <= _zero:
                try:
                    NCFService.mark_paid(inv)
                except ValueError as exc:
                    logger.warning(
                        "mark_paid skipped for invoice %s after payment %s: %s",
                        inv.pk, payment.pk, exc,
                    )

        return payment

    @staticmethod
    @transaction.atomic
    def delete(payment: Payment) -> None:
        """
        Delete a payment and reverse all of its effects:
          - Collect affected invoices before deletion
          - Delete the payment (CASCADE removes allocations)
          - Re-open any invoice that was PAID solely due to this payment
        """
        _zero = _Decimal("0.00")

        # Snapshot affected invoices before deletion
        affected = list(
            payment.allocations.select_related("invoice").values_list("invoice_id", flat=True)
        )

        payment.hard_delete()  # real SQL DELETE → CASCADE removes allocations

        # Re-open invoices whose coverage is now incomplete
        for inv_pk in affected:
            try:
                inv = SalesDocument.objects.get(pk=inv_pk)
            except SalesDocument.DoesNotExist:
                continue

            if inv.status != SalesDocument.Status.PAID:
                continue

            outstanding = _Coalesce(_Sum("amount"), _zero, output_field=_DecimalField(max_digits=14, decimal_places=2))
            still_paid = inv.allocations.aggregate(t=outstanding)["t"]
            if still_paid < inv.total:
                try:
                    NCFService.reopen(inv)
                except ValueError as exc:
                    logger.warning(
                        "reopen skipped for invoice %s after deleting payment %s: %s",
                        inv_pk, payment.pk, exc,
                    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dominant_itbis_rate(rates: list) -> str:
    """
    Return the single ITBISRate that applies to a group of items.
    If all items share the same rate, use that. Otherwise fall back to EXEMPT
    to avoid double-taxing a mixed order (the accountant can adjust manually).
    """
    unique = set(rates)
    if len(unique) == 1:
        return unique.pop()
    return SalesDocumentItem.ITBISRate.EXEMPT
