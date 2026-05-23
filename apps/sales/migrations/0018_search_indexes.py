from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0017_alter_ncfsequence_series"),
        ("core", "0003_pg_trgm"),
    ]

    operations = [
        # Customer: FTS + trigram on name, trigram on rnc_cedula
        migrations.AddIndex(
            model_name="customer",
            index=GinIndex(
                SearchVector("name", config="spanish"),
                name="customer_name_fts_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=GinIndex(
                fields=["name"],
                opclasses=["gin_trgm_ops"],
                name="customer_name_trgm_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=GinIndex(
                fields=["rnc_cedula"],
                opclasses=["gin_trgm_ops"],
                name="customer_rnc_trgm_idx",
            ),
        ),
        # Invoice: trigram on encf and doc_number
        migrations.AddIndex(
            model_name="invoice",
            index=GinIndex(
                fields=["encf"],
                opclasses=["gin_trgm_ops"],
                name="invoice_encf_trgm_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="invoice",
            index=GinIndex(
                fields=["doc_number"],
                opclasses=["gin_trgm_ops"],
                name="invoice_doc_number_trgm_idx",
            ),
        ),
        # Payment: trigram on reference
        migrations.AddIndex(
            model_name="payment",
            index=GinIndex(
                fields=["reference"],
                opclasses=["gin_trgm_ops"],
                name="payment_reference_trgm_idx",
            ),
        ),
    ]
