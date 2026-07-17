# CloudVision Analytics — AI-Native CRM & Customer Success Platform

A demo CRM for a B2B SaaS company (CloudVision Analytics), built with Flask + SQLite + Bootstrap 5 + Chart.js. Intended for executive and prospect demos — not production.

## Quick start

```bash
cd crm_demo
pip install -r requirements.txt
python app.py
```

Open http://localhost:5050 — the SQLite database is created and seeded automatically on first run (200 customers, 600 opportunities, 300 contracts/renewals, 5,000 notes, usage telemetry, and more).

## Demo logins

All accounts use password `demo123`. The login page has one-click persona buttons.

| Persona | Email |
|---|---|
| CEO | ceo@cloudvision.com |
| VP Sales | vpsales@cloudvision.com |
| Sales Rep | rep@cloudvision.com |
| Customer Success | csm@cloudvision.com |
| Finance | finance@cloudvision.com |
| Sales Operations | salesops@cloudvision.com |
| Executive Assistant | ea@cloudvision.com |

**Role switching:** use the persona dropdown in the top bar to instantly switch dashboards without logging out — ideal for live demos.

## Highlights

- Quick-create everywhere: the "+ New" button in the top bar opens modal forms for Leads, Opportunities, Accounts, Contacts, Tasks, Meetings and Notes — records save instantly and new customer accounts get a starter health score
- Edit in place: pencil icons on Accounts, Contacts, Opportunities (board + table), Tasks and the Customer 360 header open prefilled edit modals
- Drag & drop pipeline: drag deals between kanban stages — probability, AI score and close date update automatically, column totals recalculate live, and every move is audit-logged
- Seven role-based dashboards (CEO, VP Sales, Rep, CSM, Finance, Sales Ops, EA)
- Customer 360 showcase page: health ring, usage chart, contacts, contracts, renewals, meeting timeline, emails, notes, AI suggested actions, risk score
- Kanban pipeline board + sortable deal tables (DataTables)
- AI assistant everywhere: slide-out copilot panel, per-record AI buttons, full AI chat page — powered by a mocked provider in `ai_service.py` that answers from live database facts (swap in OpenAI/Anthropic later via the `BaseAIProvider` interface)
- Morning Briefing page (overnight changes) and Scenario Analysis (win-rate / renewal / deal-size sliders with live recalculation)
- Global search across accounts, contacts, deals, contracts, users, tasks, meetings
- Notifications, renewal calendar, customer health scoring (usage, exec meetings, training, NPS, adoption), reports gallery with 9 interactive charts

## Structure

```
crm_demo/
├── app.py            # Flask app factory, auto-seed on first run
├── config.py
├── database.py
├── models.py         # 18 SQLAlchemy tables
├── seed_data.py      # realistic demo data generator
├── ai_service.py     # AI abstraction + mocked provider
├── routes/           # auth, dashboards, modules, api blueprints
├── templates/        # Jinja2 templates
├── static/css|js
└── requirements.txt
```

To reset demo data, delete `crm_demo.db` and restart the app.

## Deploy live

The app is WSGI-ready (`app:app`) and served with gunicorn in production.

**Render (recommended, free):** push this repo to GitHub, then in Render choose
**New + → Blueprint** and point it at the repo — `render.yaml` provisions
everything and generates `SECRET_KEY` + `AGENT_API_TOKEN` for you.

**Any Procfile host (Railway, Fly, Heroku, etc.):** the included `Procfile`
runs `gunicorn app:app --bind 0.0.0.0:$PORT`. Set these env vars:

| Var | Purpose |
|---|---|
| `SECRET_KEY` | Flask session signing — set a strong random value |
| `AGENT_API_TOKEN` | Bearer token for the `/api/agent/*` API (rotate off the demo default) |
| `PORT` | Injected by the host; gunicorn binds to it |

The SQLite database is created and seeded automatically on first boot, so no
migration step is needed.

> ⚠️ **This is a public demo, not a secure app.** Every account uses the
> password `demo123` by design. Do not put real customer data in a hosted
> instance.

### Agent API

`routes/agent_api.py` exposes a token-authenticated `/api/agent/*` surface (the
data-plane an external orchestrator drives). Import
`CloudVision_Agent_API.postman_collection.json` into Postman to exercise it.
