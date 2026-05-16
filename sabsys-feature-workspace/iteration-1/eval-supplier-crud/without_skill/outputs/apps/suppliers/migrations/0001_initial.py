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
                ("deleted_at", models.DateTimeField(db_index=True, null=True, blank=True)),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="suppliers",
                        to="accounts.organization",
                        verbose_name="organización",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=150, verbose_name="nombre"),
                ),
                (
                    "rnc",
                    models.CharField(
                        blank=True,
                        help_text="Registro Nacional del Contribuyente (opcional).",
                        max_length=20,
                        verbose_name="RNC",
                    ),
                ),
                (
                    "phone",
                    models.CharField(blank=True, max_length=30, verbose_name="teléfono"),
                ),
                (
                    "email",
                    models.EmailField(blank=True, verbose_name="correo electrónico"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("ACTIVE", "Activo"), ("INACTIVE", "Inactivo")],
                        db_index=True,
                        default="ACTIVE",
                        max_length=10,
                        verbose_name="estado",
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
                condition=models.Q(
                    models.Q(("deleted_at__isnull", True)),
                    ~models.Q(("rnc", "")),
                ),
                fields=["organization", "rnc"],
                name="unique_active_supplier_rnc_per_org",
            ),
        ),
    ]
