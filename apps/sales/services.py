"""
apps/invoices/services.py
Business-logic services for the invoices app.

All public functions assume they are called from within a request/view context
where request.organization is already set.
"""
import logging
from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from decimal import Decimal as _Decimal

from django.db.models import Exists as _Exists, OuterRef as _OuterRef, Sum as _Sum
from django.db.models.functions import Coalesce as _Coalesce
from django.db.models import DecimalField as _DecimalField

from apps.core.models import DocumentSequence
from .models import SalesDocument, SalesDocumentItem, NCFSequence, Payment, PaymentAllocation

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
            quotation.organization, "QUOTATION",
            defaults={"prefix": "COT", "include_year": True, "padding": 4},
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

        customer = quotation.customer
        today = date.today()
        if customer.payment_term_id and customer.payment_term.days_due:
            due_date = today + timedelta(days=customer.payment_term.days_due)
        else:
            due_date = quotation.due_date

        invoice = SalesDocument.objects.create(
            doc_type=SalesDocument.DocType.INVOICE,
            organization=quotation.organization,
            customer=customer,
            ncf_type=ncf_type,
            issue_date=today,
            due_date=due_date,
            payment_condition=quotation.payment_condition,
            currency=quotation.currency,
            exchange_rate=quotation.exchange_rate,
            notes=quotation.notes,
            terms=quotation.terms,
            status=SalesDocument.Status.DRAFT,
        )

        # REFACTOR SAL-003: bulk_create all line items in 1 INSERT instead of N.
        # bulk_create bypasses the post_save signal, so recompute_totals() is
        # called once explicitly. quotation.items is already prefetch_related
        # by the caller (get_object_or_404 with prefetch_related("items")).
        new_items = [
            SalesDocumentItem(
                document=invoice,
                item=item.item,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                itbis_rate=item.itbis_rate,
            )
            for item in quotation.items.all()
        ]
        for new_item in new_items:
            new_item.compute()
        SalesDocumentItem.objects.bulk_create(new_items)
        invoice.recompute_totals()

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
            order.organization, "SALE_ORDER",
            defaults={"prefix": "OV", "include_year": True, "padding": 4},
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
        Consolidate all DRAFT sale orders for a customer within a date range
        into a single new DRAFT Invoice.

        One invoice line is created per unique catalog Item across all orders:
          description = item.name
          quantity    = sum of quantities for that item across all orders
          unit_price  = item.unit_price  (from Item model)
          itbis_rate  = item.itbis_rate  (from Item model)

        Free-text lines (no linked Item) are skipped.

        If `department` is given, only orders assigned to that department are
        included. Pass None to include all departments.

        The new Invoice is returned in DRAFT status so the user can review it
        and then call NCFService.confirm() to assign the e-NCF.

        Raises ValueError if no eligible orders are found or no catalog items exist.
        """
        if customer.organization_id != organization.pk:
            raise ValueError(_("El cliente no pertenece a esta organizacion."))
        if department and (
            department.organization_id != organization.pk
            or department.customer_id != customer.pk
        ):
            raise ValueError(_("El departamento no pertenece al cliente y organizacion indicados."))

        has_items = _Exists(
            SalesDocumentItem.objects.filter(document=_OuterRef("pk"))
        )
        qs = (
            SalesDocument.sale_orders
            .select_for_update()
            .select_related("customer")
            .filter(
                organization=organization,
                customer=customer,
                status=SalesDocument.Status.DRAFT,
                consolidated_into__isnull=True,
                issue_date__gte=period_start,
                issue_date__lte=period_end,
            )
            .filter(has_items)
        )
        if department is not None:
            qs = qs.filter(department=department)

        orders = list(qs.order_by("issue_date", "doc_number"))

        if not orders:
            scope = (
                _("para el departamento «%(dept)s»") % {"dept": department.name}
                if department
                else _("para este cliente")
            )
            raise ValueError(
                _("No hay órdenes de venta pendientes de facturar "
                  "%(scope)s en el período indicado.") % {"scope": scope}
            )

        # Aggregate quantities per catalog Item across all orders
        item_agg = list(
            SalesDocumentItem.objects
            .filter(document__in=orders, item__isnull=False)
            .values('item_id', 'item__name', 'item__unit_price', 'item__itbis_rate')
            .annotate(total_qty=_Sum('quantity'))
            .order_by('item__name')
        )

        if not item_agg:
            raise ValueError(
                _("Las órdenes seleccionadas no contienen artículos de catálogo para facturar.")
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

        for row in item_agg:
            SalesDocumentItem.objects.create(
                document=invoice,
                item_id=row['item_id'],
                description=row['item__name'],
                quantity=row['total_qty'],
                unit_price=row['item__unit_price'],
                itbis_rate=row['item__itbis_rate'],
            )

        for order in orders:
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


# ── CustomerService ───────────────────────────────────────────────────────────

class CustomerService:
    """Read-only account summary for the customer detail page."""

    @staticmethod
    def get_account_summary(customer, organization) -> dict:
        """
        Return balance, aging breakdown, and recent payments for a customer.

        Keys returned match the template context in CustomerDetailView:
          invoices, total_invoiced, total_paid, balance, overdue,
          aging_breakdown, recent_payments, credit_available
        """
        from decimal import Decimal
        from django.db.models import DecimalField, Sum
        from django.db.models.functions import Coalesce
        from .models import Payment  # avoid circular at module level

        _zero = Decimal("0.00")
        _dec_field = DecimalField(max_digits=14, decimal_places=2)

        invoices = list(
            SalesDocument.invoices.filter(organization=organization, customer=customer)
            .exclude(status__in=[SalesDocument.Status.DRAFT, SalesDocument.Status.CANCELLED])
            .with_signed_totals()
            .annotate(
                paid_amount=Coalesce(Sum("allocations__amount"), _zero, output_field=_dec_field)
            )
            .select_related("customer")
            .order_by("-issue_date")
        )

        for inv in invoices:
            inv.line_balance = inv.signed_total - inv.paid_amount

        total_invoiced = sum((inv.signed_total for inv in invoices), _zero)
        total_paid = sum((inv.paid_amount for inv in invoices), _zero)
        balance = total_invoiced - total_paid
        overdue = sum(
            inv.line_balance for inv in invoices if inv.status == SalesDocument.Status.OVERDUE
        )

        _aging = {b: _zero for b in SalesDocument.AgingBucket.values}
        for inv in invoices:
            if inv.line_balance > _zero:
                _aging[inv.aging_bucket] += inv.line_balance
        aging_breakdown = [
            {"label": SalesDocument.AgingBucket(b).label, "amount": _aging[b], "bucket": b}
            for b in SalesDocument.AgingBucket.values
        ]

        recent_payments = list(
            Payment.objects.filter(customer=customer, organization=organization)
            .prefetch_related("allocations__invoice")
            .order_by("-date", "-created_at")[:30]
        )

        credit_available = (
            (customer.credit_limit - balance)
            if customer.credit_limit is not None
            else None
        )

        return {
            "invoices": invoices,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "balance": balance,
            "overdue": overdue,
            "aging_breakdown": aging_breakdown,
            "recent_payments": recent_payments,
            "credit_available": credit_available,
        }


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
