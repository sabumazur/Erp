from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_notification"),
    ]

    operations = [
        TrigramExtension(),
    ]
