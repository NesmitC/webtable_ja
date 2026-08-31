from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0074_diagnosticattempt_diagnostic_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='diagnosticattempt',
            name='max_primary_score',
            field=models.IntegerField(default=50, verbose_name='Максимальный первичный балл'),
        ),
    ]
