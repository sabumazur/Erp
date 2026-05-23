"""
Deletes all sales documents (invoices, quotations, sale orders) across all
organizations, along with their payments, line items, and history records.
Resets DocumentSequence and NCFSequence counters to zero.

Usage:
    python manage.py empty_sale_orders
    python manage.py empty_sale_orders --no-input
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Delete all invoices, quotations, and sale orders; reset document sequences."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Skip the confirmation prompt.",
        )

    def handle(self, *args, **options):
        from apps.invoices.models import (
            SalesDocument, SalesDocumentItem, Payment, PaymentAllocation,
            DocumentSequence, NCFSequence,
        )

        counts = {
            "invoices":    SalesDocument.invoices.count(),
            "quotations":  SalesDocument.quotations.count(),
            "sale_orders": SalesDocument.sale_orders.count(),
            "payments":    Payment.all_objects.count(),
        }
        total_docs = counts["invoices"] + counts["quotations"] + counts["sale_orders"]

        if not options["no_input"]:
            self.stdout.write(
                f"\nThis will permanently delete:\n"
                f"  {counts['invoices']} invoice(s)\n"
                f"  {counts['quotations']} quotation(s)\n"
                f"  {counts['sale_orders']} sale order(s)\n"
                f"  {counts['payments']} payment(s)\n"
                f"And reset all DocumentSequence and NCFSequence counters.\n"
            )
            confirm = input("Type 'yes' to continue: ")
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        with transaction.atomic():
            alloc_deleted, _ = PaymentAllocation.objects.all().delete()
            pay_hist_deleted, _ = Payment.history.model.objects.all().delete()
            pay_deleted, _ = Payment.all_objects.all().delete()

            items_deleted, _ = SalesDocumentItem.objects.all().delete()

            inv_hist_deleted, _ = SalesDocument.history.model.objects.all().delete()

            # Null self-referential FKs before deletion to avoid constraint errors.
            SalesDocument.objects.all().update(consolidated_into=None, encf_modified=None)
            SalesDocument.objects.all().delete()

            doc_seqs_reset = DocumentSequence.objects.all().update(current_seq=0)
            ncf_seqs_reset = NCFSequence.objects.all().update(current_seq=0)

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {total_docs} document(s) "
                f"({counts['invoices']} invoices, {counts['quotations']} quotations, "
                f"{counts['sale_orders']} sale orders), "
                f"{items_deleted} line item(s), "
                f"{pay_deleted} payment(s), "
                f"{alloc_deleted} allocation(s), "
                f"{inv_hist_deleted + pay_hist_deleted} history record(s). "
                f"Reset {doc_seqs_reset} document sequence(s) and "
                f"{ncf_seqs_reset} NCF sequence(s)."
            )
        )
