"""Tests for Zillow valuation processing and daily balance history generation."""

import unittest
from datetime import date, timedelta

from zillow_to_monarch.models import ValuationPoint
from zillow_to_monarch.processor import process_zillow_valuation


class TestProcessor(unittest.TestCase):
    def setUp(self):
        # Sample valuation points: 2021-01-01 -> 2021-04-01
        self.raw_points = [
            ValuationPoint(date=date(2021, 1, 1), value=300000.0),
            ValuationPoint(date=date(2021, 2, 1), value=310000.0),
            ValuationPoint(date=date(2021, 3, 1), value=320000.0),
            ValuationPoint(date=date(2021, 4, 1), value=330000.0),
        ]

    def test_default_beginning_of_time(self):
        """When purchase_date is omitted, history starts at the earliest Zillow record."""
        result = process_zillow_valuation(
            raw_points=self.raw_points,
            end_date=date(2021, 4, 1),
            interpolation_method="forward-fill",
        )
        self.assertEqual(result.start_date, date(2021, 1, 1))
        self.assertEqual(result.initial_value, 300000.0)
        self.assertEqual(result.end_date, date(2021, 4, 1))
        self.assertEqual(result.latest_value, 330000.0)
        self.assertEqual(result.value_change, 30000.0)
        self.assertEqual(result.percent_change, 10.0)

    def test_daily_continuity(self):
        """Verify every single calendar day is present without gaps."""
        start = date(2021, 1, 1)
        end = date(2021, 4, 1)
        expected_days = (end - start).days + 1

        result = process_zillow_valuation(
            raw_points=self.raw_points,
            end_date=end,
        )
        self.assertEqual(len(result.daily_balances), expected_days)

        # Check consecutive dates
        for idx in range(len(result.daily_balances) - 1):
            curr_d = result.daily_balances[idx][0]
            next_d = result.daily_balances[idx + 1][0]
            self.assertEqual(next_d - curr_d, timedelta(days=1))

    def test_purchase_date_filtering(self):
        """When purchase_date is provided, earlier Zillow points are excluded."""
        purchase_date = date(2021, 2, 15)
        result = process_zillow_valuation(
            raw_points=self.raw_points,
            purchase_date=purchase_date,
            end_date=date(2021, 4, 1),
            interpolation_method="forward-fill",
        )
        self.assertEqual(result.start_date, purchase_date)
        # With forward-fill, on 2021-02-15 the value comes from 2021-02-01 ($310,000)
        self.assertEqual(result.initial_value, 310000.0)
        self.assertEqual(result.daily_balances[0][0], purchase_date)

    def test_purchase_price_override(self):
        """When purchase_price is provided, starting valuation on purchase_date matches it."""
        purchase_date = date(2021, 2, 15)
        purchase_price = 305000.0
        result = process_zillow_valuation(
            raw_points=self.raw_points,
            purchase_date=purchase_date,
            purchase_price=purchase_price,
            end_date=date(2021, 4, 1),
            interpolation_method="forward-fill",
        )
        self.assertEqual(result.start_date, purchase_date)
        self.assertEqual(result.initial_value, purchase_price)
        self.assertEqual(result.daily_balances[0][1], purchase_price)

    def test_purchase_date_before_zillow_earliest(self):
        """Handle purchase date prior to Zillow records gracefully."""
        purchase_date = date(2020, 6, 1)  # before 2021-01-01
        result = process_zillow_valuation(
            raw_points=self.raw_points,
            purchase_date=purchase_date,
            purchase_price=275000.0,
            end_date=date(2021, 1, 15),
        )
        self.assertEqual(result.start_date, purchase_date)
        self.assertEqual(result.initial_value, 275000.0)
        self.assertTrue(len(result.warnings) > 0)

    def test_forward_fill_interpolation(self):
        """Forward-fill keeps valuation constant until the next anchor date."""
        result = process_zillow_valuation(
            raw_points=self.raw_points,
            end_date=date(2021, 2, 1),
            interpolation_method="forward-fill",
        )
        # All days in January should be 300000.00
        jan_15 = [bal for d, bal in result.daily_balances if d == date(2021, 1, 15)][0]
        jan_31 = [bal for d, bal in result.daily_balances if d == date(2021, 1, 31)][0]
        feb_1 = [bal for d, bal in result.daily_balances if d == date(2021, 2, 1)][0]

        self.assertEqual(jan_15, 300000.0)
        self.assertEqual(jan_31, 300000.0)
        self.assertEqual(feb_1, 310000.0)

    def test_linear_interpolation(self):
        """Linear interpolation creates a smooth progression between monthly anchors."""
        result = process_zillow_valuation(
            raw_points=[
                ValuationPoint(date=date(2021, 1, 1), value=300000.0),
                ValuationPoint(date=date(2021, 1, 31), value=330000.0),
            ],
            end_date=date(2021, 1, 31),
            interpolation_method="linear",
        )
        # Midpoint on 2021-01-16 (15 days elapsed out of 30) -> 300000 + 15000 = 315000
        mid = [bal for d, bal in result.daily_balances if d == date(2021, 1, 16)][0]
        self.assertEqual(mid, 315000.0)

    def test_empty_points_raises(self):
        with self.assertRaises(ValueError):
            process_zillow_valuation(raw_points=[])


if __name__ == "__main__":
    unittest.main()
