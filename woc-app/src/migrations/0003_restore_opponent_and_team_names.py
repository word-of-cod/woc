import django.db.models.deletion
from django.db import migrations, models


def restore_name_fields(apps, schema_editor):
    Game = apps.get_model('src', 'Game')
    PlayerGameStat = apps.get_model('src', 'PlayerGameStat')

    for game in Game.objects.select_related('team_two').all().iterator():
        game.opponent = game.team_two.name
        game.save(update_fields=['opponent'])

    for stat in PlayerGameStat.objects.select_related('team_reference').all().iterator():
        stat.team = stat.team_reference.name
        stat.save(update_fields=['team'])


def recreate_team_references(apps, schema_editor):
    Team = apps.get_model('src', 'Team')
    Game = apps.get_model('src', 'Game')
    PlayerGameStat = apps.get_model('src', 'PlayerGameStat')

    unknown_team_one, _ = Team.objects.get_or_create(name='Unknown Team One')

    for game in Game.objects.all().iterator():
        opponent_name = (game.opponent or '').strip() or 'Unknown Team Two'
        team_two, _ = Team.objects.get_or_create(name=opponent_name)
        game.team_one_id = unknown_team_one.pk
        game.team_two_id = team_two.pk
        game.save(update_fields=['team_one', 'team_two'])

    for stat in PlayerGameStat.objects.all().iterator():
        team_name = (stat.team or '').strip() or 'Unknown Team One'
        team, _ = Team.objects.get_or_create(name=team_name)
        stat.team_reference_id = team.pk
        stat.save(update_fields=['team_reference'])


class Migration(migrations.Migration):
    dependencies = [
        ('src', '0002_normalize_teams_and_protect_history'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='game',
            name='games_distinct_teams',
        ),
        migrations.AddField(
            model_name='game',
            name='opponent',
            field=models.CharField(max_length=150, null=True),
        ),
        migrations.RenameField(
            model_name='playergamestat',
            old_name='team',
            new_name='team_reference',
        ),
        migrations.AlterField(
            model_name='playergamestat',
            name='team_reference',
            field=models.ForeignKey(
                db_column='team_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='player_game_stats',
                to='src.team',
            ),
        ),
        migrations.AlterField(
            model_name='game',
            name='team_one',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='games_as_team_one',
                to='src.team',
            ),
        ),
        migrations.AlterField(
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
            field=models.CharField(max_length=150, null=True),
        ),
        migrations.RunPython(
            restore_name_fields,
            recreate_team_references,
        ),
        migrations.RemoveField(
            model_name='game',
            name='team_one',
        ),
        migrations.RemoveField(
            model_name='game',
            name='team_two',
        ),
        migrations.RemoveField(
            model_name='playergamestat',
            name='team_reference',
        ),
        migrations.DeleteModel(
            name='Team',
        ),
        migrations.AlterField(
            model_name='game',
            name='opponent',
            field=models.CharField(max_length=150),
        ),
        migrations.AlterField(
            model_name='playergamestat',
            name='team',
            field=models.CharField(max_length=150),
        ),
    ]
