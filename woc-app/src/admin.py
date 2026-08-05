from django.contrib import admin

from .models import (
    BettingLine,
    CompetitionStage,
    Game,
    GameMap,
    GameMode,
    Player,
    PlayerGameStat,
    StageMapPoolEntry,
)


class PlayerGameStatInline(admin.TabularInline):
    model = PlayerGameStat
    extra = 0
    raw_id_fields = ('game',)

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related(
                'game__pool_entry__game_map',
                'game__pool_entry__mode',
                'game__pool_entry__stage',
            )
        )


class BettingLineInline(admin.TabularInline):
    model = BettingLine
    extra = 0

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('player_id', 'name')
    search_fields = ('name',)
    inlines = (PlayerGameStatInline,)


@admin.register(GameMap)
class GameMapAdmin(admin.ModelAdmin):
    list_display = ('map_id', 'name')
    search_fields = ('name',)

@admin.register(GameMode)
class GameModeAdmin(admin.ModelAdmin):
    list_display = ('mode_id', 'name')
    search_fields = ('name',)

@admin.register(CompetitionStage)
class CompetitionStageAdmin(admin.ModelAdmin):
    list_display = (
        'stage_id',
        'name',
        'season',
        'start_date',
        'end_date',
    )
    list_filter = (
        'season',
    )
    search_fields = (
        'name',
    )
    ordering = (
        '-season',
        'start_date',
    )

@admin.register(StageMapPoolEntry)
class StageMapPoolEntryAdmin(admin.ModelAdmin):
    list_display = (
        'pool_entry_id',
        'stage',
        'game_map',
        'mode',
    )
    list_filter = (
        'stage__season',
        'stage',
        'mode',
    )
    search_fields = (
        'game_map__name',
        'stage__name',
        'mode__name',
    )
    list_select_related = (
        'stage',
        'game_map',
        'mode',
    )

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = (
        'game_id',
        'event_date',
        'opponent',
        'display_map',
        'display_mode',
        'display_stage',
        'source',
    )
    list_filter = (
        'source',
        'pool_entry__stage__season',
        'pool_entry__stage',
        'pool_entry__game_map',
        'pool_entry__mode',
    )
    search_fields = (
        'opponent',
        'pool_entry__game_map__name',
        'pool_entry__mode__name',
        'pool_entry__stage__name',
    )
    list_select_related = (
        'pool_entry',
        'pool_entry__stage',
        'pool_entry__game_map',
        'pool_entry__mode',
    )
    date_hierarchy = 'event_date'
    inlines = (PlayerGameStatInline, BettingLineInline)

    @admin.display(description='Map', ordering='pool_entry__game_map__name')
    def display_map(self, obj):
        return obj.pool_entry.game_map.name

    @admin.display(description='Mode', ordering='pool_entry__mode__name')
    def display_mode(self, obj):
        return obj.pool_entry.mode.name

    @admin.display(description='Stage', ordering='pool_entry__stage__name')
    def display_stage(self, obj):
        return obj.pool_entry.stage.name
