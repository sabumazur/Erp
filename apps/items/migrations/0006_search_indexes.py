from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0005_alter_item_cost_price"),
        ("core", "0003_pg_trgm"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="item",
            index=GinIndex(
                SearchVector("name", config="spanish"),
                name="item_name_fts_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="item",
            index=GinIndex(
                fields=["name"],
                opclasses=["gin_trgm_ops"],
                name="item_name_trgm_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="item",
            index=GinIndex(
                fields=["code"],
                opclasses=["gin_trgm_ops"],
                name="item_code_trgm_idx",
            ),
        ),
    ]
