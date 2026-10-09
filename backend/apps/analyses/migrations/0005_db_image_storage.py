import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('analyses', '0004_remove_report_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='analysis',
            name='image_path',
        ),
        migrations.CreateModel(
            name='AnalysisImage',
            fields=[
                ('analysis', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    primary_key=True,
                    related_name='image',
                    serialize=False,
                    to='analyses.analysis',
                )),
                ('image_data', models.BinaryField()),
                ('content_type', models.CharField(default='image/jpeg', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Зображення аналізу',
                'verbose_name_plural': 'Зображення аналізів',
            },
        ),
    ]
