from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0018_search_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ncfsequence",
            name="max_seq",
            field=models.BigIntegerField(default=99999999, verbose_name="secuencia máxima"),
        ),
    ]
