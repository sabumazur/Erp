from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_populate_document_sequence"),
        ("purchases", "0009_add_perf_indexes"),
    ]

    operations = [
        migrations.DeleteModel(
            name="PurchaseSequence",
        ),
    ]
