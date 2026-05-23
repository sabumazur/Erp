from django.db import migrations


def rename_slug(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    # Remove any existing "sales" placeholder module (prevents slug uniqueness conflict)
    Module.objects.filter(slug="sales").delete()
    # Rename the active "invoices" module to "sales"
    Module.objects.filter(slug="invoices").update(
        slug="sales",
        name="Ventas",
        description="Facturas, cotizaciones, órdenes de venta, clientes y reportes DGII (606/607/608)",
    )


def reverse_rename_slug(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    Module.objects.filter(slug="sales").update(slug="invoices", name="Facturación")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_historicalnotification"),
    ]

    operations = [
        migrations.RunPython(rename_slug, reverse_rename_slug),
    ]
