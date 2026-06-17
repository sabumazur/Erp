import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from apps.core.models import DocumentSequence
from .models import (
    PurchaseDocument,
    PurchaseDocumentItem,
    SupplierPayment,
    SupplierPaymentAllocation,  # used in create_payment bulk-outstanding and delete_payment
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0.00")
_DEC = DecimalField(max_digits=14, decimal_places=2)


def _duplicate_ncf_error(ncf):
    return _(f"El NCF Â«{ncf}Â» ya estÃ¡ registrado en esta organizaciÃ³n.")


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
        number = DocumentSequence.generate(
            po.organization, "PURCHASE_ORDER",
            defaults={"prefix": "OC", "include_year": False, "padding": 5},
        )
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

        # bulk_create bypasses save(), so compute() must be called explicitly
        # to populate line_total/itbis_amount/line_total_with_itbis.
        new_lines = []
        for line in po.items.all():
            new_line = PurchaseDocumentItem(
                purchase_document=si,
                item=line.item,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                itbis_rate=line.itbis_rate,
            )
            new_line.compute()
            new_lines.append(new_line)
        PurchaseDocumentItem.objects.bulk_create(new_lines)

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

        invoice.supplier_rnc = invoice.supplier.rnc_cedula
        invoice.status = PurchaseDocument.Status.CONFIRMED
        try:
            invoice.save(update_fields=["supplier_rnc", "status", "updated_at"])
        except IntegrityError as exc:
            raise ValueError(_duplicate_ncf_error(invoice.supplier_ncf)) from exc

        # REFACTOR PQ-004: replace N individual Item.update() calls with a
        # single bulk_update.  Accumulate mutations in Python, then flush once.
        from apps.items.models import Item
        items_to_update = []
        for line in invoice.items.select_related("item").all():
            if line.item_id is None:
                continue
            item = line.item
            item.cost_price = line.unit_price
            if item.default_supplier_id is None:
                item.default_supplier = invoice.supplier
            items_to_update.append(item)
        if items_to_update:
            Item.objects.bulk_update(items_to_update, ["cost_price", "default_supplier"])

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

        # REFACTOR PQ-07: bulk-fetch all existing allocation totals in ONE query
        # instead of calling inv.allocations.aggregate() once per invoice inside
        # the loop below.  With N invoices this was N extra queries; now it's 1.
        existing_paid = {
            row["supplier_invoice_id"]: row["paid"]
            for row in SupplierPaymentAllocation.objects.filter(
                supplier_invoice_id__in=supplied_ids
            ).values("supplier_invoice_id").annotate(
                paid=Coalesce(Sum("amount"), _ZERO, output_field=_DEC)
            )
        }

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
            balance = inv.total - existing_paid.get(inv.pk, _ZERO)
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
                inv.status = PurchaseDocument.Status.PAID
                inv.save(update_fields=["status", "updated_at"])

        return payment

    @staticmethod
    @transaction.atomic
    def delete_payment(payment: SupplierPayment) -> None:
        affected = list(
            payment.allocations.values_list("supplier_invoice_id", flat=True)
        )
        payment.hard_delete()

        # REFACTOR PQ-08: replaced N×get() + N×aggregate() with a single
        # bulk fetch followed by a single aggregation query, then a bulk update.
        # Before: 2N DB queries for N affected invoices.
        # After:  3 DB queries regardless of N.
        paid_invoices = {
            inv.pk: inv
            for inv in PurchaseDocument.objects.filter(
                pk__in=affected,
                status=PurchaseDocument.Status.PAID,
            )
        }
        if not paid_invoices:
            return

        # One aggregate query: sum remaining allocations for all affected invoices.
        remaining_paid = {
            row["supplier_invoice_id"]: row["t"]
            for row in SupplierPaymentAllocation.objects.filter(
                supplier_invoice_id__in=list(paid_invoices.keys())
            ).values("supplier_invoice_id").annotate(
                t=Coalesce(Sum("amount"), _ZERO, output_field=_DEC)
            )
        }

        reopen_pks = []
        for inv_pk, inv in paid_invoices.items():
            still_paid = remaining_paid.get(inv_pk, _ZERO)
            if still_paid < inv.total:
                reopen_pks.append(inv_pk)

        if reopen_pks:
            try:
                PurchaseDocument.objects.filter(pk__in=reopen_pks).update(
                    status=PurchaseDocument.Status.CONFIRMED
                )
            except Exception as exc:
                logger.warning("Could not reopen invoices %s: %s", reopen_pks, exc)
