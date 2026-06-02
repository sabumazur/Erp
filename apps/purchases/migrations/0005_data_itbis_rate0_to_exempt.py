from django.db import migrations


def migrate_rate0_to_exempt(apps, schema_editor):
    PurchaseDocumentItem = apps.get_model('purchases', 'PurchaseDocumentItem')
    PurchaseDocumentItem.objects.filter(itbis_rate='RATE_0').update(itbis_rate='EXEMPT')


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0004_remove_historicalsupplier_default_ncf_type_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_rate0_to_exempt, migrations.RunPython.noop),
    ]
