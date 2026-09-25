from django.contrib import admin
from .models import Tournament, Player, TournamentParticipant, Round, Match


class TournamentParticipantInline(admin.TabularInline):
    model = TournamentParticipant
    extra = 1
    fields = ('starting_rank', 'player', 'current_points', 'buchholz_cut1', 'is_active')
    readonly_fields = ('current_points', 'buchholz_cut1')


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ('name', 'tournament_code', 'tournament_system', 'status', 'rounds_count', 'current_round_num', 'federation', 'start_date')
    list_filter = ('status', 'tournament_system', 'time_control_type', 'federation')
    search_fields = ('name', 'tournament_code', 'city', 'chief_arbiter')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TournamentParticipantInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'rating', 'federation', 'fide_id', 'gender', 'birth_year')
    list_filter = ('title', 'federation', 'gender')
    search_fields = ('name', 'fide_id', 'club_or_city')


@admin.register(TournamentParticipant)
class TournamentParticipantAdmin(admin.ModelAdmin):
    list_display = ('starting_rank', 'player', 'tournament', 'current_points', 'buchholz_cut1', 'is_active')
    list_filter = ('tournament', 'is_active')
    search_fields = ('player__name', 'tournament__name')


class MatchInline(admin.TabularInline):
    model = Match
    extra = 0
    fields = ('board_number', 'white_participant', 'result', 'black_participant', 'remarks')


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ('tournament', 'round_number', 'is_paired', 'is_completed', 'is_published')
    list_filter = ('tournament', 'is_paired', 'is_completed')
    inlines = [MatchInline]


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('round', 'board_number', 'white_participant', 'result', 'black_participant', 'white_score', 'black_score')
    list_filter = ('round__tournament', 'round__round_number', 'result')
    search_fields = ('white_participant__player__name', 'black_participant__player__name')
