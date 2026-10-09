from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='LabelTranslation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('raw_label_en', models.CharField(max_length=200, unique=True)),
                ('translated_uk', models.CharField(max_length=200)),
                ('is_manual', models.BooleanField(
                    default=False,
                    help_text='Якщо позначено, цей переклад не буде перезаписаний автоматично.',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Переклад мітки',
                'verbose_name_plural': 'Переклади міток',
                'ordering': ['raw_label_en'],
            },
        ),
    ]
