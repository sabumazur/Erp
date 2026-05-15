"""
Wipes ALL database records, preserving (and restoring) the superuser account.

Usage:
    python manage.py reset_db
    python manage.py reset_db --no-input
"""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Wipe all data and restore the superuser account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-input",
            action="store_true",
            dest="no_input",
            help="Skip the confirmation prompt.",
        )

    def handle(self, *args, **options):
        if not options["no_input"]:
            self.stdout.write(
                "\nThis will DELETE all database records (superuser will be restored).\n"
            )
            confirm = input("Type 'yes' to continue: ")
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("Aborted."))
                return

        from apps.accounts.models import User as _User

        sv_email = sv_fn = sv_ln = sv_pw_hash = None
        try:
            su = _User.all_objects.filter(is_superuser=True).first()
            if su:
                sv_email   = su.email
                sv_fn      = su.first_name
                sv_ln      = su.last_name
                sv_pw_hash = su.password
        except Exception:
            pass

        if not sv_email:
            sv_email   = "admin@sabsys.com"
            sv_fn      = "Admin"
            sv_ln      = "SabSys"
            sv_pw_hash = make_password("Admin1234!")

        # Must run outside the main transaction — ALTER TABLE not allowed with
        # pending trigger events in PostgreSQL.
        self._patch_orphaned_columns()

        with transaction.atomic():
            self._wipe()
            self._restore_superuser(sv_email, sv_fn, sv_ln, sv_pw_hash)

        self.stdout.write(self.style.SUCCESS("Reset complete."))

    def _patch_orphaned_columns(self):
        from django.db import connection

        with connection.cursor() as cur:
            cur.execute(
                "ALTER TABLE invoices_customer "
                "ALTER COLUMN default_payment_method SET DEFAULT 'TRANSFER'"
            )

    def _wipe(self):
        from apps.invoices.models import (
            Customer, Invoice, InvoiceItem, Payment, PaymentAllocation,
            PaymentTerm, NCFSequence, DocumentSequence, CustomerDepartment,
        )
        from apps.items.models import Item, ItemCodeSequence
        from apps.core.models import Module, Notification
        from apps.accounts.models import User, Organization, Team, Membership, Invitation

        self.stdout.write("Wiping database...")

        Customer.history.model.objects.all().delete()
        Invoice.history.model.objects.all().delete()
        Payment.history.model.objects.all().delete()

        PaymentAllocation.objects.all().delete()
        Payment.all_objects.all().delete()
        InvoiceItem.objects.all().delete()

        Invoice.objects.all().update(encf_modified=None, consolidated_into=None)
        Invoice.objects.all().delete()

        CustomerDepartment.all_objects.all().delete()
        Customer.all_objects.all().delete()
        NCFSequence.objects.all().delete()
        DocumentSequence.objects.all().delete()
        ItemCodeSequence.objects.all().delete()
        Item.all_objects.all().delete()
        PaymentTerm.objects.all().delete()
        Notification.all_objects.all().delete()
        Invitation.all_objects.all().delete()
        Membership.all_objects.all().delete()
        Team.all_objects.all().delete()
        Organization.all_objects.all().delete()
        User.all_objects.all().delete()
        Module.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("  Wipe complete."))

    def _restore_superuser(self, email, first_name, last_name, pw_hash):
        from apps.accounts.models import User, Organization

        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )
        user.password = pw_hash
        user.save()  # fires post_save → auto-creates default Org + OWNER Membership

        org = Organization.objects.get(owner=user)
        self.stdout.write(
            self.style.SUCCESS(f"  Superuser '{email}' restored. Org: '{org.name}'")
        )
