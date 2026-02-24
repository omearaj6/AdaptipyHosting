from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ai_demo', '0004_backfill_proficiency'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserNotebook',
            fields=[
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, related_name='notebook', serialize=False, to=settings.AUTH_USER_MODEL)),
                ('content', models.TextField(blank=True, default='')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]