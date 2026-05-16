import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0006_alter_invitation_options_alter_membership_options_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255, verbose_name="nombre / razón social")),
                ("rnc", models.CharField(blank=True, help_text="Registro Nacional de Contribuyente (9 dígitos).", max_length=20, verbose_name="RNC")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="correo electrónico")),
                ("phone", models.CharField(blank=True, max_length=20, verbose_name="teléfono")),
                ("contact_name", models.CharField(blank=True, max_length=150, verbose_name="nombre de contacto")),
                ("address", models.CharField(blank=True, max_length=255, verbose_name="dirección")),
                ("notes", models.TextField(blank=True, verbose_name="notas")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
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
                "ordering": ["name"],
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="supplier",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True),
                fields=["organization", "name"],
                name="unique_active_supplier_name_per_org",
            ),
        ),
        migrations.CreateModel(
            name="PurchaseOrderSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("current_seq", models.PositiveIntegerField(default=0, verbose_name="secuencia actual")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchase_order_sequence",
                        to="accounts.organization",
                        verbose_name="organización",
                    ),
                ),
            ],
            options={
                "verbose_name": "secuencia de orden de compra",
                "verbose_name_plural": "secuencias de órdenes de compra",
            },
        ),
        migrations.CreateModel(
            name="PurchaseOrder",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
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
                ("number", models.CharField(blank=True, editable=False, help_text="Asignado automáticamente al confirmar.", max_length=30, verbose_name="número")),
                ("issue_date", models.DateField(verbose_name="fecha de emisión")),
                ("expected_date", models.DateField(blank=True, help_text="Opcional. Fecha en que se espera recibir la mercancía.", null=True, verbose_name="fecha esperada de recepción")),
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
                        to="purchases.supplier",
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
        migrations.AddIndex(
            model_name="purchaseorder",
            index=models.Index(fields=["organization", "status"], name="purchases_po_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="purchaseorder",
            index=models.Index(fields=["organization", "issue_date"], name="purchases_po_org_date_idx"),
        ),
    ]
