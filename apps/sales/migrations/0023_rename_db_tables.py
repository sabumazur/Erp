from django.db import migrations

RENAMES = [
    ("invoices_customer", "sales_customer"),
    ("invoices_customerdepartment", "sales_customerdepartment"),
    ("invoices_documentsequence", "sales_documentsequence"),
    ("invoices_historicalcustomer", "sales_historicalcustomer"),
    ("invoices_historicalcustomerdepartment", "sales_historicalcustomerdepartment"),
    ("invoices_historicalpayment", "sales_historicalpayment"),
    ("invoices_historicalsalesdocument", "sales_historicalsalesdocument"),
    ("invoices_ncfsequence", "sales_ncfsequence"),
    ("invoices_payment", "sales_payment"),
    ("invoices_paymentallocation", "sales_paymentallocation"),
    ("invoices_paymentterm", "sales_paymentterm"),
    ("invoices_salesdocument", "sales_salesdocument"),
    ("invoices_salesdocumentitem", "sales_salesdocumentitem"),
]

rename_stmts = "\n        ".join(
    f"ALTER TABLE {old} RENAME TO {new};" for old, new in RENAMES
)
reverse_stmts = "\n        ".join(
    f"ALTER TABLE {new} RENAME TO {old};" for old, new in RENAMES
)

# Only rename if the old tables still exist (skips on fresh DB where 0001 creates sales_* directly).
FORWARD_SQL = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='invoices_customer') THEN
        {rename_stmts}
    END IF;
END $$;
"""

REVERSE_SQL = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='sales_customer') THEN
        {reverse_stmts}
    END IF;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0022_rename_app_label"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.RunSQL(sql=FORWARD_SQL, reverse_sql=REVERSE_SQL),
            ],
        ),
    ]
