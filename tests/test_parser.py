"""Tests for Zillow valuation data parser."""

import json
import unittest
from datetime import date

from zillow_to_monarch.parser import (
    parse_points_from_dict,
    parse_source_content,
    parse_valuation_csv,
    parse_zillow_html,
    parse_zillow_json,
)


class TestParser(unittest.TestCase):
    def test_parse_graphql_zestimate_history_seconds(self):
        payload = {
            "data": {
                "property": {
                    "zpid": "12345678",
                    "zestimate": 525000,
                    "address": {
                        "streetAddress": "742 Evergreen Terrace",
                        "city": "Springfield",
                        "state": "OR",
                        "zipcode": "97477",
                    },
                    "zestimateHistory": [
                        {"t": 1577836800, "v": 350000},  # 2020-01-01
                        {"t": 1580515200, "v": 355000},  # 2020-02-01
                        {"t": 1583020800, "v": 360000},  # 2020-03-01
                    ],
                }
            }
        }
        points, meta = parse_points_from_dict(payload)
        self.assertEqual(len(points), 3)
        self.assertEqual(meta.zpid, "12345678")
        self.assertEqual(meta.address, "742 Evergreen Terrace")
        self.assertEqual(meta.city, "Springfield")
        self.assertEqual(meta.state, "OR")
        self.assertEqual(points[0].date, date(2020, 1, 1))
        self.assertEqual(points[0].value, 350000.0)
        self.assertEqual(points[2].date, date(2020, 3, 1))
        self.assertEqual(points[2].value, 360000.0)

    def test_parse_graphql_zestimate_history_milliseconds(self):
        payload = {
            "property": {
                "zpid": "87654321",
                "zestimateHistory": [
                    {"t": 1609459200000, "v": 450000},  # 2021-01-01
                    {"t": 1612137600000, "v": 455000},  # 2021-02-01
                ],
            }
        }
        points, meta = parse_zillow_json(json.dumps(payload))
        self.assertEqual(len(points), 2)
        self.assertEqual(meta.zpid, "87654321")
        self.assertEqual(points[0].date, date(2021, 1, 1))
        self.assertEqual(points[0].value, 450000.0)

    def test_parse_home_value_chart_data(self):
        payload = {
            "homeValueChartData": [
                {
                    "name": "This home",
                    "points": [
                        {"x": 1577836800000, "y": 300000},  # 2020-01-01
                        {"x": 1580515200000, "y": 310000},  # 2020-02-01
                    ],
                },
                {
                    "name": "Springfield",
                    "points": [
                        {"x": 1577836800000, "y": 250000},
                    ],
                },
            ]
        }
        points, meta = parse_points_from_dict(payload)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].date, date(2020, 1, 1))
        self.assertEqual(points[0].value, 300000.0)
        self.assertEqual(points[1].date, date(2020, 2, 1))
        self.assertEqual(points[1].value, 310000.0)

    def test_parse_flat_point_list(self):
        raw_list = [
            {"date": "2022-05-15", "value": 415000},
            {"date": "2022-06-15", "value": 420000},
        ]
        points, meta = parse_points_from_dict(raw_list)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].date, date(2022, 5, 15))
        self.assertEqual(points[0].value, 415000.0)

    def test_parse_html_embedded_next_data(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Zillow Property</title></head>
        <body>
          <script id="__NEXT_DATA__" type="application/json">
          {
            "props": {
              "pageProps": {
                "componentProps": {
                  "gdpClientCache": {
                    "property": {
                      "zpid": "99999",
                      "zestimateHistory": [
                        {"t": 1640995200000, "v": 500000}
                      ]
                    }
                  }
                }
              }
            }
          }
          </script>
        </body>
        </html>
        """
        points, meta = parse_zillow_html(html)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].date, date(2022, 1, 1))
        self.assertEqual(points[0].value, 500000.0)

    def test_parse_csv_content(self):
        csv_data = """Date,Balance
2023-01-01,600000.00
2023-02-01,605000.50
"""
        points, _ = parse_valuation_csv(csv_data)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].date, date(2023, 1, 1))
        self.assertEqual(points[0].value, 600000.0)
        self.assertEqual(points[1].date, date(2023, 2, 1))
        self.assertEqual(points[1].value, 605000.50)

    def test_auto_detect_json(self):
        json_str = '{"zestimateHistory": [{"t": 1577836800, "v": 300000}]}'
        points, _ = parse_source_content(json_str)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].value, 300000.0)

    def test_auto_detect_csv(self):
        csv_str = "Date,Balance\n2023-01-01,400000"
        points, _ = parse_source_content(csv_str)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].value, 400000.0)

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            parse_zillow_json("not json at all")

    def test_empty_json_history_raises(self):
        with self.assertRaises(ValueError):
            parse_zillow_json('{"foo": "bar"}')


if __name__ == "__main__":
    unittest.main()
