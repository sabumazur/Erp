"""
Management command to transition past-due invoices to OVERDUE status.
Run daily via cron or Celery beat:
    python manage.py mark_overdue_invoices
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import Organization
from apps.invoices.services import NCFService


class Command(BaseCommand):
    help = "Mark all sent invoices past their due date as OVERDUE."

    def handle(self, *args, **options):
        total = 0
        for org in Organization.objects.filter(is_active=True):
            count = NCFService.mark_overdue_bulk(org)
            if count:
                self.stdout.write(f"  {org}: {count} factura(s) marcada(s) como VENCIDA.")
            total += count
        self.stdout.write(self.style.SUCCESS(f"Listo. {total} factura(s) actualizadas en total."))
