from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('src', '0003_restore_opponent_and_team_names'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bettingline',
            name='market',
            field=models.CharField(
                choices=[('KILLS', 'Kills'), ('DEATHS', 'Deaths')],
                max_length=10,
            ),
        ),
    ]
