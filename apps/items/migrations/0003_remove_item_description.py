from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("items", "0002_item_code_sequence"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="item",
            name="description",
        ),
    ]
