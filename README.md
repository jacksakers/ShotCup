# ShotCup 🏆

A private World Cup fantasy league app for families and friend groups. Draft teams, track scores, propose trades, and watch the leaderboard update in real-time as the tournament progresses.

Built to run on a home server (Ubuntu Mini PC) and exposed to family members over [Tailscale Funnel](https://tailscale.com/kb/1223/funnel) — no public router ports required.

---

## Tech Stack

| Layer    | Technology                        |
|----------|-----------------------------------|
| Backend  | Python 3.10+ / FastAPI            |
| Database | SQLite (built-in, zero config)    |
| Auth     | JWT (python-jose) + bcrypt        |
| Frontend | React + Vite + Tailwind *(Phase 4)* |
| Hosting  | Local Ubuntu PC + Tailscale Funnel |

---

## Project Structure

```
ShotCup/
├── README.md
├── .gitignore
└── backend/
    ├── main.py           # FastAPI app & all API routes
    ├── database.py       # SQLite setup, seeding, connection management
    ├── models.py         # Pydantic request/response schemas
    ├── parser.py         # Pure-function FIFA standings text parser
    ├── requirements.txt
    └── .env.example      # Environment variable template
```

---

## Prerequisites

- Python 3.10+
- `pip` / `venv`

---

## Setup

### 1. Create the virtual environment

```bash
cd ShotCup/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your passwords and a strong secret key:

```dotenv
SITE_PASSWORD=your-family-password
ADMIN_PASSWORD=your-admin-password
SECRET_KEY=a-long-random-secret-string
```

> **Important:** Never commit `.env` to Git. It is already in `.gitignore`.

---

## Running the Backend

From inside the `backend/` directory (with the venv activated):

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

- API is available at: `http://127.0.0.1:8000`
- Interactive API docs (Swagger UI): `http://127.0.0.1:8000/docs`
- Alternative docs (ReDoc): `http://127.0.0.1:8000/redoc`

---

## Authentication

| Type        | How it works |
|-------------|--------------|
| **Site**    | `POST /api/auth/site` with `{"password": "..."}` → returns a bearer token. Required for all non-admin endpoints. |
| **Admin**   | `POST /api/auth/admin` with `{"password": "..."}` → returns a bearer token with admin privileges. |
| **User ID** | After logging in, users select their name from a list. The app stores their `user_id` locally. No per-user password needed ("honor system"). |

Pass the token as: `Authorization: Bearer <token>`

---

## API Overview

All routes are prefixed with `/api/`. See `/docs` for full interactive documentation.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/site` | — | Site password login |
| POST | `/api/auth/admin` | — | Admin password login |
| GET | `/api/users` | Site | List all players |
| POST | `/api/users` | Site | Register a new player (pre-draft only) |
| GET | `/api/users/{id}` | Site | Get player details |
| GET | `/api/teams` | Site | List all teams with owners & scores |
| GET | `/api/teams/{id}` | Site | Get a single team |
| GET | `/api/leaderboard` | Site | Players ranked by total fantasy points |
| POST | `/api/admin/draft` | Admin | Randomly distribute teams to players |
| GET | `/api/trades` | Site | List trades (filterable by user/status) |
| POST | `/api/trades` | Site | Propose a trade |
| PUT | `/api/trades/{id}/respond` | Site | Accept or reject a pending trade |
| POST | `/api/admin/parse-standings` | Admin | Paste FIFA standings text to update stats |
| POST | `/api/admin/match-result` | Admin | Record a knockout match result |
| PUT | `/api/admin/teams/{id}` | Admin | Manually override a team's stats |
| PUT | `/api/admin/users/{id}/points` | Admin | Manually override a player's points |
| DELETE | `/api/admin/trades/{id}` | Admin | Veto/reverse a trade |
| GET | `/api/settings` | Admin | View app settings |
| PUT | `/api/settings/{key}` | Admin | Update an app setting |

---

## Scoring System

| Event | Fantasy Points |
|-------|---------------|
| Match Win | +3 |
| Match Draw (inc. penalties) | +1 |
| Goal Scored | +1 per goal |
| Clean Sheet | +2 |
| Advance to Quarter-Finals | +3 |
| Advance to Semi-Finals | +5 |
| Advance to Final | +7 |
| Win the World Cup | +10 |

---

## Admin Workflow

### Updating group stage standings

1. Go to the FIFA website and copy the standings table text.
2. `POST /api/admin/parse-standings` with `{"raw_text": "<pasted text>"}`.
3. The parser finds all known team names and extracts W/D/L/GF/GA, then recalculates all fantasy scores automatically.

### Recording knockout results

`POST /api/admin/match-result`:

```json
{
  "home_team": "France",
  "away_team": "Brazil",
  "home_goals": 2,
  "away_goals": 1,
  "is_knockout": true
}
```

For a penalty shootout (goals equal but one team advances):
```json
{
  "home_team": "Spain",
  "away_team": "Germany",
  "home_goals": 1,
  "away_goals": 1,
  "is_knockout": true,
  "winner_team": "Spain"
}
```

The loser is automatically marked as `Eliminated` and the winner's advancement round is tracked.

---

## Hosting with Tailscale Funnel

To expose the app to your family without opening router ports:

```bash
# On your Ubuntu Mini PC
tailscale funnel --bg 8000
```

Tailscale will provide a public `https://your-machine.ts.net` URL. Share that with your family.

For persistent running, create a systemd service (see [implementation.txt](docs/implementation.txt)).

---

## Development Notes

- The SQLite database file (`shotcup.db`) is created automatically on first startup.
- The 48 World Cup teams are seeded into the database on first startup if the teams table is empty.
- To reset the database, simply delete `shotcup.db` and restart the server.
- Passwords from `.env` are re-hashed into the database on every startup — changing `.env` and restarting updates the passwords.
