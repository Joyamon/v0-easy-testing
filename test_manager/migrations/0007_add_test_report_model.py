from django.db import migrations, models
import django.db.models.deletion
import uuid
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('test_manager', '0006_add_group_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='TestReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('report_type', models.CharField(choices=[('test_run', 'Test Run'), ('test_suite_run', 'Test Suite Run'), ('custom', 'Custom')], default='test_run', max_length=20)),
                ('report_format', models.CharField(choices=[('html', 'HTML'), ('pdf', 'PDF'), ('json', 'JSON')], default='html', max_length=10)),
                ('content', models.TextField()),
                ('is_public', models.BooleanField(default=False)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='test_reports', to='test_manager.project')),
                ('test_run', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='test_manager.testrun')),
                ('test_suite_run', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reports', to='test_manager.testsuiterun')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
