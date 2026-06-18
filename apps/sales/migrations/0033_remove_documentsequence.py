from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_populate_document_sequence"),
        ("sales", "0032_perf_materialized_view"),
    ]

    operations = [
        migrations.DeleteModel(
            name="DocumentSequence",
        ),
    ]
