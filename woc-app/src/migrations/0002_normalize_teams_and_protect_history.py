import django.db.models.deletion
from django.db import migrations, models


UNKNOWN_TEAM_NAME = 'Unknown Team'


def normalize_legacy_teams(apps, schema_editor):
    Team = apps.get_model('src', 'Team')
    Game = apps.get_model('src', 'Game')
    PlayerGameStat = apps.get_model('src', 'PlayerGameStat')

    team_cache = {}

    def get_or_create_team(name):
        key = name.strip().casefold()
        if key in team_cache:
            return team_cache[key]

        team = Team.objects.filter(name__iexact=name).first()
        if team is None:
            team = Team.objects.create(name=name)

        team_cache[key] = team
        return team

    for game in Game.objects.all().iterator():
        opponent_name = (game.opponent_name or '').strip()
        if not opponent_name:
            opponent_name = f'{UNKNOWN_TEAM_NAME} Two'

        team_two = get_or_create_team(opponent_name)

        stat_team_names = list(
            PlayerGameStat.objects.filter(game_id=game.pk)
            .exclude(team_name__isnull=True)
            .exclude(team_name='')
            .values_list('team_name', flat=True)
            .distinct()
        )
        other_team_names = [
            name.strip()
            for name in stat_team_names
            if name.strip() and name.strip().casefold() != opponent_name.casefold()
        ]
        team_one_name = (
            other_team_names[0]
            if other_team_names
            else f'{UNKNOWN_TEAM_NAME} One'
        )
        team_one = get_or_create_team(team_one_name)

        game.team_one_id = team_one.pk
        game.team_two_id = team_two.pk
        game.save(update_fields=['team_one', 'team_two'])

        for stat in PlayerGameStat.objects.filter(game_id=game.pk).iterator():
            legacy_name = (stat.team_name or '').strip()
            if not legacy_name:
                stat.team_id = team_one.pk
            elif legacy_name.casefold() == team_one.name.casefold():
                stat.team_id = team_one.pk
            elif legacy_name.casefold() == team_two.name.casefold():
                stat.team_id = team_two.pk
            else:
                stat.team_id = get_or_create_team(legacy_name).pk
            stat.save(update_fields=['team'])


def restore_legacy_team_names(apps, schema_editor):
    Game = apps.get_model('src', 'Game')
    PlayerGameStat = apps.get_model('src', 'PlayerGameStat')

    for game in Game.objects.select_related('team_two').all().iterator():
        game.opponent_name = game.team_two.name
        game.save(update_fields=['opponent_name'])

    for stat in PlayerGameStat.objects.select_related('team').all().iterator():
        stat.team_name = stat.team.name
        stat.save(update_fields=['team_name'])


class Migration(migrations.Migration):
    dependencies = [
        ('src', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='game',
            old_name='opponent',
            new_name='opponent_name',
        ),
        migrations.RenameField(
            model_name='playergamestat',
            old_name='team',
            new_name='team_name',
        ),
        migrations.AlterField(
            model_name='game',
            name='opponent_name',
            field=models.CharField(max_length=150, null=True),
        ),
        migrations.AlterField(
            model_name='playergamestat',
            name='team_name',
            field=models.CharField(max_length=150, null=True),
        ),
        migrations.CreateModel(
            name='Team',
            fields=[
                (
                    'team_id',
                    models.AutoField(primary_key=True, serialize=False),
                ),
                ('name', models.CharField(max_length=150, unique=True)),
            ],
            options={
                'db_table': 'teams',
                'ordering': ('name',),
            },
        ),
        migrations.AddField(
            model_name='game',
            name='team_one',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='games_as_team_one',
                to='src.team',
            ),
        ),
        migrations.AddField(
            model_name='game',
            name='team_two',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='games_as_team_two',
                to='src.team',
            ),
        ),
        migrations.AddField(
            model_name='playergamestat',
            name='team',
            field=models.ForeignKey(
                db_column='team_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='player_game_stats',
                to='src.team',
            ),
        ),
        migrations.RunPython(
            normalize_legacy_teams,
            restore_legacy_team_names,
        ),
        migrations.RemoveField(
            model_name='game',
            name='opponent_name',
        ),
        migrations.RemoveField(
            model_name='playergamestat',
            name='team_name',
        ),
        migrations.AlterField(
            model_name='game',
            name='team_one',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='games_as_team_one',
                to='src.team',
            ),
        ),
        migrations.AlterField(
            model_name='game',
            name='team_two',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='games_as_team_two',
                to='src.team',
            ),
        ),
        migrations.AlterField(
            model_name='playergamestat',
            name='team',
            field=models.ForeignKey(
                db_column='team_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='player_game_stats',
                to='src.team',
            ),
        ),
        migrations.AlterField(
            model_name='playergamestat',
            name='player',
            field=models.ForeignKey(
                db_column='player_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='game_stats',
                to='src.player',
            ),
        ),
        migrations.AlterField(
            model_name='playergamestat',
            name='game',
            field=models.ForeignKey(
                db_column='game_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='player_stats',
                to='src.game',
            ),
        ),
        migrations.AlterField(
            model_name='bettingline',
            name='player',
            field=models.ForeignKey(
                db_column='player_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='betting_lines',
                to='src.player',
            ),
        ),
        migrations.AlterField(
            model_name='bettingline',
            name='game',
            field=models.ForeignKey(
                db_column='game_id',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='betting_lines',
                to='src.game',
            ),
        ),
        migrations.RemoveConstraint(
            model_name='playergamestat',
            name='player_game_stats_kills_nonnegative',
        ),
        migrations.RemoveConstraint(
            model_name='playergamestat',
            name='player_game_stats_deaths_nonnegative',
        ),
        migrations.AddConstraint(
            model_name='game',
            constraint=models.CheckConstraint(
                condition=~models.Q(team_one=models.F('team_two')),
                name='games_distinct_teams',
            ),
        ),
    ]
