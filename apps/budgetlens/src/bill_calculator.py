from __future__ import annotations
from datetime import date
from dateutil.relativedelta import relativedelta

PERIOD_UNITS: dict[str, str] = {
    "months": "Month(s)",
    "years":  "Year(s)",
}


def monthly_equivalent(amount: float, unit: str, count: int = 1) -> float:
    if unit == "weeks":
        return round(amount * 52 / count / 12, 2)
    elif unit == "years":
        return round(amount / (count * 12), 2)
    else:  # months
        return round(amount / count, 2)


def next_charge_date(last: date, unit: str, count: int = 1) -> date:
    if unit == "weeks":
        return last + relativedelta(weeks=count)
    elif unit == "years":
        return last + relativedelta(years=count)
    else:  # months
        return last + relativedelta(months=count)


def bill_status(next_date: date | None, last_date: date | None,
                unit: str, count: int = 1, today: date | None = None) -> str:
    today = today or date.today()
    if next_date is None:
        return "upcoming"
    diff_days = (next_date - today).days
    if diff_days < 0:
        return "overdue"
    if diff_days <= 5:
        return "due_soon"
    if last_date is not None:
        if unit == "weeks":
            days_in_cycle = 7 * count
        elif unit == "years":
            days_in_cycle = 365 * count
        else:
            days_in_cycle = 365 / (12 / count)
        if (today - last_date).days < days_in_cycle:
            return "paid"
    return "upcoming"


def hit_months(start: date, unit: str, count: int, from_month: date, num: int = 12) -> set[str]:
    """Return YYYY-MM strings of months when a bill charges within the next `num` months."""
    result: set[str] = set()
    cursor = start
    end = from_month + relativedelta(months=num)
    while cursor <= end:
        if cursor >= from_month:
            result.add(cursor.strftime("%Y-%m"))
        cursor = next_charge_date(cursor, unit, count)
    return result


def frequency_label(unit: str, count: int) -> str:
    unit_label = PERIOD_UNITS.get(unit, unit)
    return f"Every {count} {unit_label}" if count != 1 else f"Every {unit_label.rstrip('(s)')}"
