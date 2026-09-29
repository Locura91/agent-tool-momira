# Agent Tool Momira

White-label SaaS for travel agents — generate social media posts, print-ready flyers, and (coming soon) destination catalogs from any Travel Compositor Holiday Package ID.

## Tools included

| Tool | What it does |
|------|-------------|
| 📱 **Social Post** | Square, Story & Google Business images + 3 captions |
| 📄 **Travel Flyer** | Print-ready A4 flyer (browser → Ctrl+P → PDF) |
| 🗺️ **Destination Catalog** | *(Coming soon)* Country catalogs from live Momira inventory |

## Stack

- **Backend** — FastAPI + SQLAlchemy (async, SQLite MVP / Postgres-ready)
- **Auth** — JWT (python-jose) + bcrypt passwords
- **Image rendering** — Pillow via the `social_kit.py` engine
- **Logo storage** — Cloudflare R2 (boto3 S3-compatible)
- **Frontend** — Plain HTML/CSS/JS (no build step)

## Quick start

```bash
# 1. Clone
git clone https://github.com/Locura91/agent-tool-momira.git
cd agent-tool-momira

# 2. Copy and fill in credentials
cp .env.example .env
# → edit .env with your TC + R2 credentials

# 3. Install dependencies (Python 3.11+)
pip install -r requirements.txt

# 4. Drop your fonts in fonts/
#    fonts/mw-bold.ttf and fonts/mw-regular.ttf  (Carlito OFL, or Poppins)

# 5. Start the server
python app.py
# → open http://localhost:8000
```

## Environment variables

See `.env.example` for the full list. Key ones:

| Variable | Description |
|----------|-------------|
| `TRAVELC_BASE_URL` | TC API base URL |
| `TRAVELC_MICROSITE_ID` | Your TC microsite ID |
| `TRAVELC_USERNAME` | TC login username |
| `TRAVELC_PASSWORD` | TC login password |
| `SECRET_KEY` | Random 64-char hex for JWT signing |
| `R2_ACCOUNT_ID` | Cloudflare R2 account ID |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret key |
| `R2_BUCKET` | R2 bucket name (default: `social-kit-logos`) |
| `R2_PUBLIC_URL` | Public URL of your R2 bucket |
| `DATABASE_URL` | SQLite (default) or Postgres async URL |

## Project structure

```
agent-tool-momira/
├── app.py              # FastAPI app + all routes
├── social_kit.py       # Core TC + image rendering engine (untouched)
├── kit_engine.py       # Per-agent wrapper (logo, ribbon compositing)
├── flyer_engine.py     # A4 HTML flyer generator
├── models.py           # SQLAlchemy Agent model
├── database.py         # Async session factory
├── auth.py             # JWT + bcrypt helpers
├── schemas.py          # Pydantic request/response models
├── r2_upload.py        # Cloudflare R2 logo storage
├── fonts/              # mw-bold.ttf + mw-regular.ttf
├── static/
│   ├── login.html
│   ├── dashboard.html
│   ├── settings.html
│   ├── tool-social-post.html
│   └── tool-flyer.html
├── .env.example
├── requirements.txt
└── .gitignore
```
