from django.db import migrations

PAYMENT_TERMS = [
    ("Contado",   "Pago inmediato al momento de la transacción.",  0),
    ("Net 7",     "Pago dentro de 7 días.",                         7),
    ("Net 15",    "Pago dentro de 15 días.",                        15),
    ("Net 30",    "Pago dentro de 30 días.",                        30),
    ("Net 45",    "Pago dentro de 45 días.",                        45),
    ("Net 60",    "Pago dentro de 60 días.",                        60),
    ("Net 90",    "Pago dentro de 90 días.",                        90),
]


def seed(apps, schema_editor):
    PaymentTerm = apps.get_model("sales", "PaymentTerm")
    for name, description, days_due in PAYMENT_TERMS:
        PaymentTerm.objects.get_or_create(
            name=name,
            defaults={"description": description, "days_due": days_due},
        )


def unseed(apps, schema_editor):
    PaymentTerm = apps.get_model("sales", "PaymentTerm")
    PaymentTerm.objects.filter(name__in=[t[0] for t in PAYMENT_TERMS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0006_add_payment_term_model_and_customer_fk"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
