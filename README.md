# MEDNEXA — Pharma Field Intelligence Platform

One integrated application for pharmaceutical medical representatives and their managers:

**KNOW** Doctor Intelligence → **PLAN** Visit Planner → **EXECUTE** Visit & Sample Logging → **ANALYZE** Manager Dashboard → **ACT** Action Center

Stack: Python · Streamlit · SQLite · pandas · Plotly. Runs fully locally; no external APIs.

> **Status: MVP complete.** All five features are integrated on one SQLite database: Doctor Intelligence Hub, Visit Planner, Visit & Sample Logging, Manager Dashboard & Analytics, and Action Center. 80 automated tests pass.

---

## Quick start

Requires Python 3.11+. Using a virtual environment is recommended.

Create and activate a virtual environment (Windows):

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

On macOS/Linux, activate it with:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Build the database from the seed CSVs (takes a few seconds; the command is blocked unless both data validators pass):

```bash
python -m mednexa.db.seed
```

To reset the demo data at any time, rebuild it:

```bash
python -m mednexa.db.seed --reset
```

Start the app:

```bash
streamlit run app.py
```

Run the tests:

```bash
python -m pytest
```

Run the seed-data validators:

```bash
python scripts/validate_data.py
```

```bash
python scripts/validate_product_data.py
```

---

## Using the app

- **Role** (sidebar): *Manager* or *Representative*.
  - Representatives work in their own territory: Action Center (home), Doctors (read-only), My Visit Plan, Log Visit, Visit History, Samples & Stock.
  - Managers see the whole team: Overview (home), Analytics, Action Center, Doctors (add/edit), Visit Planner (any rep), Visit History, Inventory. **Log Visit** appears only while a manager is *acting as* a representative.
- **Business date** (sidebar): defaults to **01 Sep 2026**, the day after the last visit in the seed data. Every due, overdue, upcoming and planning calculation uses this date and never the computer clock. Changing it is shown in the header as an override, and it can be reset.

---

## Project structure

```
app.py                     entry point: page config, theme, context, role-based navigation
mednexa/
  config.py                THE single configuration source (business rules, defaults, theme tokens)
  core/                    framework-free foundations
    db.py                  SQLite connection (foreign keys ON) + atomic transaction()
    errors.py              ServiceError family; pages show user_message, never tracebacks
    dates.py               Mon–Sat working-day calendar helpers (no machine clock)
    ids.py                 sequential IDs continuing the seed conventions (V0321, T00494, D101…)
    context.py             role, representative, "acting as", business date, permissions
  db/                      schema.sql + seed.py (validated, rebuildable)
  repositories/            SQL only
  services/                business logic, one module per owning feature + shared rules
  ui/
    theme.py               CSS + Plotly template built from config tokens
    components.py          KPI tiles, badges, pills, chips, action/doctor cards, states, filters
    formatting.py          display formatting ("—", "Not recorded", dates)
    navigation.py          role-based page map (pure data, tested)
    shell.py               sidebar workspace controls + context bar
pages/                     one file per screen; UI only (calls services)
assets/                    logo files
data/seed/                 read-only copies of the 7 validated CSVs + CHECKSUMS.sha256
scripts/                   dataset validators (path-adjusted copies)
tests/                     pytest suite
.streamlit/config.toml     Streamlit base theme (kept in sync with config.THEME by a test)
```

### Architecture rules (enforced by `tests/test_architecture.py`)

- Pages call **services**. Services call **repositories**. Repositories are the only place SQL lives.
- Pages never import `sqlite3`, `mednexa.core.db` or repositories, and contain no SQL.
- Services, repositories and core never import Streamlit.
- Brand colours are defined only in `config.py`.
- The seed CSVs are never written to. The app writes only to `mednexa.db`.

---

## Data

`data/seed/` holds exact copies of the validated datasets (5 reps, 100 doctors, 320 August-2026 visits, 12 products, 552 visit–product links, 12 inventory records, 493 sample transactions). `CHECKSUMS.sha256` records their fingerprints, and `tests/test_seed_data.py` fails if any copy changes.

## Approved business rules (configured in `mednexa/config.py`)

| Rule | Value |
|---|---|
| Segmentation | A ≥ 150 Rx/month (4 visits) · B 70–149 (2) · C < 70 (1) |
| Visit outcomes | Positive · Neutral · Negative · Doctor unavailable (history: "Not recorded") |
| Product feedback | Positive · Neutral · Negative, optional (history: "Not recorded") |
| Follow-up completion | By VISIT, or by CONTACT with a required note |
| Planning | 6 working days, max 5 visits/day; score = 40% urgency, 25% recency, 25% Rx (cap 300), 10% never visited |
| Follow-up timing | Overdue < business date · Due today = business date · Upcoming within 7 days |
| Action priority | Critical = overdue ≥ 14 days or missed A-doctor visit |
| Stock status | Critical ≤ 25% of minimum · Low < minimum · Watch ≤ 1.5 × minimum · Healthy |

## Demo script (about 6 minutes)

1. **Manager → Overview** (business date 01 Sep 2026). Point out: 320 August visits, 94% coverage, 26 overdue follow-ups (18 are critical), 2 never-visited A doctors in West Zone, and 2 products critically low on stock. The representative table shows R004 at 39% A-doctor compliance.
2. **Doctors** (KNOW). A/B/C segmentation is derived automatically from monthly prescriptions (A ≥150, B 70–149, C <70). Search and filter, then open **Dr. Yash Naik (D080)**: an A doctor with 285 Rx/month who has never been visited.
3. **Switch role → Representative, signed in as R004 · Priya Menon**. The **Action Center** (ACT) shows critical overdue follow-ups. Dr. Rahul Jadhav (D068) has 4 pending follow-ups grouped on one card.
4. **My Visit Plan** (PLAN) → *Generate plan*. Day 1 holds the overdue follow-ups (D070, D068 with its 4 follow-ups merged, D072) and the never-visited A doctors (D080, D078). Each visit shows its score and reason chips, grouped by area.
5. On **D068**, click *Log visit* (EXECUTE). The doctor, planned visit and follow-ups are pre-filled. Choose outcome *Positive*, add Product D with feedback, and first try 999 samples: the save is rejected for insufficient stock and nothing is written. Change to 5 samples, add a follow-up for 08 Sep, and save.
6. Back to the **Action Center**: D068's overdue card is gone. On another follow-up card, use *Complete by contact* (a note is required). Open *Action history* to see the audit trail.
7. **Manager → Overview** (ANALYZE): overdue follow-ups drop from 26 to 22, visits rise to 321, the September plan shows its completion rate, and Product D stock has fallen.
8. Change the **Business date** to **03 Sep 2026**: planned visits that were not logged appear as *Missed planned visit* actions. Use *Reschedule* on the card, which goes through the Visit Planner.

## Milestones

1. Foundation ✅
2. Schema and seed ✅
3. Feature 1: Doctor Intelligence Hub ✅
4. Feature 3: Visit History, Inventory ✅
5. Feature 2: Visit Planner ✅
6. Log Visit (linked to plans and follow-ups) ✅
7. Feature 4: Overview and Analytics ✅
8. Feature 5: Action Center ✅
9. Critical acceptance tests and packaging ✅

## Known limitations (MVP)

- There is no login: the role and representative are chosen in the sidebar for the demo.
- Historical August visits have no outcome or feedback, so they show as "Not recorded". New visits record both.
- August "planned vs actual" is measured as frequency compliance against the recommended visit frequency. Plan-based completion applies to plans generated from September 2026.
