import os
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = "Set the django.contrib.sites domain from RAILWAY_PUBLIC_DOMAIN."

    def handle(self, *args, **kwargs):
        domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
        if not domain:
            self.stdout.write("RAILWAY_PUBLIC_DOMAIN not set — skipping site update.")
            return

        site, created = Site.objects.update_or_create(
            id=1,
            defaults={"domain": domain, "name": "SabSys"},
        )
        action = "Created" if created else "Updated"
        self.stdout.write(f"{action} site → {domain}")
