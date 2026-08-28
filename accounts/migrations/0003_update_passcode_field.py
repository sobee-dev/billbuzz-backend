from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_role_to_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='passcode',
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
