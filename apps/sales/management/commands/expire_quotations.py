"""
Management command to expire past-due quotations and sale orders.
Run daily via cron or Celery beat:
    python manage.py expire_quotations
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import Organization
from apps.invoices.services import QuotationService


class Command(BaseCommand):
    help = "Mark confirmed/sent quotations whose valid_until has passed as EXPIRED."

    def handle(self, *args, **options):
        total = 0
        for org in Organization.objects.filter(is_active=True):
            count = QuotationService.expire_bulk(org)
            if count:
                self.stdout.write(f"  {org}: {count} cotización(es) marcada(s) como EXPIRADA.")
            total += count
        self.stdout.write(self.style.SUCCESS(f"Listo. {total} cotización(es) actualizadas en total."))
