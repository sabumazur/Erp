from django.db import migrations


PREFIX_MAP = {"QUOTATION": "COT", "SALE_ORDER": "OV"}


def populate_document_sequences(apps, schema_editor):
    DocumentSequence = apps.get_model("core", "DocumentSequence")
    OldDocSeq = apps.get_model("sales", "DocumentSequence")
    OldPurchaseSeq = apps.get_model("purchases", "PurchaseSequence")

    for row in OldDocSeq.objects.select_related("organization").all():
        DocumentSequence.objects.update_or_create(
            organization=row.organization,
            doc_type=row.doc_type,
            defaults={
                "prefix": PREFIX_MAP.get(row.doc_type, row.doc_type[:3].upper()),
                "current_seq": row.current_seq,
                "padding": 4,
                "include_year": True,
            },
        )

    for row in OldPurchaseSeq.objects.select_related("organization").all():
        DocumentSequence.objects.update_or_create(
            organization=row.organization,
            doc_type="PURCHASE_ORDER",
            defaults={
                "prefix": row.prefix,
                "current_seq": row.next_value - 1,
                "padding": row.padding,
                "include_year": False,
            },
        )


def reverse_populate(apps, schema_editor):
    DocumentSequence = apps.get_model("core", "DocumentSequence")
    OldDocSeq = apps.get_model("sales", "DocumentSequence")
    OldPurchaseSeq = apps.get_model("purchases", "PurchaseSequence")

    for row in DocumentSequence.objects.filter(doc_type__in=["QUOTATION", "SALE_ORDER"]).select_related("organization"):
        OldDocSeq.objects.update_or_create(
            organization=row.organization,
            doc_type=row.doc_type,
            defaults={"current_seq": row.current_seq},
        )

    for row in DocumentSequence.objects.filter(doc_type="PURCHASE_ORDER").select_related("organization"):
        OldPurchaseSeq.objects.update_or_create(
            organization=row.organization,
            defaults={
                "prefix": row.prefix,
                "next_value": row.current_seq + 1,
                "padding": row.padding,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_document_sequence"),
        ("sales", "0032_perf_materialized_view"),
        ("purchases", "0009_add_perf_indexes"),
    ]

    operations = [
        migrations.RunPython(populate_document_sequences, reverse_populate),
    ]
