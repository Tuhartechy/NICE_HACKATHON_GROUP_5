"""Feature 1 - the ONLY A/B/C segmentation logic in MedNexa."""
from __future__ import annotations

from mednexa import config


def segment_of(monthly_prescriptions) -> str:
    rx = int(monthly_prescriptions)
    for seg, floor, _visits, _label in config.SEGMENT_RULES:
        if rx >= floor:
            return seg
    return config.SEGMENT_RULES[-1][0]


def visits_per_month(segment: str) -> int:
    return next(v for s, _f, v, _l in config.SEGMENT_RULES if s == segment)


def label(segment: str) -> str:
    return next(l for s, _f, _v, l in config.SEGMENT_RULES if s == segment)


def rule_text() -> list[str]:
    out, rules = [], config.SEGMENT_RULES
    for i, (s, floor, v, l) in enumerate(rules):
        upper = rules[i - 1][1] - 1 if i else None
        rng = f"≥ {floor}" if upper is None else (f"< {upper + 1}" if floor == 0 else f"{floor}–{upper}")
        out.append(f"{s} · {l}: {rng} Rx/month → {v} visits/month")
    return out


def add_columns(df, rx_col="monthly_prescriptions"):
    """Add segment / potential / recommended_visits columns to a DataFrame of doctors."""
    df = df.copy()
    df["segment"] = df[rx_col].map(segment_of) if len(df) else []
    df["potential"] = df["segment"].map(label) if len(df) else []
    df["recommended_visits"] = df["segment"].map(visits_per_month) if len(df) else []
    return df
