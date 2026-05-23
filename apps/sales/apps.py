from django.apps import AppConfig


class InvoicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.invoices"
    label = "invoices"

    def ready(self):
        import apps.invoices.signals  # noqa: F401
