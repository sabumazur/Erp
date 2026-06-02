from django.db import migrations


def migrate_rate0_to_exempt(apps, schema_editor):
    SalesDocumentItem = apps.get_model('sales', 'SalesDocumentItem')
    SalesDocumentItem.objects.filter(itbis_rate='RATE_0').update(itbis_rate='EXEMPT')


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0025_financial_integrity_constraints'),
    ]

    operations = [
        migrations.RunPython(migrate_rate0_to_exempt, migrations.RunPython.noop),
    ]
