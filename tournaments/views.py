import json
import random
from datetime import date, timedelta
from functools import wraps
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.urls import reverse

from .models import Tournament, Player, TournamentParticipant, Round, Match, UserProfile
from .forms import (
    TournamentForm, PlayerRegistrationForm, MatchResultUpdateForm, PlayerForm,
    PlayerSignUpForm, OrganiserSignUpForm, LoginForm
)
from .engine import SwissEngine, RoundRobinEngine, TieBreakCalculator


def organiser_required(view_func):
    """
    Decorator requiring the user to be authenticated with an Organiser profile credentials.
    If a Player attempts to access, displays an informative permission restriction view.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.warning(request, "Please log in with your Organiser credentials to access the Admin Dashboard & Arbiter tools.")
            return redirect(f"{reverse('login')}?next={request.get_full_path()}")
        
        profile = getattr(request.user, 'profile', None)
        if not (profile and profile.is_organiser):
            return render(request, 'tournaments/access_denied.html', {
                'title': 'Organiser Credentials Required',
                'message': 'The Admin Dashboard, Tournament Editing, and Arbiter stations are restricted to verified Organiser accounts. You are currently logged in with a Player profile.',
                'profile': profile,
            }, status=403)
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def signup_view(request):
    """Sign up view for creating either Player profile or Organiser profile."""
    if request.user.is_authenticated:
        return redirect('user_profile')

    account_type = request.GET.get('type', 'player')
    
    player_form = PlayerSignUpForm()
    organiser_form = OrganiserSignUpForm()

    if request.method == 'POST':
        submitted_type = request.POST.get('account_type', 'player')
        if submitted_type == 'player':
            player_form = PlayerSignUpForm(request.POST)
            if player_form.is_valid():
                username = player_form.cleaned_data['username'].strip()
                email = player_form.cleaned_data['email'].strip()
                password = player_form.cleaned_data['password']
                name = player_form.cleaned_data['name'].strip()
                title = player_form.cleaned_data.get('title', 'NONE')
                rating = player_form.cleaned_data.get('rating', 1200)
                fide_id = player_form.cleaned_data.get('fide_id') or None
                federation = player_form.cleaned_data.get('federation', 'IND')
                club_or_city = player_form.cleaned_data.get('club_or_city', '')
                birth_year = player_form.cleaned_data.get('birth_year')
                gender = player_form.cleaned_data.get('gender', 'M')
                phone = player_form.cleaned_data.get('phone', '')

                if User.objects.filter(username__iexact=username).exists():
                    player_form.add_error('username', "Username is already taken. Please choose another.")
                elif User.objects.filter(email__iexact=email).exists():
                    player_form.add_error('email', "An account with this email address already exists.")
                else:
                    user = User.objects.create_user(username=username, email=email, password=password)
                    user.first_name = name
                    user.save()

                    # Find or create Player record
                    player = None
                    if fide_id:
                        player = Player.objects.filter(fide_id=fide_id).first()
                    if not player:
                        player = Player.objects.filter(name__iexact=name).first()
                    if not player:
                        player = Player.objects.create(
                            name=name,
                            fide_id=fide_id,
                            title=title,
                            rating=rating,
                            federation=federation,
                            club_or_city=club_or_city,
                            birth_year=birth_year,
                            gender=gender,
                            email=email,
                            phone=phone,
                        )
                    else:
                        player.rating = rating
                        player.title = title
                        player.email = email
                        player.phone = phone
                        player.save()

                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.role = 'PLAYER'
                    profile.player = player
                    profile.phone = phone
                    profile.save()

                    login(request, user)
                    messages.success(request, f"Welcome {name}! Your Player account has been registered successfully.")
                    return redirect('user_profile')
            account_type = 'player'

        elif submitted_type == 'organiser':
            organiser_form = OrganiserSignUpForm(request.POST)
            if organiser_form.is_valid():
                username = organiser_form.cleaned_data['username'].strip()
                email = organiser_form.cleaned_data['email'].strip()
                password = organiser_form.cleaned_data['password']
                name = organiser_form.cleaned_data['name'].strip()
                organization_name = organiser_form.cleaned_data.get('organization_name', '')
                arbiter_title = organiser_form.cleaned_data.get('arbiter_title', '')
                federation = organiser_form.cleaned_data.get('federation', 'IND')
                phone = organiser_form.cleaned_data.get('phone', '')

                if User.objects.filter(username__iexact=username).exists():
                    organiser_form.add_error('username', "Username is already taken. Please choose another.")
                elif User.objects.filter(email__iexact=email).exists():
                    organiser_form.add_error('email', "An account with this email address already exists.")
                else:
                    user = User.objects.create_user(username=username, email=email, password=password)
                    user.first_name = name
                    user.is_staff = True
                    user.save()

                    profile, _ = UserProfile.objects.get_or_create(user=user)
                    profile.role = 'ORGANISER'
                    profile.organization_name = organization_name
                    profile.arbiter_title = arbiter_title
                    profile.phone = phone
                    profile.save()

                    login(request, user)
                    messages.success(request, f"Welcome Organiser {name}! Your Organiser credentials are ready. Admin Dashboard is now unlocked.")
                    return redirect('admin_dashboard')
            account_type = 'organiser'

    return render(request, 'tournaments/signup.html', {
        'account_type': account_type,
        'player_form': player_form,
        'organiser_form': organiser_form,
    })


def login_view(request):
    """Login view for Organisers and Players."""
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile.is_organiser:
            return redirect('admin_dashboard')
        return redirect('user_profile')

    next_url = request.GET.get('next') or request.POST.get('next', '')
    form = LoginForm()

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                profile = getattr(user, 'profile', None)
                if profile and profile.is_organiser:
                    messages.success(request, f"Welcome back, Organiser {user.first_name or user.username}! Admin Dashboard unlocked.")
                    if next_url:
                        return redirect(next_url)
                    return redirect('admin_dashboard')
                else:
                    messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                    if next_url:
                        return redirect(next_url)
                    return redirect('user_profile')
            else:
                messages.error(request, "Invalid username or password. Please check your credentials.")

    return render(request, 'tournaments/login.html', {
        'form': form,
        'next': next_url,
    })


def logout_view(request):
    """Logout view."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('tournament_list')


def user_profile(request):
    """Profile page for the logged-in user."""
    if not request.user.is_authenticated:
        return redirect('login')

    profile = getattr(request.user, 'profile', None)
    player = profile.player if profile else None

    # Player stats & matches
    tournaments_entered = []
    player_matches = []
    total_wins = 0
    total_draws = 0
    total_losses = 0

    if player:
        tournaments_entered = player.tournament_entries.select_related('tournament').order_by('-registered_at')
        
        white_matches = Match.objects.filter(white_participant__player=player).select_related('round__tournament', 'black_participant__player')
        black_matches = Match.objects.filter(black_participant__player=player).select_related('round__tournament', 'white_participant__player')
        
        for m in white_matches:
            if m.white_score == 1.0:
                total_wins += 1
            elif m.white_score == 0.5:
                total_draws += 1
            elif m.white_score == 0.0:
                total_losses += 1
            player_matches.append({
                'round_number': m.round.round_number,
                'tournament': m.round.tournament,
                'color': 'White',
                'opponent': m.black_participant.player if m.black_participant else None,
                'result': m.result,
                'score': m.white_score,
                'pgn': m.pgn,
            })
            
        for m in black_matches:
            if m.black_score == 1.0:
                total_wins += 1
            elif m.black_score == 0.5:
                total_draws += 1
            elif m.black_score == 0.0:
                total_losses += 1
            player_matches.append({
                'round_number': m.round.round_number,
                'tournament': m.round.tournament,
                'color': 'Black',
                'opponent': m.white_participant.player if m.white_participant else None,
                'result': m.result,
                'score': m.black_score,
                'pgn': m.pgn,
            })

    # Organiser managed tournaments
    managed_tournaments = []
    if profile and profile.is_organiser:
        managed_tournaments = Tournament.objects.all().order_by('-created_at')

    context = {
        'profile': profile,
        'player': player,
        'tournaments_entered': tournaments_entered,
        'player_matches': player_matches,
        'total_wins': total_wins,
        'total_draws': total_draws,
        'total_losses': total_losses,
        'managed_tournaments': managed_tournaments,
    }
    return render(request, 'tournaments/user_profile.html', context)


@organiser_required
def admin_dashboard(request):
    """
    Comprehensive In-App Admin Dashboard:
    - Central control station for all tournaments and players
    - Quick tournament actions: Create, Edit, Delete, Arbiter Station, Recalculate
    - Player database overview & editing
    - Real-time tournament statistics and pairing status
    """
    q_tournament = request.GET.get('qt', '').strip()
    status_filter = request.GET.get('status', '').strip()
    system_filter = request.GET.get('system', '').strip()
    
    q_player = request.GET.get('qp', '').strip()
    title_filter = request.GET.get('title', '').strip()
    
    active_tab = request.GET.get('tab', 'tournaments')

    # Tournaments Query
    tournaments_qs = Tournament.objects.prefetch_related('participants', 'rounds').all()
    if q_tournament:
        tournaments_qs = tournaments_qs.filter(
            Q(name__icontains=q_tournament) |
            Q(tournament_code__icontains=q_tournament) |
            Q(city__icontains=q_tournament) |
            Q(chief_arbiter__icontains=q_tournament) |
            Q(federation__icontains=q_tournament)
        )
    if status_filter:
        tournaments_qs = tournaments_qs.filter(status=status_filter)
    if system_filter:
        tournaments_qs = tournaments_qs.filter(tournament_system=system_filter)

    # Players Query
    players_qs = Player.objects.all()
    if q_player:
        players_qs = players_qs.filter(
            Q(name__icontains=q_player) |
            Q(fide_id__icontains=q_player) |
            Q(federation__icontains=q_player) |
            Q(club_or_city__icontains=q_player)
        )
    if title_filter:
        players_qs = players_qs.filter(title=title_filter)

    # Pagination for players (25 per page)
    player_paginator = Paginator(players_qs, 25)
    player_page_number = request.GET.get('player_page', 1)
    players_page = player_paginator.get_page(player_page_number)

    # Global Stats
    total_tournaments = Tournament.objects.count()
    active_tournaments = Tournament.objects.filter(status='ACTIVE').count()
    upcoming_tournaments = Tournament.objects.filter(status='UPCOMING').count()
    finished_tournaments = Tournament.objects.filter(status='FINISHED').count()
    
    total_players = Player.objects.count()
    titled_players = Player.objects.exclude(title='NONE').count()
    total_matches = Match.objects.count()
    completed_matches = Match.objects.exclude(result='*').count()

    # Active tournaments needing arbiter attention
    active_tournaments_list = Tournament.objects.filter(status='ACTIVE').order_by('-created_at')[:5]

    # Form for adding player directly from dashboard
    player_form = PlayerForm()

    context = {
        'tournaments': tournaments_qs,
        'players': players_page,
        'active_tab': active_tab,
        'q_tournament': q_tournament,
        'status_filter': status_filter,
        'system_filter': system_filter,
        'q_player': q_player,
        'title_filter': title_filter,
        'total_tournaments': total_tournaments,
        'active_tournaments': active_tournaments,
        'upcoming_tournaments': upcoming_tournaments,
        'finished_tournaments': finished_tournaments,
        'total_players': total_players,
        'titled_players': titled_players,
        'total_matches': total_matches,
        'completed_matches': completed_matches,
        'active_tournaments_list': active_tournaments_list,
        'player_form': player_form,
        'title_choices': Player.TITLE_CHOICES,
    }
    return render(request, 'tournaments/admin_dashboard.html', context)


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


@organiser_required
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
        form = TournamentForm(initial={'start_date': start, 'end_date': end, 'status': 'UPCOMING'})

    return render(request, 'tournaments/tournament_create.html', {'form': form})


@organiser_required
def tournament_edit(request, slug):
    """Edit existing tournament configuration."""
    tournament = get_object_or_404(Tournament, slug=slug)

    if request.method == 'POST':
        form = TournamentForm(request.POST, instance=tournament)
        if form.is_valid():
            tournament = form.save()
            messages.success(request, f"Tournament '{tournament.name}' updated successfully!")
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url == 'admin':
                return redirect('admin_dashboard')
            return redirect('tournament_detail', slug=tournament.slug)
    else:
        form = TournamentForm(instance=tournament)

    return render(request, 'tournaments/tournament_edit.html', {
        'form': form,
        'tournament': tournament,
        'next': request.GET.get('next', '')
    })


@organiser_required
def tournament_delete(request, slug):
    """Safely delete tournament and all associated rounds, pairings, and participants."""
    tournament = get_object_or_404(Tournament, slug=slug)

    if request.method == 'POST':
        tournament_name = tournament.name
        tournament_code = tournament.tournament_code
        tournament.delete()
        messages.success(request, f"Tournament '{tournament_name}' ({tournament_code}) and all related fixtures have been permanently deleted.")
        return redirect('admin_dashboard')

    # GET: show delete confirmation details
    participants_count = tournament.participants.count()
    rounds_count = tournament.rounds.count()
    matches_count = Match.objects.filter(round__tournament=tournament).count()

    return render(request, 'tournaments/tournament_delete.html', {
        'tournament': tournament,
        'participants_count': participants_count,
        'rounds_count': rounds_count,
        'matches_count': matches_count,
    })


@organiser_required
def player_create(request):
    """Create a player directly from admin station."""
    if request.method == 'POST':
        form = PlayerForm(request.POST)
        if form.is_valid():
            player = form.save()
            messages.success(request, f"Player '{player.name}' added to global registry.")
            return redirect(f"/dashboard/?tab=players")
        else:
            messages.error(request, "Failed to add player. Please check the form fields.")
    return redirect('admin_dashboard')


@organiser_required
def player_edit(request, player_id):
    """Edit existing player profile."""
    player = get_object_or_404(Player, id=player_id)
    if request.method == 'POST':
        form = PlayerForm(request.POST, instance=player)
        if form.is_valid():
            form.save()
            messages.success(request, f"Player '{player.name}' updated successfully.")
            return redirect(f"/dashboard/?tab=players")
    else:
        form = PlayerForm(instance=player)

    return render(request, 'tournaments/player_form.html', {
        'form': form,
        'player': player,
        'is_edit': True
    })


@organiser_required
def player_delete(request, player_id):
    """Delete a player from global registry."""
    player = get_object_or_404(Player, id=player_id)
    if request.method == 'POST':
        player_name = player.name
        player.delete()
        messages.success(request, f"Player '{player_name}' deleted successfully.")
    return redirect(f"/dashboard/?tab=players")


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


@organiser_required
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
@organiser_required
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
@organiser_required
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
@organiser_required
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
@organiser_required
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
