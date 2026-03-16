"""FastAPI application - AI-Orbit Intelligence 3D (Sprint 10 - Production).

Unified backend with lifespan-based automatic pipeline.
Sprint 8:  SATCAT enrichment (owner, object_type), strategic OSINT filters.
Sprint 9:  Added mean_motion & inclination to SatellitePosition for
           client-side orbital animation.
Sprint 10: Cloud-ready launcher, Dockerfile, CI/CD, tests.
Sprint 11: Robust cloud data fetching — User-Agent headers, cache fallback,
           graceful degradation (no crash on network failure).
           No manual POST /api/v1/analyse needed.
Sprint 12: Fix OSINT object_type filtering — CelesTrak uses abbreviated
           codes (PAY, DEB, R/B, UNK) which must be normalised to full
           names (PAYLOAD, DEBRIS, ROCKET BODY, UNKNOWN) to match the
           frontend dropdown values.  Case-insensitive owner comparison.
Sprint 13: Fix debris at zero — TLE source was GROUP=active only (no debris).
           Now downloads active + Fengyun-1C + Iridium-33 debris TLE groups
           and merges them so the SATCAT inner-join keeps debris objects.
"""

import json
import logging
import math
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from skyfield.api import EarthSatellite, load, wgs84

from orbit_intel.anomaly import OrbitalAnomalyDetector
from orbit_intel.dynamics import extract_features, load_tle_objects
from orbit_intel.ingest import fetch_tle_data

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ---------------------------------------------------------------------------
# Sprint 11: Absolute paths — works regardless of Docker WORKDIR
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent      # .../app/
PROJECT_ROOT: Path = BASE_DIR.parent                  # .../ai-orbit-intel-3d/
DEFAULT_DATA_DIR: Path = PROJECT_ROOT / "data"        # Ensure the data directory exists at import time (Docker, HF, local, CI)
DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)

ts = load.timescale()

# ---------------------------------------------------------------------------
# Sprint 11: Shared HTTP configuration for CelesTrak requests
# ---------------------------------------------------------------------------
HTTP_USER_AGENT: str = (
    "AI-Orbit-Intel-App/1.0 "
    "(https://github.com/thierrymaesen/ai-orbit-intel-3d)"
)
HTTP_HEADERS: Dict[str, str] = {
    "User-Agent": HTTP_USER_AGENT,
    "Accept": "application/json, text/plain, */*",
}
HTTP_TIMEOUT: float = 60.0  # generous timeout for cloud cold-starts

# ---------------------------------------------------------------------------
# Sprint 12 fix: Use ONORBIT query instead of GROUP=active so that the
# SATCAT includes debris, rocket bodies, and unknown objects — not just
# active payloads.
# ---------------------------------------------------------------------------
SATCAT_URL: str = (
    "https://celestrak.org/satcat/records.php?SATCAT_STATUS=onorbit&FORMAT=json"
)

# ---------------------------------------------------------------------------
# Sprint 13 fix: Multiple TLE sources to include debris objects.
# GROUP=active only contains operational payloads — no debris.
# We now download additional debris groups and merge them.
# ---------------------------------------------------------------------------
CELESTRAK_TLE_URLS: List[str] = [
    # 1) Active (operational) satellites
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
    # 2) Fengyun-1C debris (2007 Chinese ASAT test — ~3,400 tracked pieces)
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=1999-025&FORMAT=tle",
    # 3) Iridium-33 / Cosmos-2251 collision debris (~2,000 tracked pieces)
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-33-debris&FORMAT=tle",
    # 4) Cosmos-2251 debris
    "https://celestrak.org/NORAD/elements/gp.php?GROUP=cosmos-2251-debris&FORMAT=tle",
]

TLE_FILENAME: str = "active_satellites.txt"
SATCAT_CACHE_FILE: str = "satcat_cache.json"

# ---------------------------------------------------------------------------
# Sprint 12 fix: CelesTrak SATCAT uses abbreviated OBJECT_TYPE codes.
# The frontend <select> sends full names.  This map normalises abbreviations
# to the full names expected by the UI.
# ---------------------------------------------------------------------------
SATCAT_TYPE_MAP: Dict[str, str] = {
    "PAY": "PAYLOAD",
    "DEB": "DEBRIS",
    "R/B": "ROCKET BODY",
    "UNK": "UNKNOWN",
    "TBA": "TBA",
    # Full names map to themselves (in case CelesTrak ever changes format)
    "PAYLOAD": "PAYLOAD",
    "DEBRIS": "DEBRIS",
    "ROCKET BODY": "ROCKET BODY",
    "UNKNOWN": "UNKNOWN",
}

_state: Dict[str, Any] = {
    "satellites_tle": [],
    "df_anomalies": None,
    "detector": None,
    "last_report": None,
    "satcat_lookup": {},
    "tle_extra_lookup": {},    # Sprint 9: mean_motion & inclination from TLE
}


def classify_orbit(alt_km: float) -> str:
    if alt_km < 2000:
        return "LEO"
    if alt_km > 35000:
        return "GEO"
    return "MEO"


# ----------------------------------------------------------------
# Sprint 9: Extract mean_motion & inclination from TLE/SGP4 model
# ----------------------------------------------------------------
def build_tle_extra_lookup(
    sats: List[EarthSatellite],
) -> Dict[int, Dict[str, float]]:
    """Extract mean_motion (revs/day) and inclination (degrees) directly
    from the SGP4 TLE model for each satellite."""
    lookup: Dict[int, Dict[str, float]] = {}
    for sat in sats:
        norad_id = sat.model.satnum
        try:
            mean_motion_revs_day = (
                sat.model.no_kozai * 1440.0 / (2.0 * math.pi)
            )
            inclination_deg = math.degrees(sat.model.inclo)
        except Exception:
            mean_motion_revs_day = 0.0
            inclination_deg = 0.0
        lookup[norad_id] = {
            "mean_motion": round(mean_motion_revs_day, 6),
            "inclination": round(inclination_deg, 4),
        }
    return lookup


# ---------------------------------------------------------------------------
# Sprint 12 helper: normalise a raw OBJECT_TYPE from CelesTrak
# ---------------------------------------------------------------------------
def normalise_object_type(raw: str) -> str:
    """Map CelesTrak abbreviated OBJECT_TYPE codes to full names.

    Examples:  'PAY' -> 'PAYLOAD'
               'DEB' -> 'DEBRIS'
               'R/B' -> 'ROCKET BODY'
               'UNK' -> 'UNKNOWN'
    """
    cleaned = raw.strip().upper()
    # Exact match first via lookup table
    mapped = SATCAT_TYPE_MAP.get(cleaned)
    if mapped:
        return mapped
    # Aggressive substring matching for variants
    if "DEB" in cleaned:
        return "DEBRIS"
    if "R/B" in cleaned or "ROCKET" in cleaned:
        return "ROCKET BODY"
    if "PAY" in cleaned:
        return "PAYLOAD"
    return cleaned


# ----------------------------------------------------------------
# Pydantic models
# ----------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    version: str = Field(..., examples=["1.3.0"])
    satellites_loaded: int = Field(..., examples=[14000])
    anomalies_detected: int = Field(..., examples=[700])


class SatellitePosition(BaseModel):
    name: str = Field(..., examples=["ISS (ZARYA)"])
    norad_id: int = Field(..., examples=[25544])
    lat: float = Field(..., examples=[51.64])
    lon: float = Field(..., examples=[0.12])
    alt: float = Field(..., examples=[408.0])
    orbit_type: str = Field(..., examples=["LEO"])
    anomaly_score: float = Field(
        ..., ge=0.0, le=1.0, examples=[0.12]
    )
    is_anomaly: bool = Field(..., examples=[False])
    owner: str = Field("UNKNOWN", examples=["US"])
    object_type: str = Field("UNKNOWN", examples=["PAYLOAD"])
    # Sprint 9: orbital dynamics for client-side animation
    mean_motion: float = Field(
        0.0,
        examples=[15.49],
        description="Mean motion in revolutions per day (from TLE).",
    )
    inclination: float = Field(
        0.0,
        examples=[51.6442],
        description="Orbital inclination in degrees (from TLE).",
    )


class PositionsResponse(BaseModel):
    timestamp: float = Field(..., examples=[1709136000.0])
    total_satellites: int = Field(..., examples=[10000])
    satellites: List[SatellitePosition]


class SatelliteAnomaly(BaseModel):
    name: str = Field(..., examples=["ISS (ZARYA)"])
    norad_id: int = Field(..., examples=[25544])
    inclination: float = Field(..., examples=[0.9013])
    eccentricity: float = Field(..., examples=[0.0001])
    mean_motion: float = Field(..., examples=[0.0634])
    bstar: float = Field(..., examples=[0.0001])
    is_anomaly: bool = Field(..., examples=[False])
    anomaly_score: float = Field(
        ..., ge=0.0, le=1.0, examples=[0.12]
    )


class AnomalyReport(BaseModel):
    total_satellites: int = Field(..., examples=[9000])
    total_anomalies: int = Field(..., examples=[450])
    contamination_rate: float = Field(..., examples=[0.05])
    satellites: List[SatelliteAnomaly]


class IngestResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    file_path: str = Field(..., examples=["data/active_satellites.txt"])
    satellite_count: int = Field(..., examples=[9000])


# --------------------------------------------------------------------------
# Sprint 13: Robust multi-source TLE download with merge, User-Agent,
# retry, and cache fallback.
# --------------------------------------------------------------------------
def download_tle_robust(data_dir: Path) -> Path:
    """Download TLE data from multiple CelesTrak groups and merge them.

    Sprint 13 fix: Instead of only GROUP=active (which contains zero debris),
    we now iterate over CELESTRAK_TLE_URLS (active + major debris groups)
    and concatenate all TLE text into a single file.

    Strategy:
      1. For each URL in CELESTRAK_TLE_URLS, download TLE text with a
         professional User-Agent header.
      2. Concatenate all successful responses into one combined TLE file.
      3. On ANY individual failure, log a warning but continue with the
         other sources.
      4. If ALL downloads fail, fall back to the existing cached file.
      5. If no cache exists either, raise FileNotFoundError.

    Returns:
        Path to the merged TLE file (freshly downloaded or cached).

    Raises:
        FileNotFoundError: No live data AND no cached file available.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    final_path: Path = data_dir / TLE_FILENAME

    # --- Attempt live downloads from all TLE sources ---
    all_tle_lines: List[str] = []
    seen_norad_ids: set = set()
    success_count: int = 0

    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT,
            headers=HTTP_HEADERS,
            follow_redirects=True,
        ) as client:
            for url in CELESTRAK_TLE_URLS:
                try:
                    logger.info("Downloading TLE from: %s", url)
                    resp = client.get(url)
                    resp.raise_for_status()
                    content = resp.text.strip()

                    if not content or len(content) < 50:
                        logger.warning(
                            "Empty/short response from %s -- skipping.", url
                        )
                        continue

                    # De-duplicate: parse TLE triplets and skip if NORAD ID
                    # already seen (a satellite could appear in two groups).
                    lines = content.splitlines()
                    i = 0
                    new_lines_count = 0
                    while i + 2 < len(lines):
                        line0 = lines[i].strip()
                        line1 = lines[i + 1].strip()
                        line2 = lines[i + 2].strip()

                        # Basic TLE triplet validation
                        if line1.startswith("1 ") and line2.startswith("2 "):
                            try:
                                norad_id = int(line1[2:7].strip())
                            except (ValueError, IndexError):
                                norad_id = None

                            if norad_id and norad_id not in seen_norad_ids:
                                seen_norad_ids.add(norad_id)
                                all_tle_lines.append(line0)
                                all_tle_lines.append(line1)
                                all_tle_lines.append(line2)
                                new_lines_count += 1
                            i += 3
                        else:
                            # Skip malformed line and try next
                            i += 1

                    logger.info(
                        "  -> %d new objects from %s (skipped %d duplicates).",
                        new_lines_count,
                        url.split("GROUP=")[1].split("&")[0] if "GROUP=" in url else url,
                        (len(lines) // 3) - new_lines_count,
                    )
                    success_count += 1

                except Exception as url_exc:
                    logger.warning(
                        "TLE download FAILED for %s: %s -- continuing with other sources.",
                        url,
                        url_exc,
                    )

    except Exception as exc:
        logger.warning(
            "HTTP client error during TLE downloads: %s", exc
        )

    # --- Write merged TLE file ---
    if all_tle_lines:
        merged_content = "\n".join(all_tle_lines) + "\n"
        tmp_path = final_path.with_suffix(".tmp")
        tmp_path.write_text(merged_content, encoding="utf-8")
        tmp_path.replace(final_path)
        total_objects = len(all_tle_lines) // 3
        logger.info(
            "TLE data merged & saved: %s (%d objects from %d sources, %d bytes)",
            final_path,
            total_objects,
            success_count,
            len(merged_content),
        )
        return final_path

    # --- Fallback: use cached file ---
    logger.warning("ALL TLE downloads failed -- checking local cache...")
    if final_path.exists() and final_path.stat().st_size > 100:
        age_hours = (time.time() - final_path.stat().st_mtime) / 3600
        logger.warning(
            "Using CACHED TLE file: %s (age: %.1f hours)",
            final_path,
            age_hours,
        )
        return final_path

    # --- No data at all ---
    raise FileNotFoundError(
        f"TLE download failed and no cached file found at {final_path}. "
        "The application will start with 0 satellites."
    )


# --------------------------------------------------------------------------
# Sprint 11 + Sprint 12 fix: Robust SATCAT download with normalisation
# --------------------------------------------------------------------------
def _parse_satcat_records(records: list) -> Dict[int, Dict[str, str]]:
    """Parse a list of CelesTrak SATCAT JSON records into a lookup dict.

    Sprint 12: normalises OBJECT_TYPE abbreviations (PAY -> PAYLOAD, etc.)
    so that the frontend dropdown values match.
    """
    lookup: Dict[int, Dict[str, str]] = {}
    for rec in records:
        norad_id = rec.get("NORAD_CAT_ID")
        if norad_id is None:
            continue
        try:
            norad_id = int(norad_id)
        except (ValueError, TypeError):
            continue
        owner = rec.get("OWNER", "UNKNOWN") or "UNKNOWN"
        obj_type_raw = rec.get("OBJECT_TYPE", "UNKNOWN") or "UNKNOWN"
        lookup[norad_id] = {
            "owner": owner.strip(),
            "object_type": normalise_object_type(obj_type_raw),
        }
    return lookup


def fetch_satcat(data_dir: Path) -> Dict[int, Dict[str, str]]:
    """Download SATCAT JSON from CelesTrak with proper headers.

    Falls back to a local JSON cache if the live download fails.
    Returns an empty dict (never crashes) if both fail.
    """
    logger.info("Downloading SATCAT from %s ...", SATCAT_URL)
    cache_path: Path = data_dir / SATCAT_CACHE_FILE
    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT,
            headers=HTTP_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = client.get(SATCAT_URL)
            resp.raise_for_status()
            records = resp.json()

        lookup = _parse_satcat_records(records)
        logger.info("SATCAT loaded: %d records.", len(lookup))

        # Log unique object types for debugging
        unique_types = set(v["object_type"] for v in lookup.values())
        logger.info("SATCAT unique object_types (normalised): %s", unique_types)

        # Persist cache for future fallback
        try:
            cache_path.write_text(
                json.dumps(records, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("SATCAT cache saved to %s", cache_path)
        except Exception as cache_exc:
            logger.warning("Could not save SATCAT cache: %s", cache_exc)

        return lookup

    except Exception as exc:
        logger.warning(
            "Live SATCAT download FAILED: %s -- checking cache...",
            exc,
        )
        # --- Fallback: local cache ---
        if cache_path.exists():
            try:
                records = json.loads(cache_path.read_text(encoding="utf-8"))
                lookup = _parse_satcat_records(records)
                logger.warning(
                    "Using CACHED SATCAT: %d records from %s",
                    len(lookup),
                    cache_path,
                )
                return lookup
            except Exception as cache_exc:
                logger.error("SATCAT cache read failed: %s", cache_exc)

        logger.error(
            "SATCAT unavailable (no live data, no cache). "
            "Owner/object_type will show UNKNOWN."
        )
        return {}


# --------------------------------------------------------------------------
# Sprint 11: Robust Lifespan -- never crashes, graceful degradation
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("=" * 60)
    logger.info("AI-Orbit Intelligence 3D - Initializing...")
    logger.info("Data directory: %s", DEFAULT_DATA_DIR)
    logger.info("=" * 60)
    try:
        # --- Step 1: Download / load TLE data ---
        logger.info("[1/5] Downloading TLE satellite catalogue (multi-source)...")
        try:
            download_tle_robust(data_dir=DEFAULT_DATA_DIR)
        except FileNotFoundError as tle_exc:
            logger.error("TLE download + cache miss: %s", tle_exc)

        # Try loading whatever file we have (fresh or cached)
        try:
            sats = load_tle_objects(data_dir=DEFAULT_DATA_DIR)
            logger.info("Loaded %d satellites from TLE file.", len(sats))
        except FileNotFoundError:
            logger.error(
                "No TLE file available at all. "
                "Starting with 0 satellites -- UI will display an empty globe."
            )
            sats = []
        _state["satellites_tle"] = sats

        # --- Step 2: Download / load SATCAT ---
        logger.info("[2/5] Downloading SATCAT (owner & object type)...")
        _state["satcat_lookup"] = fetch_satcat(data_dir=DEFAULT_DATA_DIR)

        # --- Sprint 13: Log debris / rocket body counts for verification ---
        satcat = _state["satcat_lookup"]
        debris_in_satcat = sum(
            1 for v in satcat.values() if v["object_type"] == "DEBRIS"
        )
        rb_in_satcat = sum(
            1 for v in satcat.values() if v["object_type"] == "ROCKET BODY"
        )
        tle_norad_ids = {sat.model.satnum for sat in sats}
        debris_with_tle = sum(
            1
            for nid in tle_norad_ids
            if satcat.get(nid, {}).get("object_type") == "DEBRIS"
        )
        rb_with_tle = sum(
            1
            for nid in tle_norad_ids
            if satcat.get(nid, {}).get("object_type") == "ROCKET BODY"
        )
        logger.info(
            "SATCAT breakdown: %d DEBRIS total, %d ROCKET BODY total.",
            debris_in_satcat,
            rb_in_satcat,
        )
        logger.info(
            "TLE+SATCAT intersection: %d DEBRIS with TLE, %d ROCKET BODY with TLE.",
            debris_with_tle,
            rb_with_tle,
        )

        # --- Step 3: Build TLE extra lookup ---
        logger.info(
            "[3/5] Building TLE extra lookup (mean_motion & inclination)..."
        )
        _state["tle_extra_lookup"] = build_tle_extra_lookup(sats)
        logger.info(
            "TLE extra lookup built: %d entries.",
            len(_state["tle_extra_lookup"]),
        )

        # --- Steps 4 & 5: Feature extraction + ML (only if we have data) ---
        if sats:
            logger.info("[4/5] Extracting orbital features...")
            df = extract_features(sats)

            logger.info("[5/5] Training Isolation Forest...")
            detector = OrbitalAnomalyDetector(contamination=0.05)
            df_anomalies = detector.fit_predict(df)
            _state["df_anomalies"] = df_anomalies
            _state["detector"] = detector

            n_anomalies = int(df_anomalies["is_anomaly"].sum())
            records: List[SatelliteAnomaly] = []
            for norad_id, row in df_anomalies.iterrows():
                records.append(
                    SatelliteAnomaly(
                        name=row["name"],
                        norad_id=int(norad_id),
                        inclination=round(
                            float(row["inclination"]), 6
                        ),
                        eccentricity=round(
                            float(row["eccentricity"]), 6
                        ),
                        mean_motion=round(
                            float(row["mean_motion"]), 6
                        ),
                        bstar=float(row["bstar"]),
                        is_anomaly=bool(row["is_anomaly"]),
                        anomaly_score=round(
                            float(row["anomaly_score"]), 4
                        ),
                    )
                )
            _state["last_report"] = AnomalyReport(
                total_satellites=len(df_anomalies),
                total_anomalies=n_anomalies,
                contamination_rate=0.05,
                satellites=records,
            )
            logger.info(
                "READY: %d satellites, %d anomalies, SATCAT entries: %d, "
                "DEBRIS with TLE: %d, ROCKET BODY with TLE: %d.",
                len(sats),
                n_anomalies,
                len(satcat),
                debris_with_tle,
                rb_with_tle,
            )
        else:
            logger.warning(
                "READY (degraded mode): 0 satellites loaded. "
                "The API will return empty results until data is available."
            )

    except Exception as exc:
        # Catch-all: log but NEVER crash the server
        logger.critical(
            "Unexpected error during startup pipeline: %s",
            exc,
            exc_info=True,
        )
        logger.warning(
            "Server starting in degraded mode -- "
            "all endpoints will return empty/default data."
        )

    yield

    # --- Shutdown cleanup ---
    _state["satellites_tle"] = []
    _state["df_anomalies"] = None
    _state["detector"] = None
    _state["last_report"] = None
    _state["satcat_lookup"] = {}
    _state["tle_extra_lookup"] = {}
    logger.info("Shutdown complete.")


# ----------------------------------------------------------------
# App setup
# ----------------------------------------------------------------
app = FastAPI(
    title="AI-Orbit Intelligence 3D",
    description=(
        "Real-time orbital anomaly detection API. "
        "Sprint 13 - Multi-source TLE for debris visibility."
    ),
    version="1.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ----------------------------------------------------------------
# Routes
# ----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    df = _state.get("df_anomalies")
    n_anomalies = int(df["is_anomaly"].sum()) if df is not None else 0
    return HealthResponse(
        status="ok",
        version="1.3.0",
        satellites_loaded=len(_state.get("satellites_tle", [])),
        anomalies_detected=n_anomalies,
    )


@app.get(
    "/api/positions",
    response_model=PositionsResponse,
    tags=["realtime"],
)
async def get_positions(
    filter_type: str = Query(
        default="ALL",
        description="ALL, LEO, MEO, GEO, ANOMALIES, or TOP10.",
    ),
    owner: Optional[str] = Query(
        default=None,
        description=(
            "Filter by country/owner code "
            "(e.g. US, PRC, CIS, FR, UK, ESA, IND, JPN)."
        ),
    ),
    object_type: Optional[str] = Query(
        default=None,
        description=(
            "Filter by object type "
            "(e.g. PAYLOAD, DEBRIS, ROCKET BODY, TBA, UNKNOWN)."
        ),
    ),
) -> PositionsResponse:
    satellites = _state.get("satellites_tle", [])
    df_anom = _state.get("df_anomalies")
    satcat = _state.get("satcat_lookup", {})
    tle_extra = _state.get("tle_extra_lookup", {})

    # Sprint 11: return empty list instead of 503 when in degraded mode
    if not satellites:
        return PositionsResponse(
            timestamp=time.time(),
            total_satellites=0,
            satellites=[],
        )

    anomaly_lookup: Dict[int, Dict[str, Any]] = {}
    if df_anom is not None:
        anomaly_lookup = df_anom[
            ["anomaly_score", "is_anomaly"]
        ].to_dict("index")

    filter_upper = filter_type.upper()

    # Sprint 12 fix: pre-normalise filter values once (not per-satellite)
    owner_filter_upper: Optional[str] = None
    if owner and owner.strip():
        owner_filter_upper = owner.strip().upper()

    object_type_filter_upper: Optional[str] = None
    if object_type and object_type.strip():
        object_type_filter_upper = object_type.strip().upper()

    t_now = ts.now()

    positions: List[SatellitePosition] = []
    for sat in satellites:
        try:
            geocentric = sat.at(t_now)
            subpoint = wgs84.subpoint(geocentric)
            lat = subpoint.latitude.degrees
            lon = subpoint.longitude.degrees
            alt = subpoint.elevation.km
        except Exception:
            continue

        # Sprint 11: skip satellites with non-finite coordinates (inf/NaN)
        if not (
            math.isfinite(lat)
            and math.isfinite(lon)
            and math.isfinite(alt)
        ):
            continue

        norad_id = sat.model.satnum
        orbit_type = classify_orbit(alt)

        anom_data = anomaly_lookup.get(norad_id)
        if anom_data is not None:
            score = float(anom_data["anomaly_score"])
            flagged = bool(anom_data["is_anomaly"])
        else:
            score = 0.0
            flagged = False

        # SATCAT enrichment (Sprint 8, normalised in Sprint 12)
        sat_meta = satcat.get(norad_id, {})
        sat_owner = sat_meta.get("owner", "UNKNOWN")
        sat_object_type = sat_meta.get("object_type", "UNKNOWN")

        # Sprint 9: TLE extra data (mean_motion & inclination)
        tle_data = tle_extra.get(norad_id, {})
        sat_mean_motion = tle_data.get("mean_motion", 0.0)
        sat_inclination = tle_data.get("inclination", 0.0)

        # --- Orbit / anomaly filters ---
        if filter_upper == "LEO" and orbit_type != "LEO":
            continue
        if filter_upper == "MEO" and orbit_type != "MEO":
            continue
        if filter_upper == "GEO" and orbit_type != "GEO":
            continue
        if filter_upper == "ANOMALIES" and not flagged:
            continue

        # --- Strategic OSINT filters (Sprint 8 + Sprint 12 fix) ---
        # Case-insensitive, whitespace-tolerant comparisons
        if owner_filter_upper:
            if sat_owner.strip().upper() != owner_filter_upper:
                continue
        if object_type_filter_upper:
            if sat_object_type.strip().upper() != object_type_filter_upper:
                continue

        positions.append(
            SatellitePosition(
                name=sat.name,
                norad_id=norad_id,
                lat=round(lat, 4),
                lon=round(lon, 4),
                alt=round(alt, 2),
                orbit_type=orbit_type,
                anomaly_score=round(score, 4),
                is_anomaly=flagged,
                owner=sat_owner,
                object_type=sat_object_type,
                mean_motion=sat_mean_motion,
                inclination=sat_inclination,
            )
        )

    # --- Sprint 7: TOP10 filter ---
    if filter_upper == "TOP10":
        positions.sort(key=lambda p: p.anomaly_score, reverse=True)
        positions = positions[:10]

    return PositionsResponse(
        timestamp=time.time(),
        total_satellites=len(positions),
        satellites=positions,
    )


@app.post(
    "/api/v1/ingest",
    response_model=IngestResponse,
    tags=["pipeline"],
)
async def ingest_tle(
    data_dir: str = Query(default="data"),
) -> IngestResponse:
    try:
        dir_path = Path(data_dir)
        result_path = fetch_tle_data(data_dir=dir_path)
        satellites = load_tle_objects(data_dir=dir_path)
        _state["satellites_tle"] = satellites
        return IngestResponse(
            status="ok",
            file_path=str(result_path),
            satellite_count=len(satellites),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"TLE download failed: {exc}",
        ) from exc


@app.post(
    "/api/v1/analyse",
    response_model=AnomalyReport,
    tags=["pipeline"],
)
async def analyse(
    data_dir: str = Query(default="data"),
    contamination: float = Query(
        default=0.05, ge=0.001, le=0.5
    ),
) -> AnomalyReport:
    try:
        satellites = load_tle_objects(data_dir=Path(data_dir))
        _state["satellites_tle"] = satellites

        df = extract_features(satellites)
        if df.empty:
            raise HTTPException(
                status_code=422,
                detail="No satellites could be parsed.",
            )

        detector = OrbitalAnomalyDetector(contamination=contamination)
        df_result = detector.fit_predict(df)
        _state["df_anomalies"] = df_result
        _state["detector"] = detector

        records: List[SatelliteAnomaly] = []
        for norad_id, row in df_result.iterrows():
            records.append(
                SatelliteAnomaly(
                    name=row["name"],
                    norad_id=int(norad_id),
                    inclination=round(
                        float(row["inclination"]), 6
                    ),
                    eccentricity=round(
                        float(row["eccentricity"]), 6
                    ),
                    mean_motion=round(
                        float(row["mean_motion"]), 6
                    ),
                    bstar=float(row["bstar"]),
                    is_anomaly=bool(row["is_anomaly"]),
                    anomaly_score=round(
                        float(row["anomaly_score"]), 4
                    ),
                )
            )

        report = AnomalyReport(
            total_satellites=len(df_result),
            total_anomalies=int(df_result["is_anomaly"].sum()),
            contamination_rate=contamination,
            satellites=records,
        )
        _state["last_report"] = report
        return report

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="TLE data not found.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@app.get(
    "/api/v1/anomalies",
    response_model=List[SatelliteAnomaly],
    tags=["results"],
)
async def get_anomalies(
    top_n: int = Query(default=10, ge=1, le=500),
    min_score: Optional[float] = Query(
        default=None, ge=0.0, le=1.0
    ),
) -> List[SatelliteAnomaly]:
    report = _state.get("last_report")
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis results available.",
        )
    results = sorted(
        report.satellites,
        key=lambda s: s.anomaly_score,
        reverse=True,
    )
    if min_score is not None:
        results = [s for s in results if s.anomaly_score >= min_score]
    return results[:top_n]


@app.get(
    "/api/v1/satellite/{norad_id}",
    response_model=SatelliteAnomaly,
    tags=["results"],
)
async def get_satellite(norad_id: int) -> SatelliteAnomaly:
    report = _state.get("last_report")
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis results available.",
        )
    for sat in report.satellites:
        if sat.norad_id == norad_id:
            return sat
    raise HTTPException(
        status_code=404,
        detail=f"Satellite {norad_id} not found.",
    )


# ----------------------------------------------------------------
# Cloud-ready launcher (Sprint 10)
# ----------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
