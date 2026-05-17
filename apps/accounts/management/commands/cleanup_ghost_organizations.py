from django.core.management.base import BaseCommand

from apps.accounts.models import Organization, Membership


class Command(BaseCommand):
    help = (
        "Remove empty auto-created workspaces that belong to invited users. "
        "An org is considered a ghost if it has exactly one member (OWNER) "
        "and contains no customers, invoices, or payments. "
        "Safe to run multiple times."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        removed = 0

        for org in Organization.objects.prefetch_related("memberships").iterator():
            memberships = list(org.memberships.all())
            if len(memberships) != 1:
                continue
            if memberships[0].role != Membership.Role.OWNER:
                continue

            has_data = (
                org.customers.exists()
                or org.invoices.exists()
                or org.payments.exists()
            )
            if has_data:
                continue

            label = f"{org.name!r}  pk={org.pk}  owner={memberships[0].user.email}"
            if dry_run:
                self.stdout.write(f"[DRY RUN] would delete: {label}")
            else:
                org.hard_delete()
                self.stdout.write(f"Deleted: {label}")
            removed += 1

        verb = "Would remove" if dry_run else "Removed"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verb} {removed} ghost organization(s)."
        ))
