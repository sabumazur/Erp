from django.db import migrations


def migrate_rate0_to_exempt(apps, schema_editor):
    Item = apps.get_model('items', 'Item')
    Item.objects.filter(itbis_rate='RATE_0').update(itbis_rate='EXEMPT')


class Migration(migrations.Migration):

    dependencies = [
        ('items', '0009_historicalitem_default_supplier_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_rate0_to_exempt, migrations.RunPython.noop),
    ]
