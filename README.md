# ♔ ChessRoster

**ChessRoster** is a full-featured chess tournament management system built with **Django, Python, HTML5, CSS3, and Bootstrap 5**, inspired by the classic architecture of [Chess-Results.com](https://s1.chess-results.com/tnr1263143.aspx?lan=1&art=2&rd=7&SNode=S0).

---

## 🌟 Key Features

1. **Tournament Formats**:
   - **FIDE Swiss-System**: Automatic pairing engine with score brackets, rematch prevention, color streak balancing, and bye handling.
   - **Round Robin**: Berger circle method fixture generation.

2. **Player Registration & Seeding**:
   - Registration form with FIDE IDs, Title (GM, IM, FM, etc.), standard rating, and federation.
   - Automatic starting rank calculation.

3. **Live Pairings & Results Updations**:
   - Board pairings with White/Black assignments.
   - Chief Arbiter station with bulk and AJAX result updates (`1-0`, `0-1`, `½-½`, `FF`, `Bye`).

4. **Official Standings & Tie-breaks**:
   - Live standings with **Points, Buchholz Cut 1 (BH-1), Buchholz (BH), Sonneborn-Berger (SB), and Wins**.
   - **Matrix Crosstable** view (e.g. `12w1`, `4b0`, `7w½`).

5. **Individual Player Scorecards**:
   - Round-by-round opponent tracking with running scores and ratings.

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Apply Database Migrations
```bash
python manage.py migrate
```

### 3. (Optional) Load 16-GM Demo Tournament
```bash
python manage.py seed_chess_data
```

### 4. Start Development Server
```bash
python manage.py runserver
```
Visit **http://127.0.0.1:8000/** in your browser.

---

## 📂 Project Structure

- `chess_manager/`: Main Django project configuration (`settings.py`, `urls.py`).
- `tournaments/`: Core tournament app:
  - `models.py`: Database models (`Tournament`, `Player`, `TournamentParticipant`, `Round`, `Match`).
  - `engine.py`: Swiss pairing algorithm, Round Robin scheduler, and Tie-Break calculator.
  - `views.py`: Application views for directory, details, registration, arbiters, and scorecards.
  - `forms.py`: Tournament & registration forms.
  - `tests.py`: Unit and integration test suite.
- `templates/`: HTML5 templates with Bootstrap 5.
- `static/`: Custom CSS themes and JavaScript.
- `db.sqlite3`: SQLite database pre-configured with demo data.
