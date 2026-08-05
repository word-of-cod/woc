from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('src', '0004_bettingline_kills_and_deaths_markets'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bettingline',
            name='market',
            field=models.CharField(
                choices=[
                    ('M1_KILLS', 'Map 1 kills'),
                    ('M2_KILLS', 'Map 2 kills'),
                    ('M3_KILLS', 'Map 3 kills'),
                    ('M1_DEATHS', 'Map 1 deaths'),
                    ('M2_DEATHS', 'Map 2 deaths'),
                    ('M3_DEATHS', 'Map 3 deaths'),
                ],
                max_length=10,
            ),
        ),
    ]
