import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0010_securityauditevent"),
        ("core", "0005_rename_invoices_module_slug"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentSequence",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("doc_type", models.CharField(max_length=30, verbose_name="tipo de documento")),
                ("prefix", models.CharField(max_length=10, verbose_name="prefijo")),
                ("current_seq", models.PositiveIntegerField(default=0, verbose_name="secuencia actual")),
                ("padding", models.PositiveSmallIntegerField(default=4, verbose_name="dígitos")),
                ("include_year", models.BooleanField(default=False, verbose_name="incluir año")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_sequences",
                        to="accounts.organization",
                        verbose_name="organización",
                    ),
                ),
            ],
            options={
                "verbose_name": "secuencia de documento",
                "verbose_name_plural": "secuencias de documentos",
            },
        ),
        migrations.AddConstraint(
            model_name="documentsequence",
            constraint=models.UniqueConstraint(
                fields=["organization", "doc_type"],
                name="unique_doc_sequence_per_org_doctype",
            ),
        ),
    ]
