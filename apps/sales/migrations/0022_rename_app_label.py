from django.db import migrations


class Migration(migrations.Migration):
    """Anchor migration marking completion of invoices→sales app label rename.

    django_migrations and django_content_type rows updated via shell SQL
    before this migration was applied.
    """

    dependencies = [
        ("sales", "0021_rename_invoice_salesdocument"),
    ]

    operations = []
