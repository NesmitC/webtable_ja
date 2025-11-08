from django.db import migrations

def add_letters_to_orthograms(apps, schema_editor):
    Orthogram = apps.get_model('main', 'Orthogram')
    for orth in Orthogram.objects.all():
        if not orth.letters:
            orth.letters = 'а,о,е,и,я'
            orth.save()

class Migration(migrations.Migration):
    dependencies = [
        ('main', '0018_alter_orthogramexample_orthogram'),
    ]

    operations = [
        migrations.RunPython(add_letters_to_orthograms),
    ]