from django.urls import path
from . import views

urlpatterns = [
    path('', views.tournament_list, name='tournament_list'),
    path('tournaments/create/', views.tournament_create, name='tournament_create'),
    path('tournaments/demo-seed/', views.seed_demo_data, name='seed_demo_data'),
    path('tournaments/<slug:slug>/', views.tournament_detail, name='tournament_detail'),
    path('tournaments/<slug:slug>/register/', views.tournament_register, name='tournament_register'),
    path('tournaments/<slug:slug>/player/<int:participant_id>/', views.player_detail, name='player_detail'),
    path('tournaments/<slug:slug>/arbiter/', views.arbiter_control_panel, name='arbiter_panel'),
    path('tournaments/<slug:slug>/generate-pairings/', views.generate_round_pairings, name='generate_pairings'),
    path('tournaments/<slug:slug>/match/<int:match_id>/update/', views.update_match_result, name='update_match_result'),
    path('tournaments/<slug:slug>/bulk-update-results/', views.bulk_update_results, name='bulk_update_results'),
    path('tournaments/<slug:slug>/recalculate/', views.recalculate_standings_view, name='recalculate_standings'),
]
