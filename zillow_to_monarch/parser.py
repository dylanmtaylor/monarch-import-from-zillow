"""Parser for Zillow historical valuation data from JSON, HTML, or CSV formats."""

import csv
import json
import re
from datetime import date, datetime, timezone
from io import StringIO
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import PropertyMetadata, ValuationPoint


def _timestamp_to_date(val: Union[int, float, str]) -> date:
    """Convert timestamp (seconds or milliseconds) or date string into a datetime.date."""
    if isinstance(val, (int, float)):
        # Epoch milliseconds (> 1e11) vs epoch seconds (< 1e11)
        ts = val / 1000.0 if val > 1e11 else float(val)
        return datetime.fromtimestamp(ts, tz=timezone.utc).date()

    if isinstance(val, str):
        val = val.strip()
        # Try numeric string (timestamp)
        if val.isdigit() or (val.replace(".", "", 1).isdigit() and val.count(".") <= 1):
            num = float(val)
            ts = num / 1000.0 if num > 1e11 else num
            return datetime.fromtimestamp(ts, tz=timezone.utc).date()

        # Try ISO format YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS
        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y",
            "%Y/%m/%d",
        ):
            try:
                return datetime.strptime(val.split(".")[0].rstrip("Z"), fmt.rstrip("Z")).date()
            except ValueError:
                continue

        # If it has a date-like prefix
        match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", val)
        if match:
            y, m, d = match.groups()
            return date(int(y), int(m), int(d))

    raise ValueError(f"Unable to parse date/timestamp from: {val!r}")


def _clean_numeric_value(val: Any) -> float:
    """Parse numeric dollar value from number or formatted string."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r"[^\d.-]", "", val)
        if cleaned:
            return float(cleaned)
    raise ValueError(f"Unable to parse numeric valuation from: {val!r}")


def parse_points_from_dict(data: Any) -> Tuple[List[ValuationPoint], PropertyMetadata]:
    """Extract ValuationPoints and PropertyMetadata from a parsed JSON dictionary or list."""
    points: List[ValuationPoint] = []
    metadata = PropertyMetadata()

    # Look for metadata in known locations
    if isinstance(data, dict):
        prop_dict = None
        if "data" in data and isinstance(data["data"], dict):
            prop_dict = data["data"].get("property")
        elif "property" in data and isinstance(data["property"], dict):
            prop_dict = data["property"]
        elif "zpid" in data:
            prop_dict = data

        if isinstance(prop_dict, dict):
            metadata.zpid = str(prop_dict.get("zpid")) if prop_dict.get("zpid") else None
            metadata.current_zestimate = (
                float(prop_dict.get("zestimate"))
                if prop_dict.get("zestimate") is not None
                else None
            )
            addr = prop_dict.get("address")
            if isinstance(addr, dict):
                metadata.address = addr.get("streetAddress")
                metadata.city = addr.get("city")
                metadata.state = addr.get("state")
                metadata.zip_code = addr.get("zipcode")
            elif isinstance(addr, str):
                metadata.address = addr

    # 1. Check for GraphQL zestimateHistory: property.zestimateHistory or data.property.zestimateHistory
    history_list = None
    if isinstance(data, dict):
        # Path 1: data -> property -> zestimateHistory
        if "data" in data and isinstance(data["data"], dict):
            history_list = data["data"].get("property", {}).get("zestimateHistory")
        # Path 2: property -> zestimateHistory
        if not history_list and "property" in data and isinstance(data["property"], dict):
            history_list = data["property"].get("zestimateHistory")
        # Path 3: direct zestimateHistory key
        if not history_list and "zestimateHistory" in data:
            history_list = data["zestimateHistory"]

    if isinstance(history_list, list) and history_list:
        for item in history_list:
            if isinstance(item, dict):
                t_val = item.get("t") or item.get("time") or item.get("timestamp") or item.get("date")
                v_val = item.get("v") or item.get("value") or item.get("price") or item.get("zestimate")
                if t_val is not None and v_val is not None:
                    try:
                        p_date = _timestamp_to_date(t_val)
                        p_val = _clean_numeric_value(v_val)
                        points.append(ValuationPoint(date=p_date, value=p_val, source="zestimateHistory"))
                    except Exception:
                        continue

    # 2. Check for homeValueChartData structure:
    # {"homeValueChartData": [{"name": "This home", "points": [{"x": ..., "y": ...}]}]}
    if not points and isinstance(data, dict):
        chart_data = data.get("homeValueChartData")
        if isinstance(chart_data, list):
            series = None
            # Prefer series named "This home" or "Zestimate"
            for s in chart_data:
                if isinstance(s, dict) and s.get("name") in ("This home", "Zestimate", "Home value"):
                    series = s
                    break
            if not series and chart_data and isinstance(chart_data[0], dict) and "points" in chart_data[0]:
                series = chart_data[0]

            if series and isinstance(series.get("points"), list):
                for pt in series["points"]:
                    if isinstance(pt, dict) and "x" in pt and "y" in pt:
                        try:
                            points.append(
                                ValuationPoint(
                                    date=_timestamp_to_date(pt["x"]),
                                    value=_clean_numeric_value(pt["y"]),
                                    source="homeValueChartData",
                                )
                            )
                        except Exception:
                            continue

    # 3. Direct array of points or chart series
    if not points and isinstance(data, list):
        # Case A: List of series objects
        if data and isinstance(data[0], dict) and "points" in data[0]:
            target = next(
                (s for s in data if isinstance(s, dict) and s.get("name") in ("This home", "Zestimate")),
                data[0],
            )
            for pt in target.get("points", []):
                if isinstance(pt, dict) and "x" in pt and "y" in pt:
                    try:
                        points.append(
                            ValuationPoint(
                                date=_timestamp_to_date(pt["x"]),
                                value=_clean_numeric_value(pt["y"]),
                                source="chart_series",
                            )
                        )
                    except Exception:
                        continue
        # Case B: Flat list of point objects
        else:
            for item in data:
                if isinstance(item, dict):
                    # Check {t, v}, {x, y}, or {date, value/balance/price}
                    t_val = item.get("t") or item.get("x") or item.get("date") or item.get("time")
                    v_val = (
                        item.get("v")
                        or item.get("y")
                        or item.get("value")
                        or item.get("balance")
                        or item.get("price")
                        or item.get("zestimate")
                    )
                    if t_val is not None and v_val is not None:
                        try:
                            points.append(
                                ValuationPoint(
                                    date=_timestamp_to_date(t_val),
                                    value=_clean_numeric_value(v_val),
                                    source="point_list",
                                )
                            )
                        except Exception:
                            continue

    # 4. Deep search for zestimateHistory or homeValueChartData in nested dictionaries (e.g., Next.js gdpClientCache)
    if not points and isinstance(data, dict):
        points, found_meta = _recursive_find_history(data)
        if found_meta.zpid and not metadata.zpid:
            metadata.zpid = found_meta.zpid
        if found_meta.address and not metadata.address:
            metadata.address = found_meta.address

    # Deduplicate points by date (keep last seen point for each date)
    date_map: Dict[date, ValuationPoint] = {}
    for p in points:
        date_map[p.date] = p

    sorted_points = sorted(date_map.values(), key=lambda pt: pt.date)
    return sorted_points, metadata


def _recursive_find_history(data: Any, depth: int = 0) -> Tuple[List[ValuationPoint], PropertyMetadata]:
    """Helper to search deeply nested JSON objects for valuation history arrays."""
    if depth > 10 or not isinstance(data, (dict, list)):
        return [], PropertyMetadata()

    if isinstance(data, dict):
        # Look for zestimateHistory key
        if "zestimateHistory" in data and isinstance(data["zestimateHistory"], list):
            res_points, res_meta = parse_points_from_dict({"zestimateHistory": data["zestimateHistory"]})
            if res_points:
                return res_points, res_meta

        # Look for homeValueChartData key
        if "homeValueChartData" in data and isinstance(data["homeValueChartData"], list):
            res_points, res_meta = parse_points_from_dict({"homeValueChartData": data["homeValueChartData"]})
            if res_points:
                return res_points, res_meta

        # Check sub-keys
        for k, v in data.items():
            if isinstance(v, (dict, list)):
                pts, meta = _recursive_find_history(v, depth + 1)
                if pts:
                    return pts, meta

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                pts, meta = _recursive_find_history(item, depth + 1)
                if pts:
                    return pts, meta

    return [], PropertyMetadata()


def parse_zillow_json(json_content: str) -> Tuple[List[ValuationPoint], PropertyMetadata]:
    """Parse JSON string from Zillow API, DevTools export, or saved payload."""
    try:
        data = json.loads(json_content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON data: {e}") from e

    points, metadata = parse_points_from_dict(data)
    if not points:
        raise ValueError(
            "No historical valuation points (zestimateHistory or homeValueChartData) found in JSON."
        )
    return points, metadata


def parse_zillow_html(html_content: str) -> Tuple[List[ValuationPoint], PropertyMetadata]:
    """Parse Zillow property page HTML, searching for __NEXT_DATA__ or embedded scripts."""
    # Try finding __NEXT_DATA__
    next_data_match = re.search(
        r'<script\s+id="__NEXT_DATA__"\s+type="application/json">([^<]+)</script>',
        html_content,
        re.DOTALL,
    )
    if next_data_match:
        try:
            return parse_zillow_json(next_data_match.group(1))
        except Exception:
            pass

    # Try finding homeValueChartData in arbitrary <script> tags
    chart_match = re.search(r"homeValueChartData\s*=\s*(\[[^;]+\]);", html_content)
    if chart_match:
        try:
            return parse_zillow_json(chart_match.group(1))
        except Exception:
            pass

    # Try finding zestimateHistory in arbitrary scripts
    history_match = re.search(r'"zestimateHistory"\s*:\s*(\[[^\]]+\])', html_content)
    if history_match:
        try:
            return parse_zillow_json(f'{{"zestimateHistory": {history_match.group(1)}}}')
        except Exception:
            pass

    raise ValueError(
        "Could not locate embedded valuation data (__NEXT_DATA__ or chart data) in HTML."
    )


def parse_valuation_csv(csv_content: str) -> Tuple[List[ValuationPoint], PropertyMetadata]:
    """Parse valuation history from a CSV format (e.g. Date,Balance or Date,Value)."""
    f = StringIO(csv_content.strip())
    reader = csv.reader(f)
    header = next(reader, None)
    if not header:
        raise ValueError("CSV is empty.")

    header_lower = [h.strip().lower() for h in header]
    date_col = -1
    val_col = -1

    for idx, col in enumerate(header_lower):
        if col in ("date", "time", "timestamp", "month"):
            date_col = idx
        elif col in ("balance", "value", "price", "zestimate", "amount"):
            val_col = idx

    if date_col == -1 or val_col == -1:
        # Fallback to col 0 = date, col 1 = value
        if len(header) >= 2:
            date_col = 0
            val_col = 1
        else:
            raise ValueError(f"Could not identify Date and Balance columns in CSV header: {header}")

    points: List[ValuationPoint] = []
    for row in reader:
        if not row or len(row) <= max(date_col, val_col):
            continue
        try:
            p_date = _timestamp_to_date(row[date_col])
            p_val = _clean_numeric_value(row[val_col])
            points.append(ValuationPoint(date=p_date, value=p_val, source="csv"))
        except Exception:
            continue

    if not points:
        raise ValueError("No valid valuation points parsed from CSV.")

    # Deduplicate and sort
    date_map = {p.date: p for p in points}
    sorted_points = sorted(date_map.values(), key=lambda pt: pt.date)
    return sorted_points, PropertyMetadata()


def parse_source_content(content: str) -> Tuple[List[ValuationPoint], PropertyMetadata]:
    """Auto-detect format (JSON, HTML, CSV) and parse valuation points."""
    trimmed = content.strip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        return parse_zillow_json(trimmed)
    if "<html" in trimmed.lower() or "<!doctype" in trimmed.lower() or "<script" in trimmed.lower():
        return parse_zillow_html(trimmed)
    # Default to CSV parser
    return parse_valuation_csv(trimmed)
