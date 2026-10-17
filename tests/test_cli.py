"""Tests for command-line interface."""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from zillow_to_monarch.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.sample_data = {
            "property": {
                "zpid": "55555555",
                "zestimateHistory": [
                    {"t": 1609459200, "v": 400000},  # 2021-01-01
                    {"t": 1612137600, "v": 410000},  # 2021-02-01
                    {"t": 1614556800, "v": 420000},  # 2021-03-01
                ],
            }
        }

    def test_cli_snippet_flag(self):
        f = io.StringIO()
        with self.assertRaises(SystemExit) as cm:
            with redirect_stdout(f):
                with patch("sys.argv", ["zillow-to-monarch", "--snippet"]):
                    main()
        self.assertEqual(cm.exception.code, 0)
        output = f.getvalue()
        self.assertIn("HomeValueChartDataQuery", output)
        self.assertIn("extractZillowHistory", output)

    def test_cli_local_file_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "input.json")
            with open(input_file, "w", encoding="utf-8") as f:
                json.dump(self.sample_data, f)

            output_file = os.path.join(tmpdir, "output.csv")
            f = io.StringIO()

            with redirect_stdout(f):
                with patch(
                    "sys.argv",
                    [
                        "zillow-to-monarch",
                        input_file,
                        "-o",
                        output_file,
                        "-e",
                        "2021-03-01",
                    ],
                ):
                    main()

            output = f.getvalue()
            self.assertIn("Export complete", output)
            self.assertIn("Starting Valuation: $400,000.00", output)
            self.assertIn("Latest Valuation:   $420,000.00", output)
            self.assertTrue(os.path.isfile(output_file))

            with open(output_file, "r", encoding="utf-8") as csv_f:
                lines = csv_f.readlines()
            self.assertEqual(lines[0].strip(), "Date,Balance")
            # 2021-01-01 to 2021-03-01 is 60 days -> 61 lines (header + 60 days)
            self.assertEqual(len(lines), 61)

    def test_cli_with_purchase_date_and_price(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, "input.json")
            with open(input_file, "w", encoding="utf-8") as f:
                json.dump(self.sample_data, f)

            output_file = os.path.join(tmpdir, "output.csv")
            f = io.StringIO()

            with redirect_stdout(f):
                with patch(
                    "sys.argv",
                    [
                        "zillow-to-monarch",
                        input_file,
                        "-o",
                        output_file,
                        "-p",
                        "2021-02-01",
                        "--purchase-price",
                        "405000",
                        "-e",
                        "2021-03-01",
                    ],
                ):
                    main()

            output = f.getvalue()
            self.assertIn("Starting Valuation: $405,000.00", output)
            self.assertIn("Latest Valuation:   $420,000.00", output)
            self.assertTrue(os.path.isfile(output_file))

            with open(output_file, "r", encoding="utf-8") as csv_f:
                lines = csv_f.readlines()
            self.assertEqual(lines[1].strip(), "2021-02-01,405000.00")


if __name__ == "__main__":
    unittest.main()
