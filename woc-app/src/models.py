from django.core.exceptions import ValidationError
from django.db import models


class GameSource(models.TextChoices):
    LAN = 'LAN', 'LAN'
    ONLINE = 'ONLINE', 'Online'


class BettingMarket(models.TextChoices):
    MAP_1_KILLS = 'M1_KILLS', 'Map 1 kills'
    MAP_2_KILLS = 'M2_KILLS', 'Map 2 kills'
    MAP_3_KILLS = 'M3_KILLS', 'Map 3 kills'
    MAP_1_DEATHS = 'M1_DEATHS', 'Map 1 deaths'
    MAP_2_DEATHS = 'M2_DEATHS', 'Map 2 deaths'
    MAP_3_DEATHS = 'M3_DEATHS', 'Map 3 deaths'


class Player(models.Model):
    player_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = 'players'
        ordering = ('name', 'player_id')

    def __str__(self):
        return self.name


class GameMap(models.Model):
    map_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'maps'
        ordering = ('name',)

    def __str__(self):
        return self.name


class GameMode(models.Model):
    mode_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'modes'
        ordering = ('name',)

    def __str__(self):
        return self.name


class CompetitionStage(models.Model):
    stage_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    season = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = 'competition_stages'
        ordering = ('season', 'start_date')
        constraints = [
            models.UniqueConstraint(
                fields=('name', 'season'),
                name='unique_stage_per_season',
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='end_date_gte_start_date',
            ),
        ]

    def __str__(self):
        return f'{self.name} (Season {self.season})'


class StageMapPoolEntry(models.Model):
    pool_entry_id = models.AutoField(primary_key=True)
    stage = models.ForeignKey(
        CompetitionStage,
        on_delete=models.PROTECT,
        related_name='map_pool',
    )
    game_map = models.ForeignKey(
        GameMap,
        on_delete=models.PROTECT,
        related_name='pool_entries',
    )
    mode = models.ForeignKey(
        GameMode,
        on_delete=models.PROTECT,
        related_name='pool_entries',
    )

    class Meta:
        db_table = 'stage_map_pool'
        ordering = ('stage', 'mode__name', 'game_map__name')
        constraints = [
            models.UniqueConstraint(
                fields=('stage', 'game_map', 'mode'),
                name='stage_map_mode_unique_combination',
            ),
        ]

    def __str__(self):
        return f'{self.stage}: {self.game_map} - {self.mode}'


class Game(models.Model):
    game_id = models.BigAutoField(primary_key=True)
    pool_entry = models.ForeignKey(
        StageMapPoolEntry,
        db_column='pool_entry_id',
        on_delete=models.PROTECT,
        related_name='games',
    )
    source = models.CharField(max_length=10, choices=GameSource.choices)
    opponent = models.CharField(max_length=150)
    event_date = models.DateTimeField(db_index=True)

    class Meta:
        db_table = 'games'
        ordering = ('-event_date', '-game_id')

    def clean(self):
        super().clean()

        if self.pool_entry_id and self.event_date:
            stage = self.pool_entry.stage
            game_date = self.event_date.date()

            if game_date < stage.start_date or game_date > stage.end_date:
                raise ValidationError(
                    {'event_date': 'Game date must fall within its stage.'}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def stage(self):
        return self.pool_entry.stage

    @property
    def game_map(self):
        return self.pool_entry.game_map

    @property
    def mode(self):
        return self.pool_entry.mode

    def __str__(self):
        return (
            f'{self.opponent} - '
            f'{self.game_map} {self.mode} '
            f'({self.event_date:%Y-%m-%d})'
        )


class PlayerGameStat(models.Model):
    pk = models.CompositePrimaryKey('player_id', 'game_id')
    player = models.ForeignKey(
        Player,
        db_column='player_id',
        on_delete=models.PROTECT,
        related_name='game_stats',
    )
    game = models.ForeignKey(
        Game,
        db_column='game_id',
        on_delete=models.PROTECT,
        related_name='player_stats',
    )
    kills = models.PositiveIntegerField()
    deaths = models.PositiveIntegerField()
    team = models.CharField(max_length=150)

    class Meta:
        db_table = 'player_game_stats'
        ordering = ('game_id', 'player_id')

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.player} in game {self.game_id}'


class BettingLine(models.Model):
    pk = models.CompositePrimaryKey('player_id', 'game_id', 'market')
    player = models.ForeignKey(
        Player,
        db_column='player_id',
        on_delete=models.PROTECT,
        related_name='betting_lines',
    )
    game = models.ForeignKey(
        Game,
        db_column='game_id',
        on_delete=models.PROTECT,
        related_name='betting_lines',
    )
    market = models.CharField(max_length=10, choices=BettingMarket.choices)
    line = models.DecimalField(max_digits=8, decimal_places=3)

    class Meta:
        db_table = 'betting_lines'
        ordering = ('game_id', 'player_id', 'market')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(line__gte=0),
                name='betting_lines_line_nonnegative',
            ),
        ]

    def __str__(self):
        return f'{self.player} - {self.market}: {self.line}'
