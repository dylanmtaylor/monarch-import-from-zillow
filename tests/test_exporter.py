"""Tests for Monarch Money balance history exporter."""

import csv
import os
import tempfile
import unittest
from datetime import date

from zillow_to_monarch.exporter import export_monarch_balance_history_csv


class TestExporter(unittest.TestCase):
    def test_export_balance_history_csv(self):
        daily_balances = [
            (date(2023, 1, 1), 500000.0),
            (date(2023, 1, 2), 500000.0),
            (date(2023, 1, 3), 500125.75),
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "balances.csv")
            written_path = export_monarch_balance_history_csv(daily_balances, out_file)

            self.assertEqual(written_path, os.path.abspath(out_file))
            self.assertTrue(os.path.isfile(written_path))

            with open(written_path, "r", encoding="utf-8") as f:
                reader = list(csv.reader(f))

            self.assertEqual(reader[0], ["Date", "Balance"])
            self.assertEqual(reader[1], ["2023-01-01", "500000.00"])
            self.assertEqual(reader[2], ["2023-01-02", "500000.00"])
            self.assertEqual(reader[3], ["2023-01-03", "500125.75"])
            self.assertEqual(len(reader), 4)


if __name__ == "__main__":
    unittest.main()
