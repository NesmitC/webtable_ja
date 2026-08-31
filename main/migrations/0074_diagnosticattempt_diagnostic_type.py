from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0073_add_primary_score_to_diagnostic'),
    ]

    operations = [
        migrations.AddField(
            model_name='diagnosticattempt',
            name='diagnostic_type',
            field=models.CharField(blank=True, max_length=20, verbose_name='Тип диагностики'),
        ),
    ]
