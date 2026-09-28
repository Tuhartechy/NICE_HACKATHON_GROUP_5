"""
MedNexa - single configuration source.

Every business constant used anywhere in the application is defined here.
No other module may redefine these values; they import them from this file.
Values reflect the approved reconciliation decisions.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from types import MappingProxyType

# --------------------------------------------------------------------------- branding
APP_NAME = "MEDNEXA"
APP_SUBTITLE = "Pharma Field Intelligence Platform"
APP_TAGLINE = "Know · Plan · Execute · Analyze · Act"

# --------------------------------------------------------------------------- paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = Path(os.environ.get("MEDNEXA_SEED_DIR", PROJECT_ROOT / "data" / "seed"))
DB_PATH = Path(os.environ.get("MEDNEXA_DB_PATH", PROJECT_ROOT / "mednexa.db"))
SEED_FILES = (
    "reps.csv", "doctors.csv", "visits.csv", "products.csv",
    "visit_products.csv", "inventory.csv", "sample_transactions.csv",
)

# --------------------------------------------------------------------------- business date
# The application never reads the machine clock for business logic.
DEFAULT_AS_OF = date(2026, 9, 1)            # day after the last visit in visits.csv
BUSINESS_DATE_MIN = date(2026, 8, 1)        # first day of seed history
BUSINESS_DATE_MAX = date(2026, 12, 31)

# --------------------------------------------------------------------------- calendar
WORKING_WEEKDAYS = frozenset({0, 1, 2, 3, 4, 5})   # Monday..Saturday (Python weekday numbers)
HOLIDAYS = frozenset({date(2026, 8, 15)})          # Independence Day

# --------------------------------------------------------------------------- roles
ROLE_REP = "Representative"
ROLE_MANAGER = "Manager"
ROLES = (ROLE_MANAGER, ROLE_REP)
DEFAULT_ROLE = ROLE_MANAGER

# --------------------------------------------------------------------------- segmentation (Feature 1)
# Ordered highest first: (segment, minimum monthly prescriptions, visits per month, label)
SEGMENT_RULES = (
    ("A", 150, 4, "High potential"),
    ("B", 70, 2, "Medium potential"),
    ("C", 0, 1, "Lower potential"),
)

# --------------------------------------------------------------------------- visits (Feature 3)
OUTCOMES = ("Positive", "Neutral", "Negative", "Doctor unavailable")
FEEDBACK = ("Positive", "Neutral", "Negative")
NOT_RECORDED = "Not recorded"
FOLLOW_UP_STATUSES = ("Pending", "Completed")
FOLLOW_UP_NOT_REQUIRED = "Not Required"            # display value for visits without a follow-up
COMPLETION_METHODS = ("VISIT", "CONTACT")
TRANSACTION_TYPES = ("SAMPLE_ISSUED", "SAMPLE_RETURNED")

# --------------------------------------------------------------------------- stock status (Feature 3)
STOCK_CRITICAL_RATIO = 0.25     # current <= 25% of minimum  -> CRITICAL (0 shown as "Out of stock")
STOCK_WATCH_RATIO = 1.5         # current <= 1.5 x minimum   -> WATCH  (below minimum -> LOW)
STOCK_STATUSES = ("CRITICAL", "LOW", "WATCH", "HEALTHY")

# --------------------------------------------------------------------------- planning (Feature 2)
PLAN_DAILY_CAPACITY = 5
PLAN_DEFAULT_DAYS = 6
PLAN_WEIGHTS = MappingProxyType({"urgency": 0.40, "recency": 0.25, "potential": 0.25, "never": 0.10})
RECENCY_CAP_DAYS = 30
RX_SCORE_CAP = 300
OVERDUE_URGENCY_CAP_DAYS = 14
URGENCY = MappingProxyType({"overdue_base": 0.8, "due_today": 0.8, "in_window": 0.6, "later": 0.3})
REVISIT_WORKING_DAYS_BASE = 26   # minimum revisit gap = floor(26 / visits_per_month) working days
PLAN_STATUSES = ("PLANNED", "COMPLETED", "SKIPPED", "CANCELLED")

# --------------------------------------------------------------------------- follow-up timing & actions (Features 3/5)
UPCOMING_WINDOW_DAYS = 7
PREP_WINDOW_WORKING_DAYS = 1     # today + next working day
OVERDUE_CRITICAL_DAYS = 14
ACTION_PRIORITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
ACTION_TYPES = (
    "OVERDUE_FOLLOW_UP", "DUE_TODAY_FOLLOW_UP", "UPCOMING_FOLLOW_UP",
    "MISSED_VISIT", "UPCOMING_VISIT_PREPARATION",
)
ACTION_STATUSES = ("OPEN", "SNOOZED", "DONE", "DISMISSED", "RESOLVED")

# --------------------------------------------------------------------------- analytics (Feature 4)
ACTIVE_DOCTOR_DAYS = 30
NOT_RECENT_MULTIPLIER = 2        # not recently visited: days since last > 2 x (30 / visits_per_month)

# --------------------------------------------------------------------------- UI
DIRECTORY_PAGE_SIZE = 25
THEME = MappingProxyType({
    "bg": "#111827",
    "surface": "#1B2433",
    "sidebar": "#0D1420",
    "surface_raised": "#222D3F",
    "border": "#2A3547",
    "primary": "#0F766E",
    "primary_soft": "#134E4A",
    "primary_hover": "#11857C",
    "primary_bright": "#2BB3A3",   # teal for text/marks on dark surfaces
    "accent": "#B8E35A",
    "text": "#F5F5F0",
    "muted": "#9AA4B2",
    "warning": "#F2B25C",
    "critical": "#F0806E",
    "success": "#6CC4A1",
    "info": "#8FB8C9",
})
FONT_STACK = "'Inter', 'Segoe UI', 'Helvetica Neue', system-ui, -apple-system, sans-serif"
MONO_STACK = "'JetBrains Mono', 'Cascadia Code', 'Consolas', ui-monospace, monospace"

# Chart colours are lighter than the brand primary so marks stay legible on the dark surface.
CHART_COLORWAY = tuple(THEME[k] for k in ("primary_bright", "accent", "info", "warning", "critical", "muted"))
SEGMENT_COLORS = MappingProxyType({"A": THEME["accent"], "B": THEME["primary_bright"], "C": THEME["muted"]})

# Planning score -> display label (Feature 2)
PLAN_LABEL_HIGH = 60
PLAN_LABEL_MEDIUM = 35
