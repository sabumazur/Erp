from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0020_historicalcustomerdepartment"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Invoice",
            new_name="SalesDocument",
        ),
        migrations.RenameModel(
            old_name="InvoiceItem",
            new_name="SalesDocumentItem",
        ),
        migrations.RenameField(
            model_name="salesdocumentitem",
            old_name="invoice",
            new_name="document",
        ),
        migrations.RenameModel(
            old_name="HistoricalInvoice",
            new_name="HistoricalSalesDocument",
        ),
    ]
