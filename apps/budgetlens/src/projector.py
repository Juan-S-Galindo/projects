from __future__ import annotations
import math
from datetime import date


def compute_projection(
    monthly_income: float,
    total_monthly_bills: float,
    avg_variable_spending: float,
    what_if_cuts: dict[str, float] | None = None,
) -> dict:
    """Pure function — no DB calls."""
    cuts = sum((what_if_cuts or {}).values())
    adjusted_variable = max(0.0, avg_variable_spending - cuts)
    projected_savable = monthly_income - total_monthly_bills - avg_variable_spending
    adjusted_savable = monthly_income - total_monthly_bills - adjusted_variable
    return {
        "monthly_income": monthly_income,
        "total_monthly_bills": total_monthly_bills,
        "avg_variable_spending": avg_variable_spending,
        "projected_savable": projected_savable,
        "adjusted_savable": adjusted_savable,
        "total_cuts": cuts,
    }


def months_to_goal(target: float, current: float, monthly_contribution: float) -> int | None:
    remaining = target - current
    if remaining <= 0:
        return 0
    if monthly_contribution <= 0:
        return None
    return math.ceil(remaining / monthly_contribution)


def goal_on_track(target: float, current: float, target_date: date,
                  monthly_contribution: float, today: date | None = None) -> bool:
    today = today or date.today()
    months_left = (target_date.year - today.year) * 12 + (target_date.month - today.month)
    if months_left <= 0:
        return current >= target
    needed_per_month = (target - current) / months_left
    return monthly_contribution >= needed_per_month
