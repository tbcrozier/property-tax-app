"""
Davidson County Property Scraper
---------------------------------
Three-step flow (no browser — pure HTTP):
  1. GET  /OFS/WP/Home                                     → session cookie
  2. POST /OFS/WP/PropertySearch/QuickPropertySearchAsync  → HTML with internal property ID
  3. POST /OFS/WP/PropertySearch/SelectAccount             → activates property in server session
  4. GET  /OFS/WP/Summary/{internal_id}/1/false            → HTML with beds/baths/sqft/etc.
  5. Write results to BigQuery table davidson_bed_bath (defined in infra/main.tf)

INSTALL:
    pip install -r requirements.txt

AUTHENTICATE WITH GCP:
    gcloud auth application-default login

TEST (single address, no BigQuery):
    python analysis/scraper.py

FULL RUN:
    Edit __main__ block at the bottom to call run_scraper() instead of test_one()
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config — update these before running
# ---------------------------------------------------------------------------
BQ_PROJECT = "public-data-dev"
BQ_SOURCE_TABLE = "property_tax.davidson_parcels"
BQ_DEST_TABLE = "property_tax.davidson_bed_bath"

PORTAL_BASE = "https://portal.padctn.org"
HOME_URL = PORTAL_BASE + "/OFS/WP/Home"
SEARCH_URL = PORTAL_BASE + "/OFS/WP/PropertySearch/QuickPropertySearchAsync"
SELECT_URL = PORTAL_BASE + "/OFS/WP/PropertySearch/SelectAccount"
SUMMARY_URL = PORTAL_BASE + "/OFS/WP/Summary/{internal_id}/1/false"

CONCURRENCY = 2       # parallel workers; increase if the server handles it
BATCH_SIZE = 500      # rows written to BigQuery at a time
RATE_LIMIT_DELAY = 4  # seconds between requests per worker

# ---------------------------------------------------------------------------
# Static DevExpress fields — same on every request (from DevTools Payload tab)
# ---------------------------------------------------------------------------
_DXSCRIPT = (
    "1_9,1_10,1_253,1_21,1_0,1_1,1_2,1_3,1_62,1_11,1_12,1_13,1_14,1_18,1_181,"
    "1_182,1_183,1_19,1_20,17_0,1_180,17_24,1_203,17_25,1_192,17_18,1_201,17_20,"
    "1_186,1_188,1_196,1_15,1_39,1_197,1_198,1_202,1_184,1_191,17_17,17_22,1_190,"
    "17_19,1_59,1_193,1_187,17_16,1_195,1_38,1_189,17_43,1_200,1_194,17_21,4_0,"
    "1_16,5_1,5_2,4_115,4_98,4_100,4_99,4_101,4_102,4_105,4_108,4_109,4_107,4_106,"
    "4_104,4_103,4_110,4_1,4_34,4_113,4_3,4_31,4_2,4_24,4_22,4_23,4_27,4_28,4_32,"
    "4_29,4_35,4_47,4_48,4_42,4_80,4_36,4_37,4_38,4_39,4_40,4_43,4_44,4_45,4_46,"
    "4_49,4_50,4_51,4_52,4_41,4_53,4_54,4_55,4_56,4_57,4_58,4_59,4_60,4_61,4_62,"
    "4_67,4_68,4_69,4_70,4_71,4_72,4_73,4_74,4_75,4_76,4_77,4_63,4_64,4_65,4_66,"
    "4_78,4_79,4_86,4_87,4_89,4_93,4_88,4_90,4_91,4_81,4_84,4_83,4_85,4_82,4_15,"
    "4_16,4_17,4_18,4_19,4_20,4_92,4_25,4_26,4_30,4_14,4_6,4_8,4_7,4_9,4_10,4_11,"
    "4_21,4_12,4_4,4_5,4_13,17_4,4_94,1_22,1_31,4_95,4_96,4_97,1_41,4_33,1_58,"
    "1_32,17_12,1_17,1_211,1_224,1_225,1_226,1_210,1_218,1_214,1_219,1_220,1_215,"
    "1_221,1_216,1_217,1_212,1_222,1_223,1_209,1_228,1_237,1_239,1_240,1_227,1_232,"
    "1_233,1_234,1_213,1_229,1_230,1_231,1_235,1_236,1_238,1_241,17_49,17_50,17_2,"
    "1_37,17_9,1_251,17_1,1_4,24_364,24_365,24_366,24_367,24_359,24_362,24_363,"
    "24_360,24_361,24_368,24_479,24_480,26_19,26_21,24_440,24_441,26_23,26_20,26_22,"
    "17_27,26_24,17_28,26_11,26_16,26_18,17_26,1_49,26_15,26_13,26_14,26_12,26_17,"
    "1_46,1_7,1_44,1_29,17_36"
)
_DXCSS = (
    "1_208,1_205,1_66,1_207,1_204,1_72,1_71,4_118,4_120,4_111,4_112,4_116,4_121,"
    "5_4,5_3,1_255,1_254,1_82,24_378,24_379,24_414,24_485,24_487,24_442,24_443,"
    "24_478,26_37,26_36,26_35,26_32,26_34,26_30,26_28,26_31,1_74"
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class PropertyResult:
    parcel_id: str
    address: str
    internal_id: str | None = None
    beds: int | None = None
    baths: int | None = None
    half_baths: int | None = None
    year_built: int | None = None
    square_footage: int | None = None
    property_type: str | None = None
    error: str | None = None
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------
def _base_headers(session_id: str, csrf_token: str) -> dict:
    return {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": PORTAL_BASE,
        "Referer": HOME_URL,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        "Cookie": (
            f"ASP.NET_SessionId={session_id}; "
            f"__RequestVerificationToken_L09GUw2={csrf_token}"
        ),
    }


async def establish_session(client: httpx.AsyncClient) -> tuple[str, str]:
    """GET home page to pick up the ASP.NET session cookie and CSRF token."""
    resp = await client.get(HOME_URL)
    resp.raise_for_status()

    session_id = client.cookies.get("ASP.NET_SessionId", "")
    csrf = client.cookies.get("__RequestVerificationToken_L09GUw2", "")

    if not csrf:
        soup = BeautifulSoup(resp.text, "lxml")
        tag = soup.find("input", {"name": "__RequestVerificationToken"})
        csrf = tag["value"] if tag else ""

    if not session_id:
        raise RuntimeError("Could not get ASP.NET session cookie — home page structure may have changed")

    log.info("Session established (id prefix: %s...)", session_id[:8])
    return session_id, csrf


# ---------------------------------------------------------------------------
# Step 1: Search → internal property ID
# ---------------------------------------------------------------------------
def _build_search_payload(house_number: str, street_name: str) -> dict:
    """
    Build the POST body for QuickPropertySearchAsync.

    SelectedSearch=2 means address mode.
    SingleSearchCriteria gets a trailing space (observed in real requests).
    """
    return {
        "RealEstate": "true",
        "SelectedSearch": "2",
        "StreetNumber": house_number.strip(),
        "AlterCriteria": "False",
        "SingleSearchCriteria": street_name.strip() + " ",
        "DXScript": _DXSCRIPT,
        "DXCss": _DXCSS,
    }


def _parse_internal_id(html: str) -> str | None:
    """Extract the first internal property ID from search results HTML."""
    # Pattern 1: onclick="SelectAccount('172535', ...)" or SelectAccount(172535, ...)
    m = re.search(r"SelectAccount\s*\(\s*['\"]?(\d+)['\"]?", html)
    if m:
        return m.group(1)

    # Pattern 2: href pointing to /OFS/WP/Summary/172535
    m = re.search(r"/OFS/WP/Summary/(\d+)", html)
    if m:
        return m.group(1)

    return None


async def quick_search(
    client: httpx.AsyncClient,
    house_number: str,
    street_name: str,
    headers: dict,
) -> str | None:
    """POST search, return internal property ID or None if not found."""
    payload = _build_search_payload(house_number, street_name)
    search_str = f"{house_number} {street_name}"
    params = {"Length": len(search_str.strip()) + 1}  # +1 for trailing space on street name
    resp = await client.post(SEARCH_URL, data=payload, params=params, headers=headers)
    resp.raise_for_status()
    return _parse_internal_id(resp.text)


# ---------------------------------------------------------------------------
# Step 2: SelectAccount — tells the server which property is active
# ---------------------------------------------------------------------------
async def select_account(
    client: httpx.AsyncClient,
    internal_id: str,
    headers: dict,
) -> None:
    """POST account selection so the server session is scoped to this property."""
    resp = await client.post(
        SELECT_URL,
        data={"account": internal_id, "isPersonalProperty": "false"},
        headers=headers,
    )
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Step 3: Fetch and parse Summary HTML
# ---------------------------------------------------------------------------
def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"\d+", text.strip())
    return int(m.group()) if m else None


def parse_summary_html(html: str) -> dict:
    """
    Extract property attributes from /OFS/WP/Summary HTML.

    The portal renders fields as:
        <li><label class="font-weight-bold" for="Number_of_Beds:">Number of Beds:</label> 2</li>

    Value is the NavigableString immediately after the closing </label> tag.
    """
    soup = BeautifulSoup(html, "lxml")
    fields: dict = {}

    label_map = {
        "Number of Beds":       "beds",
        "Number of Baths":      "baths",
        "Number of Half Baths": "half_baths",
        "Year Built":           "year_built",
        "Square Footage":       "square_footage",
        "Property Type":        "property_type",
    }

    for label_tag in soup.find_all("label", class_="font-weight-bold"):
        key = label_tag.get_text(strip=True).rstrip(":")
        if key in label_map:
            value_node = label_tag.next_sibling
            value = str(value_node).strip() if value_node else None
            fields[label_map[key]] = value

    if not fields:
        log.warning("parse_summary_html: no fields matched. HTML snippet:\n%s", html[:400])

    return fields


async def fetch_summary(
    client: httpx.AsyncClient,
    internal_id: str,
    headers: dict,
) -> dict:
    get_headers = {**headers, "Accept": "text/html, */*; q=0.01"}
    resp = await client.get(SUMMARY_URL.format(internal_id=internal_id), headers=get_headers)
    resp.raise_for_status()
    return parse_summary_html(resp.text)


# ---------------------------------------------------------------------------
# Per-parcel orchestration
# ---------------------------------------------------------------------------
async def scrape_parcel(
    client: httpx.AsyncClient,
    parcel: dict,
    headers: dict,
) -> PropertyResult:
    result = PropertyResult(parcel_id=parcel["parcel_id"], address=parcel["address"])
    try:
        internal_id = await quick_search(
            client, parcel["house_number"], parcel["street_name"], headers
        )
        if not internal_id:
            result.error = "no search result found for address"
            return result

        result.internal_id = internal_id
        await select_account(client, internal_id, headers)
        details = await fetch_summary(client, internal_id, headers)

        result.beds = _parse_int(details.get("beds"))
        result.baths = _parse_int(details.get("baths"))
        result.half_baths = _parse_int(details.get("half_baths"))
        result.year_built = _parse_int(details.get("year_built"))
        result.square_footage = _parse_int(details.get("square_footage"))
        result.property_type = details.get("property_type")

    except Exception as e:
        result.error = str(e)
        log.warning("Failed %s: %s", parcel["parcel_id"], e)

    await asyncio.sleep(RATE_LIMIT_DELAY)
    return result


# ---------------------------------------------------------------------------
# BigQuery
# ---------------------------------------------------------------------------
def load_parcels_from_bq(client: bigquery.Client, limit: int | None = None) -> list[dict]:
    """
    Read parcels from davidson_parcels. We pull PropHouse and PropStreet
    separately so we never have to split the address string ourselves.
    """
    limit_clause = f"LIMIT {limit}" if limit else ""
    query = f"""
        SELECT
            ParID       AS parcel_id,
            PropAddr    AS address,
            PropHouse   AS house_number,
            PropStreet  AS street_name
        FROM `{BQ_PROJECT}.{BQ_SOURCE_TABLE}`
        WHERE PropHouse IS NOT NULL AND PropStreet IS NOT NULL
        {limit_clause}
    """
    log.info("Loading parcels from BigQuery...")
    rows = list(client.query(query).result())
    log.info("Loaded %d parcels", len(rows))
    return [dict(r) for r in rows]


def write_results_to_bq(client: bigquery.Client, results: list[PropertyResult]) -> None:
    if not results:
        return
    rows = [
        {
            "parcel_id":      r.parcel_id,
            "address":        r.address,
            "internal_id":    r.internal_id,
            "beds":           r.beds,
            "baths":          r.baths,
            "half_baths":     r.half_baths,
            "year_built":     r.year_built,
            "square_footage": r.square_footage,
            "property_type":  r.property_type,
            "error":          r.error,
            "scraped_at":     r.scraped_at,
        }
        for r in results
    ]
    errors = client.insert_rows_json(f"{BQ_PROJECT}.{BQ_DEST_TABLE}", rows)
    if errors:
        log.error("BigQuery insert errors: %s", errors)
    else:
        log.info("Wrote %d rows to BigQuery", len(rows))


# ---------------------------------------------------------------------------
# Worker pool
# ---------------------------------------------------------------------------
async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    results: list[PropertyResult],
    session_id: str,
    csrf_token: str,
) -> None:
    headers = _base_headers(session_id, csrf_token)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        while True:
            parcel = await queue.get()
            if parcel is None:
                queue.task_done()
                break
            log.info("[w%d] %s", worker_id, parcel["parcel_id"])
            result = await scrape_parcel(client, parcel, headers)
            results.append(result)
            queue.task_done()


# ---------------------------------------------------------------------------
# Manual smoke test — no BigQuery needed
# ---------------------------------------------------------------------------
async def test_one(house_number: str = "1236", street_name: str = "LAKEWALK") -> None:
    """
    Test a single address without touching BigQuery.
    Run: python analysis/scraper.py
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        session_id, csrf_token = await establish_session(client)
        headers = _base_headers(session_id, csrf_token)
        parcel = {
            "parcel_id":   "TEST",
            "address":     f"{house_number} {street_name} RD NASHVILLE",
            "house_number": house_number,
            "street_name":  street_name,
        }
        result = await scrape_parcel(client, parcel, headers)
        print(result)


# ---------------------------------------------------------------------------
# Full BigQuery run
# ---------------------------------------------------------------------------
async def run_scraper(limit: int | None = None) -> None:
    bq_client = bigquery.Client(project=BQ_PROJECT)
    parcels = load_parcels_from_bq(bq_client, limit=limit)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as init_client:
        session_id, csrf_token = await establish_session(init_client)

    queue: asyncio.Queue = asyncio.Queue()
    for p in parcels:
        await queue.put(p)
    for _ in range(CONCURRENCY):
        await queue.put(None)  # poison pills to stop workers

    results: list[PropertyResult] = []
    await asyncio.gather(*[
        asyncio.create_task(worker(i, queue, results, session_id, csrf_token))
        for i in range(CONCURRENCY)
    ])

    for i in range(0, len(results), BATCH_SIZE):
        write_results_to_bq(bq_client, results[i : i + BATCH_SIZE])

    ok = sum(1 for r in results if r.error is None)
    log.info("Done. %d/%d succeeded.", ok, len(results))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # --- Smoke test (no BigQuery) ---
    asyncio.run(test_one("1236", "LAKEWALK"))

    # --- Small batch from BigQuery (uncomment to use) ---
    # asyncio.run(run_scraper(limit=5))

    # --- Full 200K run (uncomment when ready) ---
    # asyncio.run(run_scraper())
