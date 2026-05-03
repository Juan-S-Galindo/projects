from __future__ import annotations
from datetime import date
from dateutil.relativedelta import relativedelta

FREQUENCY_CONFIG: dict[str, dict] = {
    "weekly":          {"label": "Weekly",          "periods_per_year": 52},
    "monthly":         {"label": "Monthly",         "periods_per_year": 12},
    "every_2_months":  {"label": "Every 2 months",  "periods_per_year": 6},
    "quarterly":       {"label": "Quarterly",       "periods_per_year": 4},
    "every_6_months":  {"label": "Every 6 months",  "periods_per_year": 2},
    "yearly":          {"label": "Yearly",          "periods_per_year": 1},
}

FREQUENCY_LABELS = {k: v["label"] for k, v in FREQUENCY_CONFIG.items()}


def monthly_equivalent(amount: float, frequency: str) -> float:
    cfg = FREQUENCY_CONFIG[frequency]
    return round(amount * cfg["periods_per_year"] / 12, 2)


def next_charge_date(last: date, frequency: str) -> date:
    match frequency:
        case "weekly":         return last + relativedelta(weeks=1)
        case "monthly":        return last + relativedelta(months=1)
        case "every_2_months": return last + relativedelta(months=2)
        case "quarterly":      return last + relativedelta(months=3)
        case "every_6_months": return last + relativedelta(months=6)
        case "yearly":         return last + relativedelta(years=1)
        case _:                return last + relativedelta(months=1)


def bill_status(next_date: date | None, last_date: date | None,
                frequency: str, today: date | None = None) -> str:
    today = today or date.today()
    if next_date is None:
        return "upcoming"
    diff_days = (next_date - today).days
    if diff_days < 0:
        return "overdue"
    if diff_days <= 5:
        return "due_soon"
    # Mark as "paid" if the last charge was within the current billing cycle
    if last_date is not None:
        cfg = FREQUENCY_CONFIG[frequency]
        days_in_cycle = 365 / cfg["periods_per_year"]
        days_since_last = (today - last_date).days
        if days_since_last < days_in_cycle:
            return "paid"
    return "upcoming"


def hit_months(start: date, frequency: str, from_month: date, count: int = 12) -> set[str]:
    """Return YYYY-MM strings of months when a bill charges, within the next `count` months."""
    result: set[str] = set()
    cursor = start
    end = from_month + relativedelta(months=count)
    # Walk forward from start until we pass end
    while cursor <= end:
        if cursor >= from_month:
            result.add(cursor.strftime("%Y-%m"))
        cursor = next_charge_date(cursor, frequency)
    return result
