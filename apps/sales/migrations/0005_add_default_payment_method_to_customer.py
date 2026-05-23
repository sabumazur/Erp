# Field removed — default_payment_method will live on the Vendor model in the purchases app.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0004_alter_customer_rnc_cedula"),
    ]

    operations = []
