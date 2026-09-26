from django.db import models
from django.utils.text import slugify
from django.urls import reverse
import uuid


class Tournament(models.Model):
    SYSTEM_CHOICES = [
        ('SWISS', 'Swiss-System'),
        ('ROUND_ROBIN', 'Round Robin'),
    ]

    STATUS_CHOICES = [
        ('UPCOMING', 'Registration Open'),
        ('ACTIVE', 'In Progress'),
        ('FINISHED', 'Tournament Completed'),
    ]

    TIME_CHOICES = [
        ('CLASSICAL', 'Classical'),
        ('RAPID', 'Rapid'),
        ('BLITZ', 'Blitz'),
        ('BULLET', 'Bullet'),
        ('STANDARD', 'Standard'),
    ]

    name = models.CharField(max_length=255, help_text="e.g. 15th International Grandmaster Open 2026")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    tournament_code = models.CharField(max_length=50, unique=True, blank=True, help_text="Reference Code like tnr1263143")
    tournament_system = models.CharField(max_length=20, choices=SYSTEM_CHOICES, default='SWISS')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UPCOMING')
    time_control_type = models.CharField(max_length=20, choices=TIME_CHOICES, default='CLASSICAL')
    time_control = models.CharField(max_length=150, default="90 min + 30 sec / move", help_text="Time control description")
    rounds_count = models.PositiveIntegerField(default=7, help_text="Number of rounds")
    current_round_num = models.PositiveIntegerField(default=0)
    
    federation = models.CharField(max_length=50, default="FIDE", help_text="e.g. FIDE, IND, USA, GER")
    city = models.CharField(max_length=100, default="International Arena")
    venue = models.CharField(max_length=200, default="Grand Conference Hall")
    chief_arbiter = models.CharField(max_length=100, default="IA John Smith (FIDE)")
    deputy_arbiter = models.CharField(max_length=100, blank=True, default="FA Sarah Jenkins")
    organizer = models.CharField(max_length=150, default="Chess Federation Organization")
    
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True, default="Official FIDE rated chess tournament with standard Swiss pairing system.")
    rules_and_prizes = models.TextField(blank=True, default="Tie-Break 1: Buchholz Cut 1\nTie-Break 2: Buchholz\nTie-Break 3: Sonneborn-Berger\nTie-Break 4: Direct Encounter")
    
    is_rated = models.BooleanField(default=True, help_text="Official Rated Tournament")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "chess-tournament"
            unique_slug = base_slug
            counter = 1
            while Tournament.objects.filter(slug=unique_slug).exclude(id=self.id).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        if not self.tournament_code:
            self.tournament_code = f"tnr{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.tournament_code})"

    def get_absolute_url(self):
        return reverse('tournament_detail', kwargs={'slug': self.slug})

    @property
    def participant_count(self):
        return self.participants.filter(is_active=True).count()


class Player(models.Model):
    TITLE_CHOICES = [
        ('NONE', 'No Title'),
        ('GM', 'Grandmaster (GM)'),
        ('WGM', 'Woman Grandmaster (WGM)'),
        ('IM', 'International Master (IM)'),
        ('WIM', 'Woman International Master (WIM)'),
        ('FM', 'FIDE Master (FM)'),
        ('WFM', 'Woman FIDE Master (WFM)'),
        ('CM', 'Candidate Master (CM)'),
        ('WCM', 'Woman Candidate Master (WCM)'),
    ]

    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    name = models.CharField(max_length=150)
    fide_id = models.CharField(max_length=30, blank=True, null=True)
    national_id = models.CharField(max_length=30, blank=True, null=True)
    title = models.CharField(max_length=10, choices=TITLE_CHOICES, default='NONE')
    rating = models.PositiveIntegerField(default=1200, help_text="FIDE / Standard Rating")
    national_rating = models.PositiveIntegerField(blank=True, null=True)
    federation = models.CharField(max_length=10, default="IND", help_text="3-letter IOC/FIDE country code, e.g. IND, USA, NOR, IND")
    club_or_city = models.CharField(max_length=100, blank=True)
    birth_year = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M')
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-rating', 'name']

    def __str__(self):
        title_str = f"[{self.title}] " if self.title != 'NONE' else ""
        return f"{title_str}{self.name} ({self.rating}) - {self.federation}"


class TournamentParticipant(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='participants')
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='tournament_entries')
    starting_rank = models.PositiveIntegerField(default=1)
    
    current_points = models.FloatField(default=0.0)
    buchholz = models.FloatField(default=0.0)
    buchholz_cut1 = models.FloatField(default=0.0)
    sonneborn_berger = models.FloatField(default=0.0)
    direct_encounter = models.FloatField(default=0.0)
    wins_count = models.PositiveIntegerField(default=0)
    
    is_active = models.BooleanField(default=True, help_text="Active in ongoing rounds")
    received_bye = models.BooleanField(default=False, help_text="Has received a pairing Bye in this tournament")
    color_streak = models.IntegerField(default=0, help_text="Consecutive same colors (+ve for White, -ve for Black)")
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starting_rank']
        unique_together = ('tournament', 'player')

    def __str__(self):
        return f"#{self.starting_rank} {self.player.name} ({self.current_points} pts)"

    def get_color_preference(self):
        """Calculates color preference based on match history"""
        white_count = self.white_matches.exclude(result__icontains='BYE').count()
        black_count = self.black_matches.exclude(result__icontains='BYE').count()
        return white_count - black_count  # >0 means played more whites, prefers black


class Round(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='rounds')
    round_number = models.PositiveIntegerField()
    scheduled_time = models.DateTimeField(blank=True, null=True)
    is_paired = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['round_number']
        unique_together = ('tournament', 'round_number')

    def __str__(self):
        return f"{self.tournament.name} - Round {self.round_number}"

    @property
    def total_boards(self):
        return self.matches.count()

    @property
    def completed_boards(self):
        return self.matches.exclude(result='*').count()


class Match(models.Model):
    RESULT_CHOICES = [
        ('*', '* (Unfinished / In Progress)'),
        ('1-0', '1 - 0 (White wins)'),
        ('0-1', '0 - 1 (Black wins)'),
        ('1/2-1/2', '½ - ½ (Draw)'),
        ('1-0_FF', '1 - 0 [FF] (White win by forfeit)'),
        ('0-1_FF', '0 - 1 [FF] (Black win by forfeit)'),
        ('0-0_FF', '0 - 0 [FF] (Double forfeit)'),
        ('1-0_BYE', '1 - 0 [BYE] (Full Point Bye)'),
        ('1/2-1/2_BYE', '½ - ½ [BYE] (Half Point Bye)'),
        ('0-0_BYE', '0 - 0 [BYE] (Zero Point Bye)'),
    ]

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='matches')
    board_number = models.PositiveIntegerField(default=1)
    
    white_participant = models.ForeignKey(
        TournamentParticipant, 
        on_delete=models.CASCADE, 
        related_name='white_matches', 
        null=True, 
        blank=True
    )
    black_participant = models.ForeignKey(
        TournamentParticipant, 
        on_delete=models.CASCADE, 
        related_name='black_matches', 
        null=True, 
        blank=True
    )
    
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='*')
    white_score = models.FloatField(null=True, blank=True)
    black_score = models.FloatField(null=True, blank=True)
    
    pgn = models.TextField(blank=True, help_text="PGN Moves or commentary")
    remarks = models.CharField(max_length=255, blank=True)
    is_confirmed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['board_number']
        unique_together = ('round', 'board_number')

    def __str__(self):
        w_name = self.white_participant.player.name if self.white_participant else "BYE"
        b_name = self.black_participant.player.name if self.black_participant else "BYE"
        return f"Rd {self.round.round_number} Bd {self.board_number}: {w_name} vs {b_name} ({self.result})"

    def save(self, *args, **kwargs):
        # Auto-compute white_score and black_score based on result
        if self.result == '1-0' or self.result == '1-0_FF' or self.result == '1-0_BYE':
            self.white_score = 1.0
            self.black_score = 0.0
        elif self.result == '0-1' or self.result == '0-1_FF':
            self.white_score = 0.0
            self.black_score = 1.0
        elif self.result == '1/2-1/2' or self.result == '1/2-1/2_BYE':
            self.white_score = 0.5
            self.black_score = 0.5
        elif self.result == '0-0_FF' or self.result == '0-0_BYE':
            self.white_score = 0.0
            self.black_score = 0.0
        elif self.result == '*':
            self.white_score = None
            self.black_score = None
        super().save(*args, **kwargs)


from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('ORGANISER', 'Tournament Organiser / Arbiter'),
        ('PLAYER', 'Chess Player'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='PLAYER')
    
    # Organiser specific fields
    organization_name = models.CharField(max_length=150, blank=True, default="", help_text="e.g. Chess Federation / Academy")
    arbiter_title = models.CharField(max_length=50, blank=True, default="", help_text="e.g. IA (International Arbiter), FA, NA")
    
    # Link to Player model for player accounts
    player = models.OneToOneField(Player, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_account')
    
    phone = models.CharField(max_length=30, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_organiser(self):
        return self.role == 'ORGANISER' or self.user.is_staff or self.user.is_superuser

    @property
    def is_player(self):
        return self.role == 'PLAYER'


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()
