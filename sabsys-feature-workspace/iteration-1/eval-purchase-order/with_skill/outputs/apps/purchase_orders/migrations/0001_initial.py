import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "name",
                    models.CharField(max_length=255, verbose_name="nombre"),
                ),
                (
                    "tax_id",
                    models.CharField(
                        blank=True, max_length=50, verbose_name="RNC / Cédula"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="correo electrónico"
                    ),
                ),
                (
                    "phone",
                    models.CharField(
                        blank=True, max_length=30, verbose_name="teléfono"
                    ),
                ),
                (
                    "contact_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="contacto"
                    ),
                ),
                (
                    "address",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="dirección"
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="notas")),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="suppliers",
                        to="accounts.organization",
                        verbose_name="organización",
                    ),
                ),
            ],
            options={
                "verbose_name": "proveedor",
                "verbose_name_plural": "proveedores",
                "ordering": ["-created_at"],
                "abstract": False,
                "unique_together": {("organization", "name")},
            },
        ),
        migrations.CreateModel(
            name="PurchaseOrder",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "deleted_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                (
                    "number",
                    models.CharField(
                        blank=True,
                        editable=False,
                        help_text="Asignado automáticamente al confirmar.",
                        max_length=30,
                        verbose_name="número",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("DRAFT", "Borrador"),
                            ("CONFIRMED", "Confirmada"),
                            ("RECEIVED", "Recibida"),
                            ("CANCELLED", "Anulada"),
                        ],
                        default="DRAFT",
                        max_length=20,
                        verbose_name="estado",
                    ),
                ),
                (
                    "issue_date",
                    models.DateField(verbose_name="fecha de emisión"),
                ),
                (
                    "expected_date",
                    models.DateField(
                        blank=True,
                        null=True,
                        verbose_name="fecha esperada de entrega",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="notas")),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchase_orders",
                        to="accounts.organization",
                        verbose_name="organización",
                    ),
                ),
                (
                    "supplier",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="purchase_orders",
                        to="purchase_orders.supplier",
                        verbose_name="proveedor",
                    ),
                ),
            ],
            options={
                "verbose_name": "orden de compra",
                "verbose_name_plural": "órdenes de compra",
                "ordering": ["-created_at"],
                "abstract": False,
            },
        ),
    ]
