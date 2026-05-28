import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from .models import (
    PurchaseDocument,
    PurchaseDocumentItem,
    PurchaseSequence,
    SupplierPayment,
    SupplierPaymentAllocation,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0.00")
_DEC = DecimalField(max_digits=14, decimal_places=2)


# ── PurchaseOrderService ──────────────────────────────────────────────────────


class PurchaseOrderService:

    @staticmethod
    @transaction.atomic
    def confirm(po: PurchaseDocument) -> PurchaseDocument:
        if po.doc_type != PurchaseDocument.DocType.PURCHASE_ORDER:
            raise ValueError(_("Este documento no es una orden de compra."))
        if po.status != PurchaseDocument.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden confirmar órdenes en Borrador. "
                f"Estado actual: {po.get_status_display()}."
            )
        number = PurchaseSequence.generate(po.organization)
        po.number = number
        po.status = PurchaseDocument.Status.CONFIRMED
        po.save(update_fields=["number", "status", "updated_at"])
        return po

    @staticmethod
    @transaction.atomic
    def receive_and_invoice(po: PurchaseDocument):
        if po.doc_type != PurchaseDocument.DocType.PURCHASE_ORDER:
            raise ValueError(_("Este documento no es una orden de compra."))
        if po.status != PurchaseDocument.Status.CONFIRMED:
            raise ValueError(_("Solo se pueden recibir órdenes confirmadas."))

        po.status = PurchaseDocument.Status.RECEIVED
        po.save(update_fields=["status", "updated_at"])

        # Calculate due date from supplier payment term
        due_date = None
        if po.supplier.payment_term_id and po.supplier.payment_term.days_due:
            due_date = date.today() + timedelta(days=po.supplier.payment_term.days_due)

        si = PurchaseDocument.objects.create(
            doc_type=PurchaseDocument.DocType.SUPPLIER_INVOICE,
            organization=po.organization,
            supplier=po.supplier,
            status=PurchaseDocument.Status.DRAFT,
            issue_date=date.today(),
            due_date=due_date,
            currency=po.currency,
            exchange_rate=po.exchange_rate,
            linked_purchase_order=po,
            notes=f"Generada desde {po.number}",
        )

        for line in po.items.all():
            PurchaseDocumentItem.objects.create(
                purchase_document=si,
                item=line.item,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                itbis_rate=line.itbis_rate,
            )

        si.recompute_totals()
        return po, si

    @staticmethod
    @transaction.atomic
    def cancel(po: PurchaseDocument) -> PurchaseDocument:
        if po.doc_type != PurchaseDocument.DocType.PURCHASE_ORDER:
            raise ValueError(_("Este documento no es una orden de compra."))
        if po.status in (PurchaseDocument.Status.RECEIVED, PurchaseDocument.Status.CANCELLED):
            raise ValueError(
                _("No se puede anular una orden recibida o ya anulada.")
            )
        po.status = PurchaseDocument.Status.CANCELLED
        po.save(update_fields=["status", "updated_at"])
        return po


# ── SupplierInvoiceService ────────────────────────────────────────────────────


class SupplierInvoiceService:

    @staticmethod
    @transaction.atomic
    def confirm(invoice: PurchaseDocument) -> PurchaseDocument:
        if invoice.doc_type != PurchaseDocument.DocType.SUPPLIER_INVOICE:
            raise ValueError(_("Este documento no es una factura de proveedor."))
        if invoice.status != PurchaseDocument.Status.DRAFT:
            raise ValueError(
                f"Solo se pueden confirmar facturas en Borrador. "
                f"Estado actual: {invoice.get_status_display()}."
            )
        if not invoice.supplier_ncf:
            raise ValueError(_("Debe ingresar el NCF del proveedor antes de confirmar."))

        # Check NCF uniqueness in org (excluding self, excluding blank)
        duplicate = (
            PurchaseDocument.all_objects.filter(
                organization=invoice.organization,
                supplier_ncf=invoice.supplier_ncf,
                deleted_at__isnull=True,
            )
            .exclude(pk=invoice.pk)
            .exists()
        )
        if duplicate:
            raise ValueError(
                _(f"El NCF «{invoice.supplier_ncf}» ya está registrado en esta organización.")
            )

        invoice.supplier_rnc = invoice.supplier.id_number
        invoice.status = PurchaseDocument.Status.CONFIRMED
        invoice.save(update_fields=["supplier_rnc", "status", "updated_at"])

        # Update item cost_price and default_supplier
        from apps.items.models import Item
        for line in invoice.items.select_related("item").all():
            if line.item_id is None:
                continue
            item = line.item
            update_fields = ["updated_at"]
            item.cost_price = line.unit_price
            update_fields.append("cost_price")
            if item.default_supplier_id is None:
                item.default_supplier = invoice.supplier
                update_fields.append("default_supplier")
            Item.objects.filter(pk=item.pk).update(
                cost_price=item.cost_price,
                default_supplier_id=item.default_supplier_id,
            )

        return invoice

    @staticmethod
    @transaction.atomic
    def cancel(invoice: PurchaseDocument) -> PurchaseDocument:
        if invoice.doc_type != PurchaseDocument.DocType.SUPPLIER_INVOICE:
            raise ValueError(_("Este documento no es una factura de proveedor."))
        if invoice.status == PurchaseDocument.Status.CANCELLED:
            raise ValueError(_("La factura ya está anulada."))
        if invoice.status == PurchaseDocument.Status.PAID:
            raise ValueError(_("No se puede anular una factura pagada."))
        if invoice.allocations.exists():
            raise ValueError(_("No se puede anular una factura con pagos aplicados."))
        invoice.status = PurchaseDocument.Status.CANCELLED
        invoice.save(update_fields=["status", "updated_at"])
        return invoice

    @staticmethod
    @transaction.atomic
    def reopen(invoice: PurchaseDocument) -> PurchaseDocument:
        if invoice.doc_type != PurchaseDocument.DocType.SUPPLIER_INVOICE:
            raise ValueError(_("Este documento no es una factura de proveedor."))
        if invoice.status != PurchaseDocument.Status.CANCELLED:
            raise ValueError(_("Solo se pueden reabrir facturas anuladas."))
        if invoice.allocations.exists():
            raise ValueError(_("No se puede reabrir una factura con pagos aplicados."))
        invoice.status = PurchaseDocument.Status.DRAFT
        invoice.save(update_fields=["status", "updated_at"])
        return invoice


# ── SupplierPaymentService ────────────────────────────────────────────────────


class SupplierPaymentService:

    @staticmethod
    @transaction.atomic
    def create_payment(
        supplier,
        org,
        payment_date,
        method: str,
        reference: str,
        notes: str,
        allocations: list,
    ) -> SupplierPayment:
        if supplier.organization_id != org.pk:
            raise ValueError(_("El proveedor no pertenece a esta organización."))
        if not allocations:
            raise ValueError(_("Debe aplicar el pago a al menos una factura."))

        supplied_ids = [a["invoice"].pk for a in allocations]
        if len(supplied_ids) != len(set(supplied_ids)):
            raise ValueError(_("Una factura no puede repetirse en el mismo pago."))

        locked = {
            inv.pk: inv
            for inv in PurchaseDocument.supplier_invoices.select_for_update().filter(pk__in=supplied_ids)
        }
        if set(locked) != set(supplied_ids):
            raise ValueError(_("Una de las facturas seleccionadas no existe."))

        allocations = [
            {"invoice": locked[a["invoice"].pk], "amount": a["amount"]}
            for a in allocations
        ]

        def _outstanding(inv):
            paid = inv.allocations.aggregate(
                t=Coalesce(Sum("amount"), _ZERO, output_field=_DEC)
            )["t"]
            return inv.total - paid

        for alloc in allocations:
            inv = alloc["invoice"]
            amt = alloc["amount"]
            if inv.organization_id != org.pk:
                raise ValueError(_(f"La factura {inv.display_number} no pertenece a esta organización."))
            if inv.supplier_id != supplier.pk:
                raise ValueError(_(f"La factura {inv.display_number} no pertenece al proveedor seleccionado."))
            if inv.status not in (PurchaseDocument.Status.CONFIRMED, PurchaseDocument.Status.PAID):
                raise ValueError(_(f"La factura {inv.display_number} no está pendiente de pago."))
            if amt <= _ZERO:
                raise ValueError(_(f"El monto para {inv.display_number} debe ser mayor a cero."))
            balance = _outstanding(inv)
            alloc["_balance"] = balance
            if amt > balance:
                raise ValueError(
                    _(f"El monto {amt} excede el saldo pendiente ({balance:.2f}) "
                      f"de la factura {inv.display_number}.")
                )

        total = sum(a["amount"] for a in allocations)
        if total <= _ZERO:
            raise ValueError(_("El monto total del pago debe ser mayor a cero."))

        payment = SupplierPayment.objects.create(
            organization=org,
            supplier=supplier,
            amount=total,
            date=payment_date,
            method=method,
            reference=reference,
            notes=notes,
        )

        for alloc in allocations:
            inv = alloc["invoice"]
            amt = alloc["amount"]
            SupplierPaymentAllocation.objects.create(
                payment=payment,
                supplier_invoice=inv,
                amount=amt,
            )
            remaining = alloc["_balance"] - amt
            if remaining <= _ZERO:
                try:
                    inv.status = PurchaseDocument.Status.PAID
                    inv.save(update_fields=["status", "updated_at"])
                except Exception as exc:
                    logger.warning("Could not mark invoice %s PAID: %s", inv.pk, exc)

        return payment

    @staticmethod
    @transaction.atomic
    def delete_payment(payment: SupplierPayment) -> None:
        affected = list(
            payment.allocations.values_list("supplier_invoice_id", flat=True)
        )
        payment.hard_delete()

        for inv_pk in affected:
            try:
                inv = PurchaseDocument.objects.get(pk=inv_pk)
            except PurchaseDocument.DoesNotExist:
                continue
            if inv.status != PurchaseDocument.Status.PAID:
                continue
            still_paid = inv.allocations.aggregate(
                t=Coalesce(Sum("amount"), _ZERO, output_field=_DEC)
            )["t"]
            if still_paid < inv.total:
                try:
                    inv.status = PurchaseDocument.Status.CONFIRMED
                    inv.save(update_fields=["status", "updated_at"])
                except Exception as exc:
                    logger.warning("Could not reopen invoice %s: %s", inv_pk, exc)
