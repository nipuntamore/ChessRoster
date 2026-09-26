from django.urls import path
from . import views

urlpatterns = [
    path('', views.tournament_list, name='tournament_list'),
    path('signup/', views.signup_view, name='signup'),
    path('register/', views.signup_view, name='register_account'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.user_profile, name='user_profile'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard_alt'),
    path('tournaments/create/', views.tournament_create, name='tournament_create'),
    path('tournaments/demo-seed/', views.seed_demo_data, name='seed_demo_data'),
    path('tournaments/<slug:slug>/', views.tournament_detail, name='tournament_detail'),
    path('tournaments/<slug:slug>/edit/', views.tournament_edit, name='tournament_edit'),
    path('tournaments/<slug:slug>/delete/', views.tournament_delete, name='tournament_delete'),
    path('tournaments/<slug:slug>/register/', views.tournament_register, name='tournament_register'),
    path('tournaments/<slug:slug>/player/<int:participant_id>/', views.player_detail, name='player_detail'),
    path('tournaments/<slug:slug>/arbiter/', views.arbiter_control_panel, name='arbiter_panel'),
    path('tournaments/<slug:slug>/generate-pairings/', views.generate_round_pairings, name='generate_pairings'),
    path('tournaments/<slug:slug>/match/<int:match_id>/update/', views.update_match_result, name='update_match_result'),
    path('tournaments/<slug:slug>/bulk-update-results/', views.bulk_update_results, name='bulk_update_results'),
    path('tournaments/<slug:slug>/recalculate/', views.recalculate_standings_view, name='recalculate_standings'),
    path('players/add/', views.player_create, name='player_create'),
    path('players/<int:player_id>/edit/', views.player_edit, name='player_edit'),
    path('players/<int:player_id>/delete/', views.player_delete, name='player_delete'),
]
