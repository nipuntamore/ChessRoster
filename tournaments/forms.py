from django import forms
from .models import Tournament, Player, TournamentParticipant, Match


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            'name', 'tournament_system', 'status', 'time_control_type', 'time_control',
            'rounds_count', 'start_date', 'end_date', 'federation', 'city',
            'venue', 'chief_arbiter', 'deputy_arbiter', 'organizer', 'is_rated',
            'description', 'rules_and_prizes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 5th Spring Masters Open 2026'}),
            'tournament_system': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
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


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = [
            'name', 'title', 'rating', 'national_rating', 'federation',
            'fide_id', 'national_id', 'gender', 'birth_year', 'club_or_city',
            'email', 'phone'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'title': forms.Select(attrs={'class': 'form-select'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 3500}),
            'national_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 3500}),
            'federation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. IND, USA'}),
            'fide_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'FIDE ID (optional)'}),
            'national_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'National ID (optional)'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'birth_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'YYYY'}),
            'club_or_city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Club or City'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1-234-567-8900'}),
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


class PlayerSignUpForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose username', 'autocomplete': 'username'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'player@chess.com', 'autocomplete': 'email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create strong password', 'autocomplete': 'new-password'})
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password', 'autocomplete': 'new-password'})
    )
    name = forms.CharField(
        max_length=150,
        label="Full Real Name",
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
        max_value=3500,
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
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IND / USA / GER'})
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
    phone = forms.CharField(
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1-234-567-8900'})
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match.")
        return cleaned_data


class OrganiserSignUpForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose organiser username', 'autocomplete': 'username'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'arbiter@chessorg.com', 'autocomplete': 'email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create strong password', 'autocomplete': 'new-password'})
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password', 'autocomplete': 'new-password'})
    )
    name = forms.CharField(
        max_length=150,
        label="Organiser / Arbiter Full Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IA / FA / Director Full Name'})
    )
    organization_name = forms.CharField(
        max_length=150,
        label="Chess Organization / Club / Federation",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. All India Chess Federation / City Chess Club'})
    )
    arbiter_title = forms.CharField(
        required=False,
        max_length=50,
        label="Arbiter Title / Credentials (Optional)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. IA (International Arbiter), FA, NA'})
    )
    federation = forms.CharField(
        initial="IND",
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'IND / USA / FIDE'})
    )
    phone = forms.CharField(
        required=False,
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1-234-567-8900'})
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match.")
        return cleaned_data


class LoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username', 'autocomplete': 'username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password', 'autocomplete': 'current-password'})
    )
