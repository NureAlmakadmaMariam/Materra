import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analyses', '0006_update_eco_scores'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='analysis',
            name='idx_analyses_user_id',
        ),
        migrations.RemoveField(
            model_name='analysis',
            name='user_id',
        ),
        migrations.AddField(
            model_name='analysis',
            name='user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='analyses',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name='analysis',
            index=models.Index(fields=['user'], name='idx_analyses_user'),
        ),
    ]
