"""DevTools console snippet generator for direct in-browser Zestimate extraction."""

SNIPPET_JS = r"""
(async function extractZillowHistory() {
  console.log("🔍 Extracting Zillow Valuation History...");

  // 1. Determine ZPID from URL or page context
  const urlMatch = window.location.href.match(/(\d+)_zpid/);
  const zpid = urlMatch ? parseInt(urlMatch[1], 10) : null;

  if (!zpid) {
    console.error("❌ Could not determine ZPID from URL. Ensure you are on a Zillow property details page.");
    return;
  }

  console.log(`📌 Found ZPID: ${zpid}. Querying HomeValueChartDataQuery...`);

  // 2. Query Zillow's internal GraphQL API using current authenticated browser session
  const payload = {
    operationName: "HomeValueChartDataQuery",
    variables: {
      zpid: zpid,
      timePeriod: "TEN_YEARS",
      metricType: "LOCAL_HOME_VALUES",
      forecast: true
    },
    query: "query HomeValueChartDataQuery($zpid: ID!, $metricType: HomeValueChartMetricType, $timePeriod: HomeValueChartTimePeriod) { property(zpid: $zpid) { homeValueChartData(metricType: $metricType, timePeriod: $timePeriod) { points { x y } name } } }"
  };

  try {
    const response = await fetch("https://www.zillow.com/graphql/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "client-id": "hdp-react-web-client"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`HTTP error status ${response.status}`);
    }

    const data = await response.json();
    const chart = data?.data?.property?.homeValueChartData;
    const homeSeries = Array.isArray(chart) ? chart.find(s => s.name === "This home") || chart[0] : null;

    if (!homeSeries || !homeSeries.points || homeSeries.points.length === 0) {
      console.warn("⚠️ No chart points returned. Checking fallback in page context...");
      if (typeof homeValueChartData !== "undefined") {
        downloadJson({ homeValueChartData: homeValueChartData, zpid: zpid }, `zillow_${zpid}_chart.json`);
        return;
      }
      throw new Error("No valuation history returned.");
    }

    console.log(`✅ Successfully extracted ${homeSeries.points.length} historical valuation points!`);

    // Download JSON file
    downloadJson(data, `zillow_valuation_${zpid}.json`);
    console.log("🎉 Downloaded valuation file! You can now run:");
    console.log(`   zillow-to-monarch zillow_valuation_${zpid}.json`);

  } catch (err) {
    console.error("❌ Extraction failed:", err);
    console.info("💡 Fallback: Save this entire webpage (Ctrl+S / Cmd+S -> Webpage, Complete) and pass the HTML to zillow-to-monarch.");
  }

  function downloadJson(obj, filename) {
    const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  }
})();
"""


def get_browser_snippet() -> str:
    """Return the ready-to-run DevTools console JavaScript snippet."""
    return SNIPPET_JS.strip()
