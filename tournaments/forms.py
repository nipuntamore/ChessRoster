from django import forms
from .models import Tournament, Player, TournamentParticipant, Match


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            'name', 'tournament_system', 'time_control_type', 'time_control',
            'rounds_count', 'start_date', 'end_date', 'federation', 'city',
            'venue', 'chief_arbiter', 'deputy_arbiter', 'organizer', 'is_rated',
            'description', 'rules_and_prizes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 5th Spring Masters Open 2026'}),
            'tournament_system': forms.Select(attrs={'class': 'form-select'}),
            'time_control_type': forms.Select(attrs={'class': 'form-select'}),
            'time_control': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '90m + 30s/move'}),
            'rounds_count': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 20}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'federation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FIDE / IND / USA'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tournament Hall'}),
            'chief_arbiter': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IA Arbiter Name'}),
            'deputy_arbiter': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FA Arbiter Name'}),
            'organizer': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Chess Club / Organizer'}),
            'is_rated': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rules_and_prizes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PlayerRegistrationForm(forms.Form):
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name (e.g. Carlsen, Magnus)'})
    )
    title = forms.ChoiceField(
        choices=Player.TITLE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    rating = forms.IntegerField(
        initial=1200,
        min_value=0,
        max_value=3200,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1200'})
    )
    fide_id = forms.CharField(
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FIDE ID (optional)'})
    )
    federation = forms.CharField(
        initial="IND",
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '3-letter code (IND, USA, NOR...)'})
    )
    club_or_city = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Club or City'})
    )
    birth_year = forms.IntegerField(
        required=False,
        min_value=1920,
        max_value=2026,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'YYYY'})
    )
    gender = forms.ChoiceField(
        choices=Player.GENDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'player@chess.com'})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1-234-567-8900'})
    )


class MatchResultUpdateForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['result', 'remarks', 'pgn']
        widgets = {
            'result': forms.Select(attrs={'class': 'form-select form-select-sm match-result-select'}),
            'remarks': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Remarks'}),
            'pgn': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 3, 'placeholder': '1. e4 e5 2. Nf3 Nc6...'}),
        }
