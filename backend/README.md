# PropCheck — Backend

FastAPI service powering all three surfaces (web, Chrome extension, WhatsApp).

## Quick start

```bash
# 1. Create a virtual env
python -m venv .venv
.venv\Scripts\activate           # Windows
# source .venv/bin/activate      # macOS/Linux

# 2. Install deps
pip install -r requirements.txt

# 3. Copy env template
copy .env.example .env           # Windows
# cp .env.example .env           # macOS/Linux

# 4. Run dev server
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for the auto-generated Swagger UI.

## Test the API

```bash
curl http://localhost:8000/healthz

curl -X POST http://localhost:8000/v1/check ^
  -H "Content-Type: application/json" ^
  -d "{\"url\": \"https://www.magicbricks.com/propertyDetails/3-BHK-Apartment-FOR-Sale-Whitefield\"}"
```

(Use single quotes / `\` line continuations on macOS/Linux.)

At MVP this returns a stubbed report. Real scoring lands during Sprint 1 (see `../specs/sprint-1.md`).

## Folder structure

```
backend/
├── app/
│   ├── main.py              ← FastAPI app, routers wired
│   ├── config.py            ← Settings loaded from .env
│   ├── api/                 ← HTTP route handlers
│   │   ├── health.py        ← /healthz
│   │   └── check.py         ← /v1/check, /v1/check/{id}
│   ├── models/
│   │   └── schemas.py       ← Pydantic request/response models
│   ├── engine/
│   │   └── trust_score.py   ← Trust scoring rules (v1 stub)
│   └── parsers/             ← Per-portal HTML parsers (Sprint 1, Day 4–5)
├── requirements.txt
├── .env.example
├── .gitignore
└── Dockerfile               ← For Railway
```

## Specs

Read these before adding code:

- [../specs/architecture.md](../specs/architecture.md)
- [../specs/api.md](../specs/api.md)
- [../specs/database.md](../specs/database.md)
- [../specs/trust-engine.md](../specs/trust-engine.md)
- [../specs/sprint-1.md](../specs/sprint-1.md)
