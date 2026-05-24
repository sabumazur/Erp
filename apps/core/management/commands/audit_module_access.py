from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Team
from apps.core.models import Module


class Command(BaseCommand):
    help = "Audit module access configuration without modifying any grants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit unsuccessfully when audit findings are reported.",
        )

    def handle(self, *args, **options):
        findings = 0

        if not Module.objects.filter(slug="sales").exists():
            findings += 1
            self.stdout.write(
                self.style.WARNING("[MISSING] Canonical module 'sales' does not exist.")
            )

        unrestricted = Team.objects.filter(modules__isnull=True).select_related(
            "organization"
        )
        for team in unrestricted:
            findings += 1
            self.stdout.write(
                self.style.WARNING(
                    f"[UNRESTRICTED] Team '{team.name}' in '{team.organization.name}' "
                    "has no module grants; blank intentionally means access to all modules."
                )
            )

        inactive_assignments = (
            Team.objects.filter(modules__is_active=False)
            .select_related("organization")
            .prefetch_related("modules")
            .distinct()
        )
        for team in inactive_assignments:
            inactive = ", ".join(
                team.modules.filter(is_active=False).values_list("slug", flat=True)
            )
            findings += 1
            self.stdout.write(
                self.style.WARNING(
                    f"[INACTIVE] Team '{team.name}' in '{team.organization.name}' "
                    f"is assigned inactive module(s): {inactive}."
                )
            )

        if findings:
            summary = f"Module access audit reported {findings} finding(s)."
            self.stdout.write(self.style.WARNING(summary))
            if options["strict"]:
                raise CommandError(summary)
            return

        self.stdout.write(self.style.SUCCESS("Module access audit reported no findings."))
