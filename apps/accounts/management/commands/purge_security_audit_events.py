from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import SecurityAuditEvent


class Command(BaseCommand):
    help = "Delete security audit events older than the configured retention period."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--no-input", action="store_true")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=settings.SECURITY_AUDIT_RETENTION_DAYS)
        queryset = SecurityAuditEvent.objects.filter(created_at__lt=cutoff)
        count = queryset.count()
        if options["dry_run"]:
            self.stdout.write(f"{count} security audit event(s) would be deleted.")
            return
        if not options["no_input"]:
            answer = input(f"Delete {count} security audit event(s) older than {cutoff.date()}? [y/N] ")
            if answer.lower() not in {"y", "yes"}:
                raise CommandError("Deletion cancelled.")
        SecurityAuditEvent.objects.all().purge_before(cutoff)
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} security audit event(s)."))
