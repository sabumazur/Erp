import decimal
import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0004_expand_organization_fields"),
    ]

    operations = [
        # ── Customer ──────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="customers",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
                ("name", models.CharField(max_length=255, verbose_name="nombre / razón social")),
                ("id_type", models.CharField(
                    choices=[("RNC", "RNC"), ("CED", "Cédula"),
                             ("PAS", "Pasaporte"), ("EXT", "Identificación extranjera")],
                    default="RNC",
                    max_length=3,
                    verbose_name="tipo de identificación",
                )),
                ("rnc_cedula", models.CharField(blank=True, max_length=20, verbose_name="RNC / Cédula")),
                ("email", models.EmailField(blank=True, verbose_name="correo electrónico")),
                ("phone", models.CharField(blank=True, max_length=20, verbose_name="teléfono")),
                ("address", models.CharField(blank=True, max_length=255, verbose_name="dirección")),
                ("city", models.CharField(blank=True, max_length=100, verbose_name="ciudad")),
                ("province", models.CharField(blank=True, max_length=100, verbose_name="provincia")),
                ("country", models.CharField(blank=True, default="República Dominicana", max_length=100, verbose_name="país")),
                ("notes", models.TextField(blank=True, verbose_name="notas")),
                ("default_ncf_type", models.IntegerField(
                    choices=[
                        (31, "31 – Factura de Crédito Fiscal"), (32, "32 – Factura de Consumo"),
                        (33, "33 – Nota de Débito"), (34, "34 – Nota de Crédito"),
                        (41, "41 – Comprobante de Compras"), (43, "43 – Gastos Menores"),
                        (44, "44 – Regímenes Especiales"), (45, "45 – Gubernamental"),
                        (46, "46 – Exportaciones"), (47, "47 – Pagos al Exterior"),
                    ],
                    default=31,
                    verbose_name="tipo de comprobante por defecto",
                )),
            ],
            options={"verbose_name": "cliente", "verbose_name_plural": "clientes",
                     "ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(rnc_cedula=""),
                fields=["organization", "rnc_cedula"],
                name="unique_active_customer_rnc_per_org",
            ),
        ),

        # ── NCFSequence ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="NCFSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ncf_sequences",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
                ("ncf_type", models.IntegerField(
                    choices=[
                        (31, "31 – Factura de Crédito Fiscal"), (32, "32 – Factura de Consumo"),
                        (33, "33 – Nota de Débito"), (34, "34 – Nota de Crédito"),
                        (41, "41 – Comprobante de Compras"), (43, "43 – Gastos Menores"),
                        (44, "44 – Regímenes Especiales"), (45, "45 – Gubernamental"),
                        (46, "46 – Exportaciones"), (47, "47 – Pagos al Exterior"),
                    ],
                    verbose_name="tipo de comprobante",
                )),
                ("series", models.CharField(default="E", max_length=1, verbose_name="serie")),
                ("current_seq", models.PositiveIntegerField(default=0, verbose_name="secuencia actual")),
                ("max_seq", models.PositiveIntegerField(default=9999999999, verbose_name="secuencia máxima")),
                ("is_active", models.BooleanField(default=True, verbose_name="activa")),
            ],
            options={"verbose_name": "secuencia NCF", "verbose_name_plural": "secuencias NCF"},
        ),
        migrations.AddConstraint(
            model_name="ncfsequence",
            constraint=models.UniqueConstraint(
                condition=models.Q(is_active=True),
                fields=["organization", "ncf_type"],
                name="unique_active_ncf_sequence_per_org_type",
            ),
        ),

        # ── Invoice ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Invoice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="invoices",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
                ("customer", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="invoices",
                    to="invoices.customer",
                    verbose_name="cliente",
                )),
                ("encf", models.CharField(blank=True, max_length=13, verbose_name="e-NCF")),
                ("ncf_type", models.IntegerField(
                    choices=[
                        (31, "31 – Factura de Crédito Fiscal"), (32, "32 – Factura de Consumo"),
                        (33, "33 – Nota de Débito"), (34, "34 – Nota de Crédito"),
                        (41, "41 – Comprobante de Compras"), (43, "43 – Gastos Menores"),
                        (44, "44 – Regímenes Especiales"), (45, "45 – Gubernamental"),
                        (46, "46 – Exportaciones"), (47, "47 – Pagos al Exterior"),
                    ],
                    default=31,
                    verbose_name="tipo de comprobante",
                )),
                ("encf_modified", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="credit_debit_notes",
                    to="invoices.invoice",
                    verbose_name="NCF afectado",
                )),
                ("issue_date", models.DateField(default=django.utils.timezone.now, verbose_name="fecha de emisión")),
                ("due_date", models.DateField(blank=True, null=True, verbose_name="fecha de vencimiento")),
                ("payment_condition", models.CharField(
                    choices=[("CASH", "Contado"), ("CREDIT", "Crédito"), ("FREE", "Gratuito"), ("OTHER", "Otro")],
                    default="CASH", max_length=10, verbose_name="condición de pago",
                )),
                ("currency", models.CharField(
                    choices=[("DOP", "Peso Dominicano (DOP)"), ("USD", "Dólar Americano (USD)"), ("EUR", "Euro (EUR)")],
                    default="DOP", max_length=3, verbose_name="moneda",
                )),
                ("exchange_rate", models.DecimalField(
                    decimal_places=4, default=decimal.Decimal("1.0000"),
                    max_digits=12, verbose_name="tasa de cambio",
                )),
                ("subtotal", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0.00"),
                    max_digits=14, verbose_name="subtotal (sin ITBIS)",
                )),
                ("itbis_18", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0.00"),
                    max_digits=14, verbose_name="ITBIS 18%",
                )),
                ("itbis_16", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0.00"),
                    max_digits=14, verbose_name="ITBIS 16%",
                )),
                ("total", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0.00"),
                    max_digits=14, verbose_name="total",
                )),
                ("status", models.CharField(
                    choices=[
                        ("DRAFT", "Borrador"), ("CONFIRMED", "Confirmada"), ("SENT", "Enviada"),
                        ("PAID", "Pagada"), ("OVERDUE", "Vencida"), ("CANCELLED", "Anulada"),
                    ],
                    db_index=True, default="DRAFT", max_length=12, verbose_name="estado",
                )),
                ("notes", models.TextField(blank=True, verbose_name="notas internas")),
                ("terms", models.TextField(blank=True, verbose_name="términos y condiciones")),
                ("xml_content", models.TextField(blank=True, verbose_name="XML e-CF")),
                ("dgii_status", models.CharField(
                    choices=[("PENDING", "Pendiente"), ("ACCEPTED", "Aceptada"), ("REJECTED", "Rechazada")],
                    default="PENDING", max_length=10, verbose_name="estado DGII",
                )),
                ("dgii_track_id", models.CharField(blank=True, max_length=100, verbose_name="track ID DGII")),
            ],
            options={"verbose_name": "factura", "verbose_name_plural": "facturas",
                     "ordering": ["-created_at"], "abstract": False},
        ),
        migrations.AddConstraint(
            model_name="invoice",
            constraint=models.UniqueConstraint(
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(encf=""),
                fields=["organization", "encf"],
                name="unique_encf_per_org",
            ),
        ),

        # ── InvoiceItem ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name="InvoiceItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="items",
                    to="invoices.invoice",
                    verbose_name="factura",
                )),
                ("description", models.CharField(max_length=500, verbose_name="descripción")),
                ("quantity", models.DecimalField(
                    decimal_places=4, default=decimal.Decimal("1.0000"),
                    max_digits=12, verbose_name="cantidad",
                )),
                ("unit_price", models.DecimalField(
                    decimal_places=2, max_digits=14,
                    verbose_name="precio unitario (sin ITBIS)",
                )),
                ("itbis_rate", models.CharField(
                    choices=[
                        ("EXEMPT", "Exento (0%)"), ("RATE_0", "Tasa 0% (exportación)"),
                        ("RATE_16", "ITBIS 16%"), ("RATE_18", "ITBIS 18%"),
                    ],
                    default="RATE_18", max_length=8, verbose_name="tasa ITBIS",
                )),
                ("line_total", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0.00"),
                    max_digits=14, verbose_name="total línea (sin ITBIS)",
                )),
                ("itbis_amount", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0.00"),
                    max_digits=14, verbose_name="monto ITBIS",
                )),
                ("line_total_with_itbis", models.DecimalField(
                    decimal_places=2, default=decimal.Decimal("0.00"),
                    max_digits=14, verbose_name="total línea con ITBIS",
                )),
            ],
            options={"verbose_name": "línea de factura", "verbose_name_plural": "líneas de factura",
                     "ordering": ["pk"]},
        ),

        # ── Payment ───────────────────────────────────────────────────────────
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="payments",
                    to="accounts.organization",
                    verbose_name="organización",
                )),
                ("invoice", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="payments",
                    to="invoices.invoice",
                    verbose_name="factura",
                )),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="monto")),
                ("date", models.DateField(default=django.utils.timezone.now, verbose_name="fecha de pago")),
                ("method", models.CharField(
                    choices=[
                        ("CASH", "Efectivo"), ("CHECK", "Cheque"),
                        ("CARD", "Tarjeta de crédito/débito"),
                        ("TRANSFER", "Transferencia bancaria"),
                        ("SWAP", "Permuta"), ("OTHER", "Otro"),
                    ],
                    default="TRANSFER", max_length=10, verbose_name="forma de pago",
                )),
                ("reference", models.CharField(blank=True, max_length=100, verbose_name="referencia")),
                ("notes", models.TextField(blank=True, verbose_name="notas")),
            ],
            options={"verbose_name": "pago", "verbose_name_plural": "pagos",
                     "ordering": ["-created_at"], "abstract": False},
        ),
    ]
