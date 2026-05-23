"""
0009_invoiceitem_item_fk

Adds an optional FK from InvoiceItem to items.Item.
SET_NULL ensures existing line items are unaffected if a catalog entry is deleted.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0008_document_types"),
        ("items",    "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceitem",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="line_items",
                to="items.item",
                verbose_name="artículo",
            ),
        ),
    ]
