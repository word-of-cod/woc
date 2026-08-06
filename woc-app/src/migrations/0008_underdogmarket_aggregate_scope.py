from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('src', '0007_playeralias_underdogmarket'),
    ]

    operations = [
        migrations.AddField(
            model_name='underdogmarket',
            name='market_scope',
            field=models.CharField(
                choices=[
                    ('SINGLE_GAME', 'Single game'),
                    ('GAMES_1_3', 'Games 1-3'),
                ],
                default='SINGLE_GAME',
                max_length=20,
            ),
        ),
        migrations.RemoveConstraint(
            model_name='underdogmarket',
            name='underdog_markets_game_number_positive',
        ),
        migrations.AlterField(
            model_name='underdogmarket',
            name='series_game_number',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name='underdogmarket',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(series_game_number__isnull=True)
                    | models.Q(series_game_number__gte=1)
                ),
                name='underdog_markets_game_number_positive',
            ),
        ),
    ]
