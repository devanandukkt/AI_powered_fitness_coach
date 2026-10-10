# Generated for daily authenticated activity tracking.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0006_userbmi'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginActivityDay',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_activity_days', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date'],
                'constraints': [
                    models.UniqueConstraint(fields=('user', 'date'), name='unique_user_login_activity_day'),
                ],
            },
        ),
    ]
