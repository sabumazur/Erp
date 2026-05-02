"""
0002_item_code_sequence

Creates the items_itemcodesequence table.
One row per organization; atomically tracks the next auto-generated item code.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items",    "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ItemCodeSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("organization", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="item_code_sequence",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
                ("prefix", models.CharField(
                    default="ART",
                    max_length=5,
                    verbose_name="prefijo",
                    help_text="Prefijo del código generado automáticamente (ej. ART, PRD, VTA).",
                )),
                ("current_seq", models.PositiveIntegerField(
                    default=0,
                    verbose_name="secuencia actual",
                )),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "secuencia de códigos de artículo",
                "verbose_name_plural": "secuencias de códigos de artículo",
            },
        ),
    ]
