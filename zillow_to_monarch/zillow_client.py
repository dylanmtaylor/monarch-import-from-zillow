"""Client for fetching historical valuation data directly from Zillow."""

import json
import os
import re
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

GRAPHQL_URL = "https://www.zillow.com/graphql/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

GRAPHQL_QUERY = """
query HomeValueChartDataQuery($zpid: ID!, $metricType: HomeValueChartMetricType, $timePeriod: HomeValueChartTimePeriod) {
  property(zpid: $zpid) {
    homeValueChartData(metricType: $metricType, timePeriod: $timePeriod) {
      points {
        x
        y
      }
      name
    }
  }
}
"""


class PerimeterXBlockedError(Exception):
    """Raised when Zillow's PerimeterX / HUMAN Security bot wall intercepts the request."""
    pass


def extract_zpid(source: str) -> str:
    """Extract numeric Zillow Property ID (ZPID) from a URL or raw ID string.

    Examples:
        - "https://www.zillow.com/homedetails/123-Main-St/12345678_zpid/" -> "12345678"
        - "12345678_zpid" -> "12345678"
        - "12345678" -> "12345678"
    """
    clean_src = source.strip()
    match = re.search(r"(\d+)_zpid", clean_src)
    if match:
        return match.group(1)

    # Check if purely digits
    if clean_src.isdigit():
        return clean_src

    # Look for any trailing sequence of digits
    digits_match = re.findall(r"\b\d{6,12}\b", clean_src)
    if digits_match:
        return digits_match[-1]

    raise ValueError(
        f"Could not extract a valid ZPID from input: '{source}'. "
        "Expected numeric ZPID or Zillow URL (e.g. '.../12345678_zpid/')."
    )


def fetch_zillow_history(
    zpid_or_url: str,
    cookie: Optional[str] = None,
    timeout: int = 15,
) -> str:
    """Fetch property valuation history from Zillow's GraphQL API.

    Args:
        zpid_or_url: Property ZPID or Zillow URL.
        cookie: Optional cookie string from a logged-in or verified browser session.
        timeout: Request timeout in seconds.

    Returns:
        Raw JSON response string.

    Raises:
        PerimeterXBlockedError: If PerimeterX anti-bot verification blocks the request.
        ValueError: If ZPID extraction or query parameters are invalid.
    """
    zpid = extract_zpid(zpid_or_url)

    # Use cookie argument, fallback to ZILLOW_COOKIE environment variable
    session_cookie = cookie or os.environ.get("ZILLOW_COOKIE", "").strip()

    payload = {
        "operationName": "HomeValueChartDataQuery",
        "variables": {
            "zpid": int(zpid) if zpid.isdigit() else zpid,
            "timePeriod": "TEN_YEARS",
            "metricType": "LOCAL_HOME_VALUES",
            "forecast": True,
        },
        "query": GRAPHQL_QUERY,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "client-id": "hdp-react-web-client",
    }

    if session_cookie:
        headers["Cookie"] = session_cookie

    post_data = json.dumps(payload).encode("utf-8")
    req = Request(GRAPHQL_URL, data=post_data, headers=headers, method="POST")

    try:
        with urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            raw_body = response.read().decode("utf-8", errors="replace")

            if "px-captcha" in raw_body or "Access to this page has been denied" in raw_body:
                raise PerimeterXBlockedError(
                    "Zillow's PerimeterX / HUMAN anti-bot protection challenged this request."
                )

            return raw_body

    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        if e.code in (403, 429) or "px-captcha" in error_body or "denied" in error_body.lower():
            raise PerimeterXBlockedError(
                f"Zillow returned HTTP {e.code} (Anti-Bot Challenge). "
                "PerimeterX blocked direct automated request."
            ) from e
        raise RuntimeError(f"Zillow GraphQL query failed with HTTP {e.code}: {e.reason}") from e

    except URLError as e:
        raise RuntimeError(f"Network error communicating with Zillow: {e.reason}") from e
