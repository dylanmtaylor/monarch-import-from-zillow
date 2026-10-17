"""Exporter for Monarch Money-compatible balance history CSV files."""

import csv
import os
from datetime import date
from typing import List, Tuple

from .models import ProcessingResult


def export_monarch_balance_history_csv(
    daily_balances: List[Tuple[date, float]],
    output_path: str,
) -> str:
    """Export daily balance snapshots to Monarch-compatible CSV.

    Format:
        Date,Balance
        2024-01-01,550000.00
        2024-01-02,550000.00

    Args:
        daily_balances: List of (date, balance) tuples.
        output_path: Destination path for the CSV file.

    Returns:
        The resolved absolute path of the written CSV file.
    """
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    with open(abs_output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Balance"])
        for d, bal in daily_balances:
            writer.writerow([
                d.strftime("%Y-%m-%d"),
                f"{bal:.2f}",
            ])

    return abs_output


def export_result(result: ProcessingResult, output_path: str) -> str:
    """Convenience function to export a ProcessingResult directly."""
    return export_monarch_balance_history_csv(result.daily_balances, output_path)
