from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from .models import Tournament, Player, TournamentParticipant, Round, Match
from .engine import SwissEngine, RoundRobinEngine, TieBreakCalculator


class ChessTournamentEngineTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.tournament = Tournament.objects.create(
            name="World Masters Invitational 2026",
            tournament_code="tnr999999",
            tournament_system="SWISS",
            rounds_count=5,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=5),
            chief_arbiter="IA John Smith"
        )
        # Create 6 players with varied ratings
        self.players_data = [
            {"name": "Carlsen, Magnus", "title": "GM", "rating": 2830, "federation": "NOR"},
            {"name": "Nakamura, Hikaru", "title": "GM", "rating": 2800, "federation": "USA"},
            {"name": "Gukesh, D", "title": "GM", "rating": 2790, "federation": "IND"},
            {"name": "Caruana, Fabiano", "title": "GM", "rating": 2805, "federation": "USA"},
            {"name": "Erigaisi, Arjun", "title": "GM", "rating": 2795, "federation": "IND"},
            {"name": "Praggnanandhaa, R", "title": "GM", "rating": 2750, "federation": "IND"},
        ]
        self.participants = []
        for p_data in self.players_data:
            p = Player.objects.create(**p_data)
            tp = TournamentParticipant.objects.create(tournament=self.tournament, player=p)
            self.participants.append(tp)

    def test_starting_rank_initialization(self):
        SwissEngine.initialize_starting_ranks(self.tournament)
        top_seed = self.tournament.participants.get(starting_rank=1)
        self.assertEqual(top_seed.player.name, "Carlsen, Magnus")
        self.assertEqual(top_seed.player.rating, 2830)

    def test_round_1_swiss_pairing(self):
        success, msg = SwissEngine.generate_pairings_for_round(self.tournament, 1)
        self.assertTrue(success)
        r1 = self.tournament.rounds.get(round_number=1)
        self.assertEqual(r1.matches.count(), 3)  # 6 players -> 3 boards

        # In classical Swiss top-half vs bottom-half:
        # Seed 1 vs Seed 4
        # Seed 2 vs Seed 5
        # Seed 3 vs Seed 6
        m1 = r1.matches.get(board_number=1)
        self.assertIsNotNone(m1.white_participant)
        self.assertIsNotNone(m1.black_participant)

    def test_match_result_and_tiebreaks(self):
        SwissEngine.generate_pairings_for_round(self.tournament, 1)
        r1 = self.tournament.rounds.get(round_number=1)
        
        # Set scores: Board 1 White wins (1-0), Board 2 Draw (1/2-1/2), Board 3 Black wins (0-1)
        m1 = r1.matches.get(board_number=1)
        m1.result = '1-0'
        m1.save()

        m2 = r1.matches.get(board_number=2)
        m2.result = '1/2-1/2'
        m2.save()

        m3 = r1.matches.get(board_number=3)
        m3.result = '0-1'
        m3.save()

        TieBreakCalculator.recalculate_standings(self.tournament)

        # White on board 1 should have 1.0 point
        m1.white_participant.refresh_from_db()
        self.assertEqual(m1.white_participant.current_points, 1.0)
        self.assertEqual(m1.white_participant.wins_count, 1)

        # White on board 2 should have 0.5 points
        m2.white_participant.refresh_from_db()
        self.assertEqual(m2.white_participant.current_points, 0.5)

        # White on board 3 should have 0.0 points
        m3.white_participant.refresh_from_db()
        self.assertEqual(m3.white_participant.current_points, 0.0)

    def test_round_2_pairing_without_rematches(self):
        # Round 1
        SwissEngine.generate_pairings_for_round(self.tournament, 1)
        r1 = self.tournament.rounds.get(round_number=1)
        for m in r1.matches.all():
            m.result = '1-0'
            m.save()
        TieBreakCalculator.recalculate_standings(self.tournament)

        # Round 2
        success, msg = SwissEngine.generate_pairings_for_round(self.tournament, 2)
        self.assertTrue(success)
        r2 = self.tournament.rounds.get(round_number=2)
        self.assertEqual(r2.matches.count(), 3)

        # Ensure no repeat pairings between R1 and R2
        r1_pairs = set()
        for m in r1.matches.all():
            r1_pairs.add(frozenset([m.white_participant_id, m.black_participant_id]))

        for m in r2.matches.all():
            curr_pair = frozenset([m.white_participant_id, m.black_participant_id])
            self.assertNotIn(curr_pair, r1_pairs)

    def test_views_response(self):
        from django.test import RequestFactory
        from tournaments.views import tournament_list, tournament_detail, tournament_register
        
        rf = RequestFactory()
        
        # Test Tournament List
        req = rf.get(reverse('tournament_list'))
        response = tournament_list(req)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"World Masters Invitational 2026", response.content)

        # Test Tournament Detail (art=0, 1, 2, 4, 5)
        req_art0 = rf.get(f"{reverse('tournament_detail', kwargs={'slug': self.tournament.slug})}?art=0")
        response_art0 = tournament_detail(req_art0, slug=self.tournament.slug)
        self.assertEqual(response_art0.status_code, 200)

        req_art1 = rf.get(f"{reverse('tournament_detail', kwargs={'slug': self.tournament.slug})}?art=1")
        response_art1 = tournament_detail(req_art1, slug=self.tournament.slug)
        self.assertEqual(response_art1.status_code, 200)
        self.assertIn(b"Carlsen, Magnus", response_art1.content)

        req_art4 = rf.get(f"{reverse('tournament_detail', kwargs={'slug': self.tournament.slug})}?art=4")
        response_art4 = tournament_detail(req_art4, slug=self.tournament.slug)
        self.assertEqual(response_art4.status_code, 200)

        req_art5 = rf.get(f"{reverse('tournament_detail', kwargs={'slug': self.tournament.slug})}?art=5")
        response_art5 = tournament_detail(req_art5, slug=self.tournament.slug)
        self.assertEqual(response_art5.status_code, 200)

    def test_player_registration_view(self):
        from django.test import RequestFactory
        from tournaments.views import tournament_register
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware

        rf = RequestFactory()
        req = rf.post(
            reverse('tournament_register', kwargs={'slug': self.tournament.slug}),
            data={
                'name': 'Anand, Viswanathan',
                'title': 'GM',
                'rating': 2750,
                'fide_id': '5000017',
                'federation': 'IND',
                'gender': 'M',
            }
        )
        SessionMiddleware(lambda r: None).process_request(req)
        req.session.save()
        MessageMiddleware(lambda r: None).process_request(req)

        response = tournament_register(req, slug=self.tournament.slug)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Player.objects.filter(name='Anand, Viswanathan').exists())
        self.assertTrue(TournamentParticipant.objects.filter(player__name='Anand, Viswanathan').exists())
