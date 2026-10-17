# Monarch Import from Zillow (`zillow-to-monarch`)

Generate continuous daily real estate asset balance history from Zillow for **Monarch Money**.

---

## 🎯 The Problem

When tracking real estate in [Monarch Money](https://www.monarchmoney.com/):
1. **Real estate assets are not accounts**: Unlike bank checking or credit card accounts, real estate assets in Monarch do not have transactions—they track net worth purely via **Account Balance History**.
2. **Aggregators and manual assets lack historical valuations**: When you add a real estate asset to Monarch, you typically get either today's single valuation or at best a couple of months of data. Monarch does not automatically pull years of historical appreciation.
3. **Without historical balance data, your net worth graph is distorted**: Past net worth curves will either look flat, show sudden artificial vertical spikes on the day you linked the house, or completely omit your home equity before linking.

Zillow maintains extensive historical valuation datasets (Zestimate history) spanning years or decades. This tool extracts that valuation data and produces:
- **`monarch_zillow_balance_history.csv`**: A continuous daily timeline with forward-filled or smoothly interpolated valuations for every single calendar day, giving you a smooth, accurate historical real estate net worth chart in Monarch Money.

---

## ✨ Features

- **Built Specifically for Real Estate Assets**: Only generates balance history (`Date,Balance`). No extraneous transaction files.
- **Purchase Date Support**:
  - Provide an optional `--purchase-date` / `-p` (`YYYY-MM-DD`) to start your asset's timeline on the exact day you acquired the home.
  - **Beginning-of-Time Default**: If no purchase date is provided, the timeline automatically defaults to the earliest available valuation record in Zillow's dataset.
- **Continuous Daily Balance History**: Generates daily balance snapshots (carrying forward or interpolating valuations across non-estimate days) to eliminate chart spikes and gaps in Monarch.
- **Configurable Timeline Interpolation**:
  - `forward-fill` (default): Step-wise progression where valuation stays constant until Zillow's next valuation date.
  - `linear`: Smooth daily linear interpolation between valuation dates for continuous net worth curves.
- **Anti-Bot & PerimeterX Resilient**:
  - Direct remote fetching via ZPID or Zillow URL (with optional session cookie support).
  - Built-in DevTools helper (`zillow-to-monarch --snippet`) to extract valuation JSON directly in your authenticated browser session in 5 seconds.
  - Accepts local files: saved JSON, webpage HTML, or existing CSV files.
- **100% Local & Private**: All data processing runs entirely on your local machine. No external services or accounts required.

---

## 🚀 Installation

### Requirements
- Python 3.8 or higher
- `requests>=2.25.0` (installed automatically)

### Install via git / pip
```bash
git clone https://github.com/dylanmtaylor/monarch-import-from-zillow.git
cd monarch-import-from-zillow
pip install .
```

Or install in editable/development mode:
```bash
pip install -e ".[dev]"
```

---

## 💻 Usage

### Quick Start with a Local Zillow Data Export (Recommended)

Because Zillow protects its platform with PerimeterX anti-bot challenges, the most reliable and fastest method is to run the 1-click DevTools snippet in your browser:

1. Open your property page on [Zillow.com](https://www.zillow.com/).
2. Run `zillow-to-monarch --snippet` and copy the JavaScript snippet:
   ```bash
   zillow-to-monarch --snippet
   ```
3. Open your browser console (`F12` or `Cmd+Option+I` -> **Console**), paste the snippet, and press **Enter**.
4. The snippet will automatically download `zillow_valuation_<zpid>.json`.
5. Run `zillow-to-monarch` pointing to your downloaded file:

```bash
# With purchase date (starts timeline on purchase date)
zillow-to-monarch ./zillow_valuation_12345678.json -p 2021-04-15

# Without purchase date (defaults to the beginning of time in Zillow records)
zillow-to-monarch ./zillow_valuation_12345678.json
```

### Direct Remote Fetching

You can also pass a Zillow URL or ZPID directly to the CLI:

```bash
zillow-to-monarch "https://www.zillow.com/homedetails/123-Main-St/12345678_zpid/" -p 2020-06-01
```

> **Note**: If Zillow's bot challenge blocks the automated curl/script request, pass your session cookie with `--cookie "<cookie_string>"` or use the DevTools snippet method above.

---

### Command-Line Options

```text
usage: zillow-to-monarch [-h] [-p PURCHASE_DATE] [-o OUTPUT]
                         [-m {forward-fill,linear}] [-e END_DATE]
                         [-a ASSET_NAME] [-c COOKIE] [--snippet]
                         [SOURCE]

positional arguments:
  SOURCE                Zillow URL, ZPID, or path to local JSON/HTML/CSV file.

options:
  -h, --help            Show this help message and exit.
  -p, --purchase-date   Date property was purchased (YYYY-MM-DD). If omitted,
                        defaults to the beginning of time in Zillow records.
  -o, --output          Destination path for Monarch balance history CSV
                        (default: ./output/monarch_zillow_balance_history.csv).
  -m, --method          Daily timeline method: 'forward-fill' (step-wise, default)
                        or 'linear' (smooth interpolation).
  -e, --end-date        End date for balance history (YYYY-MM-DD). Defaults to today.
  -a, --asset-name      Optional asset/property label for logs and preview in Monarch.
  -c, --cookie          Optional Zillow session cookie string for direct fetching.
  --snippet             Print the ready-to-use DevTools console snippet and exit.
```

---

### Example Output

```text
==========================================================
 Zillow Property Valuation to Monarch Money Converter
==========================================================
Source:           Local File: /home/user/Downloads/zillow_valuation_12345678.json
Property / Asset: 742 Evergreen Terrace - Springfield, OR
Output file:      /home/user/output/monarch_zillow_balance_history.csv
Start timeline:   2021-04-15 (Purchase Date)
Interpolation:    forward-fill
----------------------------------------------------------
✅ Successfully parsed 96 historical Zillow valuation points.
📅 Daily Date Range: 2021-04-15 -> 2026-10-17
📈 Total Daily Balance Snapshots: 2012
🏠 Starting Valuation: $425,000.00
🏡 Latest Valuation:   $582,400.00 (+$157,400.00 / +37.04%)
----------------------------------------------------------
🎉 Export complete! Generated Monarch balance history file:
  /home/user/output/monarch_zillow_balance_history.csv
----------------------------------------------------------
Next Steps in Monarch Money (Web App):
  1. In Monarch, go to Accounts.
  2. Select your Real Estate Asset (or add one via '+ Add Account' -> 'Real Estate').
  3. Click 'Edit' in the top-right corner of the asset screen.
  4. Select 'Upload balance history'.
  5. Upload 'monarch_zillow_balance_history.csv'.
  6. Confirm the column mapping (Date & Balance) and finish import!
==========================================================
```

---

## 📥 How to Import into Monarch Money

Balance history uploads must be performed on the **Monarch Money Web App** (desktop browser):

1. **Open Monarch Money** and navigate to **Accounts**.
2. **Select your Real Estate asset**:
   - If you haven't created it yet, click **"+ Add Account"** -> **"Real Estate"**, name it, and enter your current value.
3. Click the **"Edit"** button in the top-right corner of the asset page.
4. Select **"Upload balance history"** (or **"Import balance history"**).
5. Upload the generated CSV file (`monarch_zillow_balance_history.csv`).
6. Confirm the column mapping:
   - **Date** -> `Date`
   - **Balance** -> `Balance`
7. Preview the historical balance chart and click **Import**. Your Monarch net worth history will immediately update with the historical property values!

---

## 🧪 Testing

To run the comprehensive unit test suite:

```bash
python3 -m unittest discover -s tests -v
```

---

## 🔒 Security & Privacy

Financial assets and home addresses are sensitive personal data.
- The repository `.gitignore` automatically prevents all CSV, JSON, HTML, and output directories from being tracked.
- Test suites use strictly synthetic mock data.
- All timeline generation and CSV export happens locally on your computer with zero external data sharing.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
