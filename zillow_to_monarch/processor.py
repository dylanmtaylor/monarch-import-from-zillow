"""Processes Zillow valuation points into continuous daily balance history."""

from datetime import date, timedelta
from typing import List, Optional, Tuple

from .models import PropertyMetadata, ProcessingResult, ValuationPoint


def process_zillow_valuation(
    raw_points: List[ValuationPoint],
    purchase_date: Optional[date] = None,
    end_date: Optional[date] = None,
    interpolation_method: str = "forward-fill",
    property_metadata: Optional[PropertyMetadata] = None,
) -> ProcessingResult:
    """Process raw valuation points into a continuous daily balance history for Monarch Money.

    Args:
        raw_points: List of ValuationPoint objects parsed from Zillow data.
        purchase_date: Optional date of property purchase. If omitted, history defaults
                       to going back to the beginning of time in Zillow data.
        end_date: Optional end date for the history timeline (defaults to today or the latest
                  data point if in the future).
        interpolation_method: "forward-fill" (default, step-wise carrying forward of valuation)
                              or "linear" (smooth daily interpolation between valuation points).
        property_metadata: Optional PropertyMetadata object.

    Returns:
        ProcessingResult containing continuous daily balances and summary statistics.
    """
    if not raw_points:
        raise ValueError("Cannot process empty valuation points list.")

    if property_metadata is None:
        property_metadata = PropertyMetadata()

    method_norm = interpolation_method.lower().strip()
    if method_norm not in ("forward-fill", "step", "linear"):
        raise ValueError(
            f"Unsupported interpolation method: '{interpolation_method}'. "
            "Supported methods: 'forward-fill', 'linear'."
        )

    # Sort raw points chronologically
    sorted_points = sorted(raw_points, key=lambda p: p.date)
    earliest_zillow_date = sorted_points[0].date
    latest_zillow_date = sorted_points[-1].date

    warnings: List[str] = []

    # Determine timeline start date and initial balance
    if purchase_date is not None:
        start_date = purchase_date
        if purchase_date < earliest_zillow_date:
            warnings.append(
                f"Purchase date ({purchase_date}) is earlier than Zillow's earliest record ({earliest_zillow_date}). "
                f"Back-filling starting valuation using earliest Zillow estimate (${sorted_points[0].value:,.2f})."
            )
    else:
        # Default to the beginning of time in Zillow data
        start_date = earliest_zillow_date

    # Determine timeline end date
    today = date.today()
    if end_date is not None:
        target_end_date = end_date
    else:
        target_end_date = max(today, latest_zillow_date)

    if start_date > target_end_date:
        raise ValueError(
            f"Start date ({start_date}) cannot be after end date ({target_end_date})."
        )

    # Build reference anchors: list of (date, value)
    anchors: List[Tuple[date, float]] = []

    # Determine starting value on start_date from Zillow points
    initial_value = _determine_value_at_date(
        sorted_points, start_date, method_norm
    )

    anchors.append((start_date, initial_value))

    # Add all Zillow data points strictly after start_date and up to target_end_date
    for pt in sorted_points:
        if start_date < pt.date <= target_end_date:
            anchors.append((pt.date, pt.value))

    # If the last anchor is before target_end_date, carry forward latest known valuation to target_end_date
    last_anchor_date, last_anchor_val = anchors[-1]
    if last_anchor_date < target_end_date:
        anchors.append((target_end_date, last_anchor_val))

    # Remove any duplicate dates in anchors (keeping last)
    unique_anchors: List[Tuple[date, float]] = []
    seen_dates = set()
    for d, val in reversed(anchors):
        if d not in seen_dates:
            seen_dates.add(d)
            unique_anchors.append((d, val))
    unique_anchors.reverse()
    unique_anchors.sort(key=lambda a: a[0])

    # Generate daily balances for every single calendar day from start_date to target_end_date
    daily_balances: List[Tuple[date, float]] = []
    num_days = (target_end_date - start_date).days + 1

    anchor_idx = 0
    num_anchors = len(unique_anchors)

    curr_date = start_date
    while curr_date <= target_end_date:
        # Advance anchor_idx to bounding segment
        while (
            anchor_idx + 1 < num_anchors
            and unique_anchors[anchor_idx + 1][0] <= curr_date
        ):
            anchor_idx += 1

        d0, v0 = unique_anchors[anchor_idx]

        if method_norm == "linear" and anchor_idx + 1 < num_anchors:
            d1, v1 = unique_anchors[anchor_idx + 1]
            total_span = (d1 - d0).days
            if total_span > 0:
                elapsed = (curr_date - d0).days
                ratio = elapsed / total_span
                day_val = v0 + ratio * (v1 - v0)
            else:
                day_val = v0
        else:
            # forward-fill / step
            day_val = v0

        daily_balances.append((curr_date, round(day_val, 2)))
        curr_date += timedelta(days=1)

    return ProcessingResult(
        raw_points=sorted_points,
        daily_balances=daily_balances,
        start_date=start_date,
        end_date=target_end_date,
        initial_value=daily_balances[0][1],
        latest_value=daily_balances[-1][1],
        property_metadata=property_metadata,
        purchase_date=purchase_date,
        interpolation_method="linear" if method_norm == "linear" else "forward-fill",
        warnings=warnings,
    )


def _determine_value_at_date(
    points: List[ValuationPoint], target_date: date, method: str
) -> float:
    """Find or interpolate property valuation at a specific target date."""
    if not points:
        raise ValueError("Points list is empty.")

    # Check for exact date match
    for pt in points:
        if pt.date == target_date:
            return pt.value

    # If target_date is before earliest point
    if target_date < points[0].date:
        return points[0].value

    # If target_date is after latest point
    if target_date > points[-1].date:
        return points[-1].value

    # Target date lies between points: find preceding and succeeding points
    p_prev = points[0]
    p_next = points[-1]
    for i in range(len(points) - 1):
        if points[i].date <= target_date <= points[i + 1].date:
            p_prev = points[i]
            p_next = points[i + 1]
            break

    if method == "linear":
        span = (p_next.date - p_prev.date).days
        if span > 0:
            elapsed = (target_date - p_prev.date).days
            ratio = elapsed / span
            return p_prev.value + ratio * (p_next.value - p_prev.value)
        return p_prev.value

    # forward-fill
    return p_prev.value
