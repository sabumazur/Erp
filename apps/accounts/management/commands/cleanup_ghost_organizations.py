from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Deprecated: personal workspaces are retained and are not deleted automatically."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "No organizations were deleted. Automatic workspace cleanup has been disabled."
        ))
