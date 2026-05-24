from django.db import migrations


def rename_slug(apps, schema_editor):
    Module = apps.get_model("core", "Module")
    invoices = Module.objects.filter(slug="invoices").first()
    sales = Module.objects.filter(slug="sales").first()
    metadata = {
        "name": "Ventas",
        "description": (
            "Facturas, cotizaciones, órdenes de venta, clientes y reportes "
            "DGII (606/607/608)"
        ),
    }

    if invoices and not sales:
        Module.objects.filter(pk=invoices.pk).update(slug="sales", **metadata)
        return

    if sales:
        if invoices:
            sales.teams.add(*invoices.teams.all())
            Module.objects.filter(pk=invoices.pk).delete()
        Module.objects.filter(pk=sales.pk).update(**metadata)


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
