"""
0013_itemcodesequence_per_type

Replaces the OneToOneField(organization) on ItemCodeSequence with
ForeignKey(organization) + item_type field, allowing one counter row
per (organization, item_type).

Existing rows are migrated to item_type='BOTH' (they used prefix "ART").
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0012_item_item_org_active_idx"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        # 1. Add item_type with a temporary default so existing rows are valid
        migrations.AddField(
            model_name="itemcodesequence",
            name="item_type",
            field=models.CharField(
                max_length=10,
                verbose_name="tipo de artículo",
                default="BOTH",
            ),
            preserve_default=False,
        ),
        # 2. Drop the old OneToOneField and replace with ForeignKey
        migrations.AlterField(
            model_name="itemcodesequence",
            name="organization",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="item_code_sequences",
                to="accounts.organization",
                verbose_name="organización",
            ),
        ),
        # 3. Update prefix — remove default (model no longer has default="ART")
        migrations.AlterField(
            model_name="itemcodesequence",
            name="prefix",
            field=models.CharField(
                max_length=5,
                verbose_name="prefijo",
                help_text="Prefijo del código generado automáticamente (ej. VTA, COM, ART).",
            ),
        ),
        # 4. Add unique constraint on (organization, item_type)
        migrations.AddConstraint(
            model_name="itemcodesequence",
            constraint=models.UniqueConstraint(
                fields=["organization", "item_type"],
                name="unique_item_code_sequence_per_org_type",
            ),
        ),
    ]
