from django.test import TestCase, Client
from django.urls import reverse
from datetime import date, timedelta
from .models import Tournament, Player, TournamentParticipant, Round, Match
from .engine import SwissEngine, RoundRobinEngine, TieBreakCalculator


class ChessTournamentEngineTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        from django.contrib.auth.models import User
        from .models import UserProfile
        
        self.organiser_user = User.objects.create_user(username="test_organiser", email="org@chess.com", password="password123")
        self.organiser_user.profile.role = 'ORGANISER'
        self.organiser_user.profile.save()

        self.player_user = User.objects.create_user(username="test_player", email="player@chess.com", password="password123")
        self.player_user.profile.role = 'PLAYER'
        self.player_user.profile.save()

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

    def test_admin_dashboard_view(self):
        from django.test import RequestFactory
        from tournaments.views import admin_dashboard
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware

        rf = RequestFactory()
        
        # Test Organiser can access
        req_org = rf.get(reverse('admin_dashboard'))
        req_org.user = self.organiser_user
        SessionMiddleware(lambda r: None).process_request(req_org)
        req_org.session.save()
        MessageMiddleware(lambda r: None).process_request(req_org)
        response_org = admin_dashboard(req_org)
        self.assertEqual(response_org.status_code, 200)
        self.assertIn(b"Tournament Command Center", response_org.content)

        # Test Player is restricted
        req_player = rf.get(reverse('admin_dashboard'))
        req_player.user = self.player_user
        SessionMiddleware(lambda r: None).process_request(req_player)
        req_player.session.save()
        MessageMiddleware(lambda r: None).process_request(req_player)
        response_player = admin_dashboard(req_player)
        self.assertEqual(response_player.status_code, 403)
        self.assertIn(b"Organiser Credentials Required", response_player.content)

    def test_tournament_edit_view(self):
        from django.test import RequestFactory
        from tournaments.views import tournament_edit
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware

        rf = RequestFactory()
        
        # GET
        req_get = rf.get(reverse('tournament_edit', kwargs={'slug': self.tournament.slug}))
        req_get.user = self.organiser_user
        SessionMiddleware(lambda r: None).process_request(req_get)
        req_get.session.save()
        MessageMiddleware(lambda r: None).process_request(req_get)
        response_get = tournament_edit(req_get, slug=self.tournament.slug)
        self.assertEqual(response_get.status_code, 200)
        self.assertIn(b"Edit Tournament", response_get.content)

        # POST
        req_post = rf.post(reverse('tournament_edit', kwargs={'slug': self.tournament.slug}), data={
            'name': 'World Masters Invitational 2026 Updated',
            'tournament_system': 'SWISS',
            'status': 'ACTIVE',
            'time_control_type': 'CLASSICAL',
            'time_control': '90m + 30s',
            'rounds_count': 7,
            'start_date': date.today(),
            'end_date': date.today() + timedelta(days=7),
            'federation': 'FIDE',
            'city': 'Paris',
            'venue': 'Grand Hotel',
            'chief_arbiter': 'IA Laurent Freyd',
            'deputy_arbiter': '',
            'organizer': 'FIDE',
            'is_rated': True,
            'description': 'Updated description',
            'rules_and_prizes': 'Updated rules'
        })
        req_post.user = self.organiser_user
        SessionMiddleware(lambda r: None).process_request(req_post)
        req_post.session.save()
        MessageMiddleware(lambda r: None).process_request(req_post)

        response_post = tournament_edit(req_post, slug=self.tournament.slug)
        self.assertEqual(response_post.status_code, 302)
        self.tournament.refresh_from_db()
        self.assertEqual(self.tournament.name, 'World Masters Invitational 2026 Updated')
        self.assertEqual(self.tournament.status, 'ACTIVE')
        self.assertEqual(self.tournament.rounds_count, 7)

    def test_tournament_delete_view(self):
        from django.test import RequestFactory
        from tournaments.views import tournament_delete
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware

        t_to_delete = Tournament.objects.create(
            name="Temporary Blitz Cup",
            tournament_code="tnrTMP01",
            tournament_system="SWISS",
            rounds_count=3,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1),
            chief_arbiter="IA Test"
        )
        rf = RequestFactory()

        # GET confirmation page
        req_get = rf.get(reverse('tournament_delete', kwargs={'slug': t_to_delete.slug}))
        req_get.user = self.organiser_user
        SessionMiddleware(lambda r: None).process_request(req_get)
        req_get.session.save()
        MessageMiddleware(lambda r: None).process_request(req_get)
        response_get = tournament_delete(req_get, slug=t_to_delete.slug)
        self.assertEqual(response_get.status_code, 200)
        self.assertIn(b"Confirm Tournament Deletion", response_get.content)

        # POST delete
        req_post = rf.post(reverse('tournament_delete', kwargs={'slug': t_to_delete.slug}))
        req_post.user = self.organiser_user
        SessionMiddleware(lambda r: None).process_request(req_post)
        req_post.session.save()
        MessageMiddleware(lambda r: None).process_request(req_post)

        response_post = tournament_delete(req_post, slug=t_to_delete.slug)
        self.assertEqual(response_post.status_code, 302)
        self.assertFalse(Tournament.objects.filter(slug=t_to_delete.slug).exists())

    def test_player_edit_and_delete_view(self):
        from django.test import RequestFactory
        from tournaments.views import player_edit, player_delete
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware

        player = Player.objects.create(name="Test Player", rating=1500, federation="IND")
        rf = RequestFactory()

        # Edit
        req_edit = rf.post(reverse('player_edit', kwargs={'player_id': player.id}), data={
            'name': 'Test Player Updated',
            'title': 'FM',
            'rating': 2300,
            'federation': 'IND',
            'gender': 'M',
        })
        req_edit.user = self.organiser_user
        SessionMiddleware(lambda r: None).process_request(req_edit)
        req_edit.session.save()
        MessageMiddleware(lambda r: None).process_request(req_edit)

        response_edit = player_edit(req_edit, player_id=player.id)
        self.assertEqual(response_edit.status_code, 302)
        player.refresh_from_db()
        self.assertEqual(player.name, 'Test Player Updated')
        self.assertEqual(player.title, 'FM')
        self.assertEqual(player.rating, 2300)

        # Delete
        req_del = rf.post(reverse('player_delete', kwargs={'player_id': player.id}))
        req_del.user = self.organiser_user
        SessionMiddleware(lambda r: None).process_request(req_del)
        req_del.session.save()
        MessageMiddleware(lambda r: None).process_request(req_del)

        response_del = player_delete(req_del, player_id=player.id)
        self.assertEqual(response_del.status_code, 302)
        self.assertFalse(Player.objects.filter(id=player.id).exists())

    def test_auth_signup_and_login_views(self):
        from django.test import RequestFactory
        from tournaments.views import signup_view, login_view, user_profile
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.contrib.messages.middleware import MessageMiddleware
        from django.contrib.auth.models import AnonymousUser

        rf = RequestFactory()

        # Sign up new player
        req_signup = rf.post(reverse('signup'), data={
            'account_type': 'player',
            'username': 'newchessguy',
            'email': 'newguy@chess.com',
            'password': 'ComplexPassword123!',
            'password_confirm': 'ComplexPassword123!',
            'name': 'Kasparov, Garry',
            'rating': 2812,
            'title': 'GM',
            'federation': 'RUS',
            'gender': 'M',
        })
        req_signup.user = AnonymousUser()
        SessionMiddleware(lambda r: None).process_request(req_signup)
        req_signup.session.save()
        MessageMiddleware(lambda r: None).process_request(req_signup)

        resp_signup = signup_view(req_signup)
        self.assertEqual(resp_signup.status_code, 302)
        self.assertTrue(Player.objects.filter(name='Kasparov, Garry').exists())

        # Test profile view
        req_prof = rf.get(reverse('user_profile'))
        req_prof.user = self.player_user
        SessionMiddleware(lambda r: None).process_request(req_prof)
        req_prof.session.save()
        MessageMiddleware(lambda r: None).process_request(req_prof)
        resp_prof = user_profile(req_prof)
        self.assertEqual(resp_prof.status_code, 200)
        self.assertIn(b"Player Card", resp_prof.content)
