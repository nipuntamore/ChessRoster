import json
import random
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator

from .models import Tournament, Player, TournamentParticipant, Round, Match
from .forms import TournamentForm, PlayerRegistrationForm, MatchResultUpdateForm
from .engine import SwissEngine, RoundRobinEngine, TieBreakCalculator


def tournament_list(request):
    """List all tournaments with status filters and search."""
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    system_filter = request.GET.get('system', '')

    tournaments = Tournament.objects.all()

    if query:
        tournaments = tournaments.filter(
            Q(name__icontains=query) |
            Q(tournament_code__icontains=query) |
            Q(city__icontains=query) |
            Q(organizer__icontains=query) |
            Q(federation__icontains=query)
        )
    if status_filter:
        tournaments = tournaments.filter(status=status_filter)
    if system_filter:
        tournaments = tournaments.filter(tournament_system=system_filter)

    total_tournaments = Tournament.objects.count()
    active_count = Tournament.objects.filter(status='ACTIVE').count()
    total_players = Player.objects.count()

    context = {
        'tournaments': tournaments,
        'query': query,
        'status_filter': status_filter,
        'system_filter': system_filter,
        'total_tournaments': total_tournaments,
        'active_count': active_count,
        'total_players': total_players,
    }
    return render(request, 'tournaments/tournament_list.html', context)


def tournament_create(request):
    """Create a new chess tournament."""
    if request.method == 'POST':
        form = TournamentForm(request.POST)
        if form.is_valid():
            tournament = form.save()
            messages.success(request, f"Tournament '{tournament.name}' ({tournament.tournament_code}) created successfully!")
            return redirect('tournament_detail', slug=tournament.slug)
    else:
        # Default start date tomorrow, end date 5 days later
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=5)
        form = TournamentForm(initial={'start_date': start, 'end_date': end})

    return render(request, 'tournaments/tournament_create.html', {'form': form})


def tournament_detail(request, slug):
    """
    Main Tournament Hub (matching Chess-Results.com structure with art codes):
    art=0: Overview / Info
    art=1: Starting rank / Player list
    art=2: Pairings & Results for round rd
    art=4: Standings / Final ranking
    art=5: Crosstable / Grid
    """
    tournament = get_object_or_404(Tournament, slug=slug)
    art = request.GET.get('art', '0')
    rd_param = request.GET.get('rd', '')

    # Determine active round
    selected_round_num = None
    if rd_param and rd_param.isdigit():
        selected_round_num = int(rd_param)
    elif tournament.current_round_num > 0:
        selected_round_num = tournament.current_round_num
    else:
        selected_round_num = 1

    # Fetch rounds
    all_rounds = tournament.rounds.order_by('round_number')
    selected_round = all_rounds.filter(round_number=selected_round_num).first()

    # Get pairings for selected round
    round_matches = []
    if selected_round:
        round_matches = selected_round.matches.select_related(
            'white_participant__player', 
            'black_participant__player'
        ).order_by('board_number')

    # Get participants for player list
    participants_list = tournament.participants.select_related('player').order_by('starting_rank')

    # Standings
    standings = tournament.participants.select_related('player').order_by(
        '-current_points', '-buchholz_cut1', '-buchholz', '-sonneborn_berger', 'starting_rank'
    )

    # Crosstable data calculation
    crosstable_rows = []
    if art == '5' or art == 'crosstable':
        crosstable_rows = _build_crosstable(tournament)

    context = {
        'tournament': tournament,
        'art': art,
        'selected_round_num': selected_round_num,
        'selected_round': selected_round,
        'all_rounds': all_rounds,
        'round_matches': round_matches,
        'participants_list': participants_list,
        'standings': standings,
        'crosstable_rows': crosstable_rows,
    }
    return render(request, 'tournaments/tournament_detail.html', context)


def tournament_register(request, slug):
    """Player registration for a tournament."""
    tournament = get_object_or_404(Tournament, slug=slug)

    if request.method == 'POST':
        form = PlayerRegistrationForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name'].strip()
            fide_id = form.cleaned_data.get('fide_id') or None
            
            # Find or create player
            player = None
            if fide_id:
                player = Player.objects.filter(fide_id=fide_id).first()
            if not player:
                player = Player.objects.filter(name__iexact=name).first()
            if not player:
                player = Player.objects.create(
                    name=name,
                    fide_id=fide_id,
                    title=form.cleaned_data.get('title', 'NONE'),
                    rating=form.cleaned_data.get('rating', 1200),
                    federation=form.cleaned_data.get('federation', 'IND'),
                    club_or_city=form.cleaned_data.get('club_or_city', ''),
                    birth_year=form.cleaned_data.get('birth_year'),
                    gender=form.cleaned_data.get('gender', 'M'),
                    email=form.cleaned_data.get('email'),
                    phone=form.cleaned_data.get('phone', '')
                )
            else:
                # Update player rating/details
                player.rating = form.cleaned_data.get('rating', player.rating)
                player.title = form.cleaned_data.get('title', player.title)
                player.save()

            # Check if already registered
            if TournamentParticipant.objects.filter(tournament=tournament, player=player).exists():
                messages.warning(request, f"Player {player.name} is already registered in this tournament.")
            else:
                current_count = tournament.participants.count()
                TournamentParticipant.objects.create(
                    tournament=tournament,
                    player=player,
                    starting_rank=current_count + 1
                )
                # Re-seed starting ranks
                SwissEngine.initialize_starting_ranks(tournament)
                messages.success(request, f"Player {player.name} registered successfully! Starting Rank updated.")

            return redirect(f"{tournament.get_absolute_url()}?art=1")
    else:
        form = PlayerRegistrationForm()

    return render(request, 'tournaments/tournament_register.html', {
        'tournament': tournament,
        'form': form
    })


def player_detail(request, slug, participant_id):
    """
    Individual Player Scorecard (like Chess-Results player card).
    Shows all round-by-round pairings, opponent details, colors, results, points.
    """
    tournament = get_object_or_404(Tournament, slug=slug)
    participant = get_object_or_404(TournamentParticipant, id=participant_id, tournament=tournament)

    # Gather all matches of this participant
    rounds = tournament.rounds.order_by('round_number')
    player_games = []

    running_score = 0.0
    for r in rounds:
        match_as_white = r.matches.filter(white_participant=participant).first()
        match_as_black = r.matches.filter(black_participant=participant).first()

        if match_as_white:
            m = match_as_white
            is_bye = m.result.endswith('BYE')
            opp = m.black_participant
            opp_player = opp.player if opp else None
            opp_rank = opp.starting_rank if opp else "-"
            opp_rating = opp_player.rating if opp_player else "-"
            color = "W"
            res = m.result
            pts = m.white_score if m.white_score is not None else 0.0
            if m.white_score is not None:
                running_score += pts
                pts_display = str(m.white_score)
            else:
                pts_display = "*"
                
            player_games.append({
                'round_num': r.round_number,
                'board': m.board_number,
                'color': color,
                'is_bye': is_bye,
                'opp_rank': opp_rank,
                'opp_name': opp_player.name if opp_player else "BYE",
                'opp_title': opp_player.title if (opp_player and opp_player.title != 'NONE') else "",
                'opp_rating': opp_rating,
                'opp_fed': opp_player.federation if opp_player else "",
                'opp_participant_id': opp.id if opp else None,
                'result': res,
                'points_earned': pts_display,
                'running_score': running_score if m.white_score is not None else "-",
                'pgn': m.pgn,
            })
        elif match_as_black:
            m = match_as_black
            is_bye = m.result.endswith('BYE')
            opp = m.white_participant
            opp_player = opp.player if opp else None
            opp_rank = opp.starting_rank if opp else "-"
            opp_rating = opp_player.rating if opp_player else "-"
            color = "B"
            res = m.result
            pts = m.black_score if m.black_score is not None else 0.0
            if m.black_score is not None:
                running_score += pts
                pts_display = str(m.black_score)
            else:
                pts_display = "*"

            player_games.append({
                'round_num': r.round_number,
                'board': m.board_number,
                'color': color,
                'is_bye': is_bye,
                'opp_rank': opp_rank,
                'opp_name': opp_player.name if opp_player else "BYE",
                'opp_title': opp_player.title if (opp_player and opp_player.title != 'NONE') else "",
                'opp_rating': opp_rating,
                'opp_fed': opp_player.federation if opp_player else "",
                'opp_participant_id': opp.id if opp else None,
                'result': res,
                'points_earned': pts_display,
                'running_score': running_score if m.black_score is not None else "-",
                'pgn': m.pgn,
            })

    context = {
        'tournament': tournament,
        'participant': participant,
        'player': participant.player,
        'player_games': player_games,
    }
    return render(request, 'tournaments/player_detail.html', context)


def arbiter_control_panel(request, slug):
    """
    Arbiter Management Station:
    - Quick result updater
    - Generate next round pairings
    - Force standing recalculation
    - Direct player additions
    - Close / Complete tournament
    """
    tournament = get_object_or_404(Tournament, slug=slug)
    active_round_num = request.GET.get('rd')
    if active_round_num and active_round_num.isdigit():
        current_rd_num = int(active_round_num)
    else:
        current_rd_num = tournament.current_round_num or 1

    current_round = tournament.rounds.filter(round_number=current_rd_num).first()
    matches = []
    if current_round:
        matches = current_round.matches.select_related(
            'white_participant__player', 'black_participant__player'
        ).order_by('board_number')

    all_rounds = tournament.rounds.order_by('round_number')

    context = {
        'tournament': tournament,
        'current_rd_num': current_rd_num,
        'current_round': current_round,
        'matches': matches,
        'all_rounds': all_rounds,
        'result_choices': Match.RESULT_CHOICES,
    }
    return render(request, 'tournaments/arbiter_panel.html', context)


@require_POST
def generate_round_pairings(request, slug):
    """Triggers pairing generation for the next or requested round."""
    tournament = get_object_or_404(Tournament, slug=slug)
    round_num_to_pair = int(request.POST.get('round_number', tournament.current_round_num + 1))

    if tournament.tournament_system == 'ROUND_ROBIN':
        success, msg = RoundRobinEngine.generate_all_fixtures(tournament)
    else:
        if round_num_to_pair > tournament.rounds_count:
            messages.error(request, f"Cannot pair round {round_num_to_pair}. Maximum rounds is {tournament.rounds_count}.")
            return redirect('arbiter_panel', slug=tournament.slug)
        success, msg = SwissEngine.generate_pairings_for_round(tournament, round_num_to_pair)

    if success:
        messages.success(request, msg)
    else:
        messages.error(request, msg)

    return redirect(f"{tournament.get_absolute_url()}?art=2&rd={round_num_to_pair}")


@require_POST
def update_match_result(request, slug, match_id):
    """Updates a single match score from form or AJAX."""
    tournament = get_object_or_404(Tournament, slug=slug)
    match_obj = get_object_or_404(Match, id=match_id, round__tournament=tournament)
    
    new_result = request.POST.get('result')
    remarks = request.POST.get('remarks', '')
    pgn = request.POST.get('pgn', '')

    if new_result:
        match_obj.result = new_result
        match_obj.remarks = remarks
        if pgn:
            match_obj.pgn = pgn
        match_obj.save()

        # Recalculate full tournament standings
        TieBreakCalculator.recalculate_standings(tournament)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'success': True,
                'match_id': match_obj.id,
                'result': match_obj.result,
                'white_score': match_obj.white_score,
                'black_score': match_obj.black_score,
                'message': 'Result updated and standings recalculated successfully.'
            })

        messages.success(request, f"Board {match_obj.board_number} result updated to {match_obj.result}.")

    rd_num = match_obj.round.round_number
    return redirect(f"/tournaments/{tournament.slug}/arbiter/?rd={rd_num}")


@require_POST
def bulk_update_results(request, slug):
    """Saves multiple board results at once."""
    tournament = get_object_or_404(Tournament, slug=slug)
    round_id = request.POST.get('round_id')
    round_obj = get_object_or_404(Round, id=round_id, tournament=tournament)

    updated_count = 0
    for match in round_obj.matches.all():
        result_key = f"result_{match.id}"
        remarks_key = f"remarks_{match.id}"
        if result_key in request.POST:
            res = request.POST[result_key]
            rem = request.POST.get(remarks_key, '')
            if res != match.result or rem != match.remarks:
                match.result = res
                match.remarks = rem
                match.save()
                updated_count += 1

    TieBreakCalculator.recalculate_standings(tournament)
    messages.success(request, f"Updated {updated_count} match results for Round {round_obj.round_number}. Standings refreshed!")
    return redirect(f"/tournaments/{tournament.slug}/arbiter/?rd={round_obj.round_number}")


@require_POST
def recalculate_standings_view(request, slug):
    """Forces standings and tiebreak recalculation."""
    tournament = get_object_or_404(Tournament, slug=slug)
    TieBreakCalculator.recalculate_standings(tournament)
    messages.success(request, "Tournament standings and tiebreaks recalculated successfully.")
    return redirect(f"{tournament.get_absolute_url()}?art=4")


def seed_demo_data(request):
    """
    Creates a full demo tournament preloaded with 16 Grandmasters/Masters,
    generates 3 completed rounds with authentic scores, and Round 4 ready to pair/update!
    """
    DEMO_PLAYERS = [
        {"name": "Carlsen, Magnus", "title": "GM", "rating": 2832, "federation": "NOR", "fide_id": "1503014", "gender": "M"},
        {"name": "Nakamura, Hikaru", "title": "GM", "rating": 2802, "federation": "USA", "fide_id": "2016192", "gender": "M"},
        {"name": "Gukesh, D", "title": "GM", "rating": 2794, "federation": "IND", "fide_id": "46616543", "gender": "M"},
        {"name": "Caruana, Fabiano", "title": "GM", "rating": 2805, "federation": "USA", "fide_id": "2020009", "gender": "M"},
        {"name": "Erigaisi, Arjun", "title": "GM", "rating": 2797, "federation": "IND", "fide_id": "35009192", "gender": "M"},
        {"name": "Praggnanandhaa, R", "title": "GM", "rating": 2750, "federation": "IND", "fide_id": "25059530", "gender": "M"},
        {"name": "Firouzja, Alireza", "title": "GM", "rating": 2767, "federation": "FRA", "fide_id": "12573981", "gender": "M"},
        {"name": "Nepomniachtchi, Ian", "title": "GM", "rating": 2755, "federation": "FID", "fide_id": "4168119", "gender": "M"},
        {"name": "Vachier-Lagrave, Maxime", "title": "GM", "rating": 2740, "federation": "FRA", "fide_id": "623539", "gender": "M"},
        {"name": "Vidit, Santosh Gujrathi", "title": "GM", "rating": 2720, "federation": "IND", "fide_id": "5029465", "gender": "M"},
        {"name": "Hou, Yifan", "title": "GM", "rating": 2633, "federation": "CHN", "fide_id": "8602980", "gender": "F"},
        {"name": "Ju, Wenjun", "title": "GM", "rating": 2560, "federation": "CHN", "fide_id": "8603006", "gender": "F"},
        {"name": "Vaishali, Rameshbabu", "title": "GM", "rating": 2505, "federation": "IND", "fide_id": "25060783", "gender": "F"},
        {"name": "Divya, Deshmukh", "title": "WGM", "rating": 2470, "federation": "IND", "fide_id": "35015095", "gender": "F"},
        {"name": "Nihal, Sarin", "title": "GM", "rating": 2670, "federation": "IND", "fide_id": "25092340", "gender": "M"},
        {"name": "Keymer, Vincent", "title": "GM", "rating": 2730, "federation": "GER", "fide_id": "12940690", "gender": "M"},
    ]

    t, created = Tournament.objects.get_or_create(
        slug="chennai-grand-masters-open-2026",
        defaults={
            'name': '10th Chennai Grandmasters International Chess Open 2026',
            'tournament_code': 'tnr1263143',
            'tournament_system': 'SWISS',
            'status': 'ACTIVE',
            'time_control_type': 'CLASSICAL',
            'time_control': '90 min + 30 sec increment',
            'rounds_count': 7,
            'federation': 'IND',
            'city': 'Chennai',
            'venue': 'Leela Palace Grand Ballroom',
            'chief_arbiter': 'IA Swapnil Bansod (FIDE)',
            'deputy_arbiter': 'FA Ananya Sen',
            'organizer': 'All India Chess Federation (AICF)',
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=7),
            'description': 'Premier FIDE Category tournament featuring world elite grandmasters and national stars.',
            'rules_and_prizes': 'Total Prize Fund: $100,000\n1st Place: $30,000\nTiebreaks: Buchholz Cut 1, Buchholz, Sonneborn-Berger'
        }
    )

    # Register players
    for p_data in DEMO_PLAYERS:
        player, _ = Player.objects.get_or_create(
            name=p_data['name'],
            defaults=p_data
        )
        TournamentParticipant.objects.get_or_create(
            tournament=t,
            player=player
        )

    # Initialize ranks
    SwissEngine.initialize_starting_ranks(t)

    # If rounds don't exist, generate round 1, round 2, round 3 with results
    if t.rounds.count() == 0:
        # Round 1
        SwissEngine.generate_pairings_for_round(t, 1)
        r1 = t.rounds.get(round_number=1)
        for i, m in enumerate(r1.matches.all()):
            # Simulate realistic results: top seeds mostly win or have a fighting draw
            if i in [0, 1, 2, 4, 6]:
                m.result = '1-0'
            elif i in [3, 5]:
                m.result = '1/2-1/2'
            else:
                m.result = '0-1'
            m.save()

        # Round 2
        SwissEngine.generate_pairings_for_round(t, 2)
        r2 = t.rounds.get(round_number=2)
        for i, m in enumerate(r2.matches.all()):
            if i in [0, 2, 5]:
                m.result = '1/2-1/2'
            elif i in [1, 3]:
                m.result = '1-0'
            else:
                m.result = '0-1'
            m.save()

        # Round 3
        SwissEngine.generate_pairings_for_round(t, 3)
        r3 = t.rounds.get(round_number=3)
        for i, m in enumerate(r3.matches.all()):
            if i in [0, 1]:
                m.result = '1-0'
            elif i in [2, 4]:
                m.result = '1/2-1/2'
            else:
                m.result = '0-1'
            m.save()

        # Generate Round 4 fixtures ready for live entry
        SwissEngine.generate_pairings_for_round(t, 4)

    TieBreakCalculator.recalculate_standings(t)
    messages.success(request, f"Demo tournament '{t.name}' (Code: {t.tournament_code}) loaded with 16 Grandmasters, 3 completed rounds, and Round 4 ready!")
    return redirect(f"{t.get_absolute_url()}?art=2&rd=4")


def _build_crosstable(tournament: Tournament):
    """Helper to create matrix crosstable data like Chess-Results."""
    participants = list(tournament.participants.select_related('player').order_by(
        '-current_points', '-buchholz_cut1', '-buchholz', '-sonneborn_berger', 'starting_rank'
    ))
    rank_lookup = {p.id: idx + 1 for idx, p in enumerate(participants)}
    starting_rank_lookup = {p.id: p.starting_rank for p in participants}

    rounds = list(tournament.rounds.order_by('round_number'))
    all_matches = Match.objects.filter(round__tournament=tournament).select_related(
        'round', 'white_participant', 'black_participant'
    )

    # map (participant_id, round_number) -> result_string (e.g. '12w1', '4b0', '7w½', 'Bye 1')
    matrix_results = {}
    for m in all_matches:
        rd_num = m.round.round_number
        if m.result.endswith('BYE'):
            if m.white_participant:
                score_str = "1" if "1-0" in m.result else ("½" if "1/2" in m.result else "0")
                matrix_results[(m.white_participant.id, rd_num)] = f"Bye ({score_str})"
            elif m.black_participant:
                score_str = "1" if "1-0" in m.result else ("½" if "1/2" in m.result else "0")
                matrix_results[(m.black_participant.id, rd_num)] = f"Bye ({score_str})"
            continue

        if m.white_participant and m.black_participant:
            w_id = m.white_participant.id
            b_id = m.black_participant.id
            w_start_rk = starting_rank_lookup.get(w_id, "")
            b_start_rk = starting_rank_lookup.get(b_id, "")

            if m.result == '1-0' or m.result == '1-0_FF':
                matrix_results[(w_id, rd_num)] = f"{b_start_rk}w1"
                matrix_results[(b_id, rd_num)] = f"{w_start_rk}b0"
            elif m.result == '0-1' or m.result == '0-1_FF':
                matrix_results[(w_id, rd_num)] = f"{b_start_rk}w0"
                matrix_results[(b_id, rd_num)] = f"{w_start_rk}b1"
            elif m.result == '1/2-1/2':
                matrix_results[(w_id, rd_num)] = f"{b_start_rk}w½"
                matrix_results[(b_id, rd_num)] = f"{w_start_rk}b½"
            else:
                matrix_results[(w_id, rd_num)] = f"{b_start_rk}w*"
                matrix_results[(b_id, rd_num)] = f"{w_start_rk}b*"

    crosstable_rows = []
    for idx, p in enumerate(participants, start=1):
        round_cells = []
        for r in rounds:
            cell_val = matrix_results.get((p.id, r.round_number), "-")
            round_cells.append({
                'round_num': r.round_number,
                'value': cell_val
            })
        crosstable_rows.append({
            'rank': idx,
            'starting_rank': p.starting_rank,
            'participant': p,
            'player': p.player,
            'rounds': round_cells,
            'points': p.current_points,
            'buchholz_cut1': p.buchholz_cut1,
            'buchholz': p.buchholz,
            'sonneborn_berger': p.sonneborn_berger,
            'wins': p.wins_count,
        })

    return crosstable_rows
