# Generated by Django 5.0.7 on 2024-12-07 11:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservasi", "0004_remove_recommendation_confidence_score_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="reservasi",
            name="status_updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
