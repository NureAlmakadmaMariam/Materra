from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('analyses', '0003_update_waste_class_recycling'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='analysis',
            name='report_path',
        ),
        migrations.RemoveField(
            model_name='analysis',
            name='report_generated_at',
        ),
    ]
