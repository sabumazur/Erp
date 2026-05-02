"""
0008_document_types

Adds the unified document model fields:
  - Invoice.doc_type          discriminator (INVOICE / QUOTATION / SALE_ORDER)
  - Invoice.doc_number        non-fiscal reference (COT-YYYY-NNNN, OV-YYYY-NNNN)
  - Invoice.valid_until       quotation expiry
  - Invoice.delivery_date     sale-order delivery date
  - Invoice.signed_by         printed name of person who received the order
  - Invoice.consolidated_into self-FK: sale order → consolidating invoice
  - New Status choices        (ACCEPTED, REJECTED, EXPIRED, CONVERTED, DELIVERED, INVOICED)
  - DocumentSequence model    lightweight auto-increment for non-fiscal docs
  - Unique constraint         doc_number per org
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0007_seed_payment_terms"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        # ── 1. doc_type ──────────────────────────────────────────────────────
        migrations.AddField(
            model_name="invoice",
            name="doc_type",
            field=models.CharField(
                choices=[
                    ("INVOICE",    "Factura"),
                    ("QUOTATION",  "Cotización"),
                    ("SALE_ORDER", "Orden de Venta"),
                ],
                db_index=True,
                default="INVOICE",
                max_length=20,
                verbose_name="tipo de documento",
            ),
        ),

        # ── 2. doc_number ────────────────────────────────────────────────────
        migrations.AddField(
            model_name="invoice",
            name="doc_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Asignado automáticamente al confirmar (COT-YYYY-NNNN / OV-YYYY-NNNN).",
                max_length=20,
                verbose_name="número de documento",
            ),
            preserve_default=False,
        ),

        # ── 3. valid_until ───────────────────────────────────────────────────
        migrations.AddField(
            model_name="invoice",
            name="valid_until",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="válida hasta",
            ),
        ),

        # ── 4. delivery_date ─────────────────────────────────────────────────
        migrations.AddField(
            model_name="invoice",
            name="delivery_date",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="fecha de entrega",
            ),
        ),

        # ── 5. signed_by ─────────────────────────────────────────────────────
        migrations.AddField(
            model_name="invoice",
            name="signed_by",
            field=models.CharField(
                blank=True,
                help_text="Nombre de la persona que recibió y firmó la entrega.",
                max_length=150,
                verbose_name="recibido por",
            ),
        ),

        # ── 6. consolidated_into (self-FK) ────────────────────────────────────
        migrations.AddField(
            model_name="invoice",
            name="consolidated_into",
            field=models.ForeignKey(
                blank=True,
                help_text="Factura que consolidó esta orden de venta.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="consolidated_orders",
                to="invoices.invoice",
                verbose_name="consolidada en",
            ),
        ),

        # ── 7. Unique constraint on doc_number per org ────────────────────────
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(doc_number=""),
                fields=["organization", "doc_number"],
                name="unique_doc_number_per_org",
            ),
        ),

        # ── 8. DocumentSequence model ─────────────────────────────────────────
        migrations.CreateModel(
            name="DocumentSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("doc_type", models.CharField(
                    choices=[
                        ("QUOTATION",  "Cotización"),
                        ("SALE_ORDER", "Orden de Venta"),
                    ],
                    max_length=20,
                    verbose_name="tipo de documento",
                )),
                ("current_seq", models.PositiveIntegerField(default=0, verbose_name="secuencia actual")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="document_sequences",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
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
                name="unique_doc_sequence_per_org_type",
            ),
        ),
    ]
