"""
Chess Tournament Pairing Engine & Tie-Break Calculator
Supports FIDE Swiss-System pairing principles and Round Robin scheduling.
Calculates official chess tiebreaks: Buchholz, Buchholz Cut 1, Sonneborn-Berger, Direct Encounter.
"""

from typing import List, Tuple, Optional, Dict
from django.db import transaction
from .models import Tournament, TournamentParticipant, Round, Match


class TieBreakCalculator:
    """
    Computes all standard chess tournament standings and tiebreaks for a tournament.
    """
    @classmethod
    def recalculate_standings(cls, tournament: Tournament):
        participants = list(tournament.participants.select_related('player').all())
        participant_map = {p.id: p for p in participants}
        
        # Step 1: Reset scores and gather match histories
        # player_id -> list of (opponent_participant_id, my_score, opponent_score, is_bye)
        match_history: Dict[int, List[dict]] = {p.id: [] for p in participants}
        
        # Get all completed or scored matches in this tournament
        matches = Match.objects.filter(
            round__tournament=tournament
        ).select_related('round', 'white_participant', 'black_participant').all()
        
        for m in matches:
            if m.white_score is None and m.black_score is None:
                continue
                
            w_id = m.white_participant_id if m.white_participant else None
            b_id = m.black_participant_id if m.black_participant else None
            
            w_score = m.white_score if m.white_score is not None else 0.0
            b_score = m.black_score if m.black_score is not None else 0.0
            
            if w_id and b_id:
                # Regular match
                match_history[w_id].append({
                    'opp_id': b_id,
                    'my_score': w_score,
                    'opp_score': b_score,
                    'is_bye': False,
                    'color': 'W',
                    'match_id': m.id
                })
                match_history[b_id].append({
                    'opp_id': w_id,
                    'my_score': b_score,
                    'opp_score': w_score,
                    'is_bye': False,
                    'color': 'B',
                    'match_id': m.id
                })
            elif w_id and not b_id:
                # White bye
                match_history[w_id].append({
                    'opp_id': None,
                    'my_score': w_score,
                    'opp_score': 0.0,
                    'is_bye': True,
                    'color': 'W',
                    'match_id': m.id
                })
            elif b_id and not w_id:
                # Black bye
                match_history[b_id].append({
                    'opp_id': None,
                    'my_score': b_score,
                    'opp_score': 0.0,
                    'is_bye': True,
                    'color': 'B',
                    'match_id': m.id
                })

        # Calculate base points & wins
        for p in participants:
            history = match_history[p.id]
            p.current_points = sum(item['my_score'] for item in history)
            p.wins_count = sum(1 for item in history if item['my_score'] == 1.0)
            
            # Check color streak
            streak = 0
            for item in history:
                if not item['is_bye']:
                    if item['color'] == 'W':
                        streak += 1
                    else:
                        streak -= 1
            p.color_streak = streak

        # Map current points for fast lookup
        points_map = {p.id: p.current_points for p in participants}

        # Step 2: Compute Buchholz, Buchholz Cut 1, and Sonneborn-Berger
        for p in participants:
            history = match_history[p.id]
            opp_scores = []
            sb = 0.0
            
            for item in history:
                opp_id = item['opp_id']
                my_sc = item['my_score']
                
                if opp_id is not None and opp_id in points_map:
                    opp_pts = points_map[opp_id]
                    opp_scores.append(opp_pts)
                    if my_sc == 1.0:
                        sb += opp_pts
                    elif my_sc == 0.5:
                        sb += 0.5 * opp_pts
                else:
                    # In case of bye or unassigned
                    pass
                    
            bh = sum(opp_scores)
            if len(opp_scores) > 1:
                bh_cut1 = bh - min(opp_scores)
            else:
                bh_cut1 = bh
                
            p.buchholz = round(bh, 2)
            p.buchholz_cut1 = round(bh_cut1, 2)
            p.sonneborn_berger = round(sb, 2)
            p.save()


class SwissEngine:
    """
    Swiss Pairing Engine:
    - Round 1: Top half seeded against bottom half
    - Subsequent rounds: Score group bracket pairings with color alternate rules & rematch avoidance
    """
    @classmethod
    def initialize_starting_ranks(cls, tournament: Tournament):
        """Sorts registered participants by rating DESC, title rank, name and sets starting_rank."""
        TITLE_RANKS = {
            'GM': 1, 'WGM': 2, 'IM': 3, 'WIM': 4,
            'FM': 5, 'WFM': 6, 'CM': 7, 'WCM': 8, 'NONE': 9
        }
        participants = list(tournament.participants.select_related('player').all())
        participants.sort(
            key=lambda p: (
                -p.player.rating,
                TITLE_RANKS.get(p.player.title, 9),
                p.player.name.lower()
            )
        )
        for index, p in enumerate(participants, start=1):
            p.starting_rank = index
            p.save()

    @classmethod
    def get_past_opponents(cls, tournament: Tournament) -> Dict[int, set]:
        """Returns map of participant_id -> set of opponent participant_ids faced in past rounds."""
        opponents_map: Dict[int, set] = {p.id: set() for p in tournament.participants.all()}
        matches = Match.objects.filter(
            round__tournament=tournament
        ).select_related('white_participant', 'black_participant')
        
        for m in matches:
            if m.white_participant and m.black_participant:
                opponents_map[m.white_participant.id].add(m.black_participant.id)
                opponents_map[m.black_participant.id].add(m.white_participant.id)
        return opponents_map

    @classmethod
    def get_color_histories(cls, tournament: Tournament) -> Dict[int, List[str]]:
        """Returns map of participant_id -> list of colors played ('W' or 'B') in past rounds."""
        colors_map: Dict[int, List[str]] = {p.id: [] for p in tournament.participants.all()}
        rounds = Round.objects.filter(tournament=tournament).order_by('round_number')
        
        for r in rounds:
            for m in r.matches.all():
                if m.result.endswith('BYE'):
                    continue
                if m.white_participant and m.white_participant.id in colors_map:
                    colors_map[m.white_participant.id].append('W')
                if m.black_participant and m.black_participant.id in colors_map:
                    colors_map[m.black_participant.id].append('B')
        return colors_map

    @classmethod
    @transaction.atomic
    def generate_pairings_for_round(cls, tournament: Tournament, round_number: int) -> Tuple[bool, str]:
        """Generates pairings for the given round number."""
        # Ensure ranks and standings are fresh
        if round_number == 1:
            cls.initialize_starting_ranks(tournament)
        else:
            TieBreakCalculator.recalculate_standings(tournament)

        round_obj, _ = Round.objects.get_or_create(
            tournament=tournament,
            round_number=round_number
        )

        if round_obj.matches.exists():
            return False, f"Round {round_number} already has pairings generated."

        active_participants = list(
            tournament.participants.filter(is_active=True).select_related('player')
        )
        
        if len(active_participants) < 2:
            return False, "Not enough active participants to pair (minimum 2 required)."

        past_opponents = cls.get_past_opponents(tournament)
        color_histories = cls.get_color_histories(tournament)

        # Handle Odd participant count with a BYE
        bye_participant = None
        if len(active_participants) % 2 != 0:
            # Pick lowest point / lowest seeded participant who hasn't had a bye yet
            candidates = [p for p in active_participants if not p.received_bye]
            if not candidates:
                candidates = active_participants
            # Sort candidate by points asc, then starting_rank desc (lowest rated)
            candidates.sort(key=lambda p: (p.current_points, -p.starting_rank))
            bye_participant = candidates[0]
            bye_participant.received_bye = True
            bye_participant.save()
            active_participants = [p for p in active_participants if p.id != bye_participant.id]

        pairings: List[Tuple[TournamentParticipant, TournamentParticipant]] = []

        if round_number == 1:
            # Round 1: Classical Swiss top-half vs bottom-half
            active_participants.sort(key=lambda p: p.starting_rank)
            half = len(active_participants) // 2
            top_half = active_participants[:half]
            bottom_half = active_participants[half:]

            for i in range(half):
                p1 = top_half[i]
                p2 = bottom_half[i]
                # Alternate board 1 (White for higher seed), board 2 (Black for higher seed)
                if i % 2 == 0:
                    pairings.append((p1, p2))
                else:
                    pairings.append((p2, p1))
        else:
            # Round 2+: Sort by points DESC, then Buchholz DESC, then starting_rank ASC
            active_participants.sort(key=lambda p: (-p.current_points, -p.buchholz_cut1, p.starting_rank))
            
            # Recursive backtracking pairing engine with fallback
            paired_tuples = cls._pair_swiss_recursive(
                players=active_participants,
                past_opponents=past_opponents,
                color_histories=color_histories
            )

            if not paired_tuples:
                # Fallback greedy pairing if strict criteria couldn't find a solution
                paired_tuples = cls._pair_greedy_fallback(
                    players=active_participants,
                    past_opponents=past_opponents
                )

            pairings = paired_tuples

        # Create Match objects for this round
        board_num = 1
        for white_p, black_p in pairings:
            Match.objects.create(
                round=round_obj,
                board_number=board_num,
                white_participant=white_p,
                black_participant=black_p,
                result='*'
            )
            board_num += 1

        # If there is a BYE
        if bye_participant:
            Match.objects.create(
                round=round_obj,
                board_number=board_num,
                white_participant=bye_participant,
                black_participant=None,
                result='1-0_BYE',
                remarks='Full Point Bye'
            )

        round_obj.is_paired = True
        round_obj.save()

        # Update tournament current round
        if tournament.current_round_num < round_number:
            tournament.current_round_num = round_number
            if tournament.status == 'UPCOMING':
                tournament.status = 'ACTIVE'
            tournament.save()

        # Recalculate standings so bye score reflects immediately
        TieBreakCalculator.recalculate_standings(tournament)

        return True, f"Successfully generated pairings for Round {round_number} ({len(pairings)} boards{' + 1 Bye' if bye_participant else ''})."

    @classmethod
    def _choose_colors(cls, p1: TournamentParticipant, p2: TournamentParticipant, 
                        color_histories: Dict[int, List[str]]) -> Tuple[TournamentParticipant, TournamentParticipant]:
        """Determines who plays White and who plays Black based on past color preferences."""
        h1 = color_histories.get(p1.id, [])
        h2 = color_histories.get(p2.id, [])
        
        w1_count = h1.count('W')
        b1_count = h1.count('B')
        pref1 = w1_count - b1_count  # >0 means has more Whites -> wants Black
        
        w2_count = h2.count('W')
        b2_count = h2.count('B')
        pref2 = w2_count - b2_count
        
        # If one strongly wants White and other wants Black
        if pref1 < pref2:
            return p1, p2  # p1 gets White
        elif pref2 < pref1:
            return p2, p1  # p2 gets White
            
        # If equal, check last round color (alternate)
        last1 = h1[-1] if h1 else None
        last2 = h2[-1] if h2 else None
        
        if last1 == 'B' and last2 == 'W':
            return p1, p2
        elif last1 == 'W' and last2 == 'B':
            return p2, p1
            
        # Default: higher ranked player alternates based on round or gets White
        if p1.starting_rank < p2.starting_rank:
            return (p1, p2) if (len(h1) % 2 == 0) else (p2, p1)
        return (p2, p1) if (len(h2) % 2 == 0) else (p1, p2)

    @classmethod
    def _pair_swiss_recursive(cls, players: List[TournamentParticipant], 
                               past_opponents: Dict[int, set], 
                               color_histories: Dict[int, List[str]]) -> Optional[List[Tuple[TournamentParticipant, TournamentParticipant]]]:
        """Backtracking search for valid Swiss pairings with no repeat matchups."""
        if not players:
            return []

        p1 = players[0]
        rest = players[1:]

        for i, p2 in enumerate(rest):
            # Check if they have already played
            if p2.id not in past_opponents.get(p1.id, set()):
                # Determine colors
                white_p, black_p = cls._choose_colors(p1, p2, color_histories)
                
                # Recurse for remaining players
                remaining = rest[:i] + rest[i+1:]
                sub_pairings = cls._pair_swiss_recursive(remaining, past_opponents, color_histories)
                if sub_pairings is not None:
                    return [(white_p, black_p)] + sub_pairings

        return None

    @classmethod
    def _pair_greedy_fallback(cls, players: List[TournamentParticipant], past_opponents: Dict[int, set]):
        """Fallback pairer when strict pairing has graph dead-ends."""
        unpaired = list(players)
        pairings = []
        
        while len(unpaired) >= 2:
            p1 = unpaired.pop(0)
            best_idx = 0
            # Prefer someone they haven't played
            for i, cand in enumerate(unpaired):
                if cand.id not in past_opponents.get(p1.id, set()):
                    best_idx = i
                    break
            p2 = unpaired.pop(best_idx)
            pairings.append((p1, p2))
            
        return pairings


class RoundRobinEngine:
    """
    Generates all round fixtures for a Round Robin tournament (Berger tables).
    """
    @classmethod
    @transaction.atomic
    def generate_all_fixtures(cls, tournament: Tournament) -> Tuple[bool, str]:
        SwissEngine.initialize_starting_ranks(tournament)
        participants = list(tournament.participants.order_by('starting_rank').all())
        n = len(participants)
        
        if n < 2:
            return False, "At least 2 players are required for Round Robin."

        # If odd number of players, add a dummy participant for BYE
        has_ghost = (n % 2 != 0)
        players = list(participants)
        if has_ghost:
            players.append(None)
            n += 1

        num_rounds = n - 1
        tournament.rounds_count = num_rounds
        tournament.save()

        # Circle algorithm for Berger schedule
        for r_num in range(1, num_rounds + 1):
            round_obj, _ = Round.objects.get_or_create(
                tournament=tournament,
                round_number=r_num
            )
            round_obj.matches.all().delete()

            board_num = 1
            for i in range(n // 2):
                p1 = players[i]
                p2 = players[n - 1 - i]

                if p1 is None or p2 is None:
                    real_p = p1 if p1 else p2
                    Match.objects.create(
                        round=round_obj,
                        board_number=board_num,
                        white_participant=real_p,
                        black_participant=None,
                        result='1-0_BYE',
                        remarks='Round Robin Bye'
                    )
                else:
                    # Alternate colors for balance
                    if (r_num + i) % 2 == 0:
                        w, b = p1, p2
                    else:
                        w, b = p2, p1
                    Match.objects.create(
                        round=round_obj,
                        board_number=board_num,
                        white_participant=w,
                        black_participant=b,
                        result='*'
                    )
                board_num += 1

            round_obj.is_paired = True
            round_obj.save()

            # Rotate array: keep players[0] fixed, rotate the rest
            players = [players[0]] + [players[-1]] + players[1:-1]

        tournament.status = 'ACTIVE'
        tournament.current_round_num = 1
        tournament.save()
        TieBreakCalculator.recalculate_standings(tournament)
        return True, f"Generated complete {num_rounds}-round Round Robin schedule successfully."
