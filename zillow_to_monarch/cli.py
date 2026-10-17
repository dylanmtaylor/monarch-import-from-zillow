"""Command-line interface for zillow-to-monarch."""

import argparse
import os
import sys
from datetime import date, datetime
from typing import Optional

from .exporter import export_result
from .parser import parse_source_content
from .processor import process_zillow_valuation
from .snippet import get_browser_snippet
from .zillow_client import PerimeterXBlockedError, fetch_zillow_history


def parse_date_arg(val: Optional[str]) -> Optional[date]:
    """Parse date argument in YYYY-MM-DD format."""
    if not val:
        return None
    try:
        return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Invalid date format '{val}'. Expected YYYY-MM-DD."
        ) from e


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zillow-to-monarch",
        description=(
            "Extract real estate valuation history from Zillow and generate a continuous "
            "daily balance history CSV for import into Monarch Money."
        ),
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=None,
        metavar="SOURCE",
        help=(
            "Zillow URL, ZPID, or path to local JSON/HTML/CSV file containing valuation data."
        ),
    )
    parser.add_argument(
        "-p", "--purchase-date",
        type=parse_date_arg,
        default=None,
        help=(
            "Date property was purchased (YYYY-MM-DD). If omitted, history defaults to "
            "the beginning of time in Zillow's dataset."
        ),
    )
    parser.add_argument(
        "-o", "--output",
        default="./output/monarch_zillow_balance_history.csv",
        help="Destination path for Monarch balance history CSV (default: ./output/monarch_zillow_balance_history.csv).",
    )
    parser.add_argument(
        "-m", "--method",
        choices=["forward-fill", "linear"],
        default="forward-fill",
        help="Daily timeline method: 'forward-fill' (step-wise, default) or 'linear' (smooth interpolation).",
    )
    parser.add_argument(
        "-e", "--end-date",
        type=parse_date_arg,
        default=None,
        help="End date for balance history (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "-a", "--asset-name",
        default=None,
        help="Optional asset/property label for logs and preview in Monarch.",
    )
    parser.add_argument(
        "-c", "--cookie",
        default=None,
        help="Optional Zillow session cookie string for direct fetching.",
    )
    parser.add_argument(
        "--snippet",
        action="store_true",
        help="Print the ready-to-use DevTools console snippet for 1-click browser export and exit.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.snippet:
        print("// =========================================================")
        print("// Zillow Zestimate DevTools Console Exporter")
        print("// 1. Open your property page on Zillow.com in Chrome/Firefox")
        print("// 2. Press F12 -> Console -> Paste the code below -> Enter")
        print("// =========================================================")
        print(get_browser_snippet())
        sys.exit(0)

    if not args.source:
        parser.print_help()
        sys.exit(1)

    source = args.source
    output_path = os.path.abspath(args.output)
    source_label = source

    print("==========================================================")
    print(" Zillow Property Valuation to Monarch Money Converter")
    print("==========================================================")

    # 1. Acquire raw content (from local file or Zillow API)
    content: str
    if os.path.isfile(source):
        source_label = f"Local File: {os.path.abspath(source)}"
        print(f"Source:           {source_label}")
        try:
            with open(source, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"\n❌ Failed to read input file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        source_label = f"Zillow Remote: {source}"
        print(f"Source:           {source_label}")
        print("🌐 Connecting to Zillow API...")
        try:
            content = fetch_zillow_history(source, cookie=args.cookie)
        except PerimeterXBlockedError as e:
            print(f"\n🛡️ {e}\n", file=sys.stderr)
            print("Zillow anti-bot protection blocked direct automated command-line access.", file=sys.stderr)
            print("You have two quick, reliable alternatives:\n", file=sys.stderr)
            print("  Option A (Recommended - 5 Seconds):", file=sys.stderr)
            print("    1. Open your Zillow property page in your browser.", file=sys.stderr)
            print("    2. Run 'zillow-to-monarch --snippet' and paste it into the DevTools Console (F12).", file=sys.stderr)
            print("    3. Pass the downloaded JSON file to this tool:\n", file=sys.stderr)
            print("       zillow-to-monarch ./zillow_valuation_<zpid>.json -p 2021-04-15\n", file=sys.stderr)
            print("  Option B (Pass Session Cookie):", file=sys.stderr)
            print("    Pass your browser's cookie header via '--cookie \"...\"' or 'export ZILLOW_COOKIE=\"...\"'.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Network error fetching from Zillow: {e}", file=sys.stderr)
            sys.exit(1)

    # 2. Parse valuation points and metadata
    try:
        raw_points, metadata = parse_source_content(content)
    except Exception as e:
        print(f"\n❌ Parsing failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Determine display name
    asset_label = args.asset_name or metadata.display_name

    # 3. Process into daily balances
    purchase_desc = (
        f"{args.purchase_date.strftime('%Y-%m-%d')} (Purchase Date)"
        if args.purchase_date
        else f"{raw_points[0].date.strftime('%Y-%m-%d')} (Beginning of Zillow records)"
    )

    print(f"Property / Asset: {asset_label}")
    print(f"Output file:      {output_path}")
    print(f"Start timeline:   {purchase_desc}")
    print(f"Interpolation:    {args.method}")
    print("----------------------------------------------------------")

    try:
        result = process_zillow_valuation(
            raw_points=raw_points,
            purchase_date=args.purchase_date,
            end_date=args.end_date,
            interpolation_method=args.method,
            property_metadata=metadata,
        )
    except Exception as e:
        print(f"\n❌ Processing failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ Successfully parsed {len(raw_points)} historical Zillow valuation points.")
    print(f"📅 Daily Date Range: {result.start_date} -> {result.end_date}")
    print(f"📈 Total Daily Balance Snapshots: {len(result.daily_balances)}")
    print(f"🏠 Starting Valuation: ${result.initial_value:,.2f}")
    print(
        f"🏡 Latest Valuation:   ${result.latest_value:,.2f} "
        f"({result.value_change:+,.2f} / {result.percent_change:+.2f}%)"
    )

    if result.warnings:
        print("\n⚠️ Notices:")
        for w in result.warnings:
            print(f"  - {w}")

    # 4. Export CSV
    try:
        exported_path = export_result(result, output_path)
    except Exception as e:
        print(f"\n❌ Export failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n----------------------------------------------------------")
    print(f"🎉 Export complete! Generated Monarch balance history file:")
    print(f"  {exported_path}")
    print("----------------------------------------------------------")
    print("Next Steps in Monarch Money (Web App):")
    print("  1. In Monarch, go to Accounts.")
    print("  2. Select your Real Estate Asset (or add one via '+ Add Account' -> 'Real Estate').")
    print("  3. Click 'Edit' in the top-right corner of the asset screen.")
    print("  4. Select 'Upload balance history'.")
    print(f"  5. Upload '{os.path.basename(exported_path)}'.")
    print("  6. Confirm the column mapping (Date & Balance) and finish import!")
    print("==========================================================")


if __name__ == "__main__":
    main()
