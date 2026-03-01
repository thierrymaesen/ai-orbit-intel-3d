"""FastAPI real-time satellite position & anomaly API.

Loads TLE data at startup (full catalogue), downloads SATCAT for
owner/type enrichment, runs Isolation Forest anomaly detection, and
serves an endpoint that computes live lat/lon/altitude positions for
every satellite using Skyfield SGP4 propagation, enriched with the
pre-computed anomaly severity score plus owner and object_type metadata.

Sprint 8: SATCAT enrichment, owner & object_type filters.
Sprint 9: Added mean_motion & inclination fields for client-side orbital animation.
"""

import logging
import math
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from skyfield.api import EarthSatellite, load

from .anomaly import OrbitalAnomalyDetector
from .dynamics import extract_features, load_tle_objects

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

DEFAULT_DATA_DIR: Path = Path("data")
SATCAT_URL: str = "https://celestrak.org/satcat/records.php?GROUP=active&FORMAT=json"

ts = load.timescale()

APP_STATE: Dict[str, Any] = {
    "satellites": [],
    "df_anomalies": None,
    "satcat_lookup": {},
    "tle_extra_lookup": {},  # Sprint 9: mean_motion & inclination from TLE
}


def classify_orbit(altitude_km: float) -> str:
    """Classify orbit: LEO < 2000 km, GEO > 35000 km, else MEO."""
    if altitude_km < 2000:
        return "LEO"
    if altitude_km > 35000:
        return "GEO"
    return "MEO"


def fetch_satcat() -> Dict[int, Dict[str, str]]:
    """Download SATCAT JSON from CelesTrak and build a lookup dict keyed by
    NORAD_CAT_ID with owner and object_type values."""
    logger.info("Downloading SATCAT from %s ...", SATCAT_URL)
    lookup: Dict[int, Dict[str, str]] = {}
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(SATCAT_URL)
            resp.raise_for_status()
            records = resp.json()
        for rec in records:
            norad_id = rec.get("NORAD_CAT_ID")
            if norad_id is None:
                continue
            try:
                norad_id = int(norad_id)
            except (ValueError, TypeError):
                continue
            owner = rec.get("OWNER", "UNKNOWN") or "UNKNOWN"
            obj_type = rec.get("OBJECT_TYPE", "UNKNOWN") or "UNKNOWN"
            lookup[norad_id] = {
                "owner": owner.strip(),
                "object_type": obj_type.strip(),
            }
        logger.info("SATCAT loaded: %d records.", len(lookup))
    except Exception as exc:
        logger.error("Failed to download SATCAT: %s", exc)
    return lookup


def build_tle_extra_lookup(sats: List[EarthSatellite]) -> Dict[int, Dict[str, float]]:
    """Sprint 9: Extract mean_motion (revs/day) and inclination (degrees)
    directly from the SGP4 TLE model for each satellite.
    These values are embedded in the TLE lines and parsed by Skyfield/sgp4."""
    lookup: Dict[int, Dict[str, float]] = {}
    for sat in sats:
        norad_id = sat.model.satnum
        try:
            # sgp4 model stores mean motion in radians/minute -> convert to revs/day
            # no_kozai (rad/min) * 1440 / (2*pi) = revs/day
            mean_motion_revs_day = sat.model.no_kozai * 1440.0 / (2.0 * math.pi)
            inclination_deg = math.degrees(sat.model.inclo)
        except Exception:
            mean_motion_revs_day = 0.0
            inclination_deg = 0.0
        lookup[norad_id] = {
            "mean_motion": round(mean_motion_revs_day, 6),
            "inclination": round(inclination_deg, 4),
        }
    return lookup


class SatellitePosition(BaseModel):
    """Real-time position of a single satellite."""

    name: str = Field(..., examples=["ISS (ZARYA)"])
    norad_id: int = Field(..., examples=[25544])
    lat: float = Field(..., examples=[51.64], description="Latitude in degrees.")
    lon: float = Field(..., examples=[0.12], description="Longitude in degrees.")
    alt: float = Field(..., examples=[408.0], description="Altitude in kilometres.")
    orbit_type: str = Field(..., examples=["LEO"], description="LEO, MEO or GEO.")
    anomaly_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        examples=[0.12],
        description="0.0 = normal, 1.0 = highly anomalous.",
    )
    is_anomaly: bool = Field(..., examples=[False], description="True if anomalous.")
    owner: str = Field("UNKNOWN", examples=["US"], description="Country/owner code.")
    object_type: str = Field(
        "UNKNOWN",
        examples=["PAYLOAD"],
        description="PAYLOAD, DEBRIS, ROCKET BODY, etc.",
    )
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
    """Batch response for all satellite positions."""

    timestamp: float = Field(..., examples=[1709136000.0])
    total_satellites: int = Field(..., examples=[10000])
    satellites: List[SatellitePosition]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load full TLE catalogue, download SATCAT, and train Isolation Forest at startup."""
    logger.info("Initializing Space Data & AI Engine...")
    sats: List[EarthSatellite] = load_tle_objects(data_dir=DEFAULT_DATA_DIR)
    logger.info("Loaded full catalogue: %d satellites", len(sats))
    APP_STATE["satellites"] = sats

    # Sprint 8: download SATCAT for owner & object type enrichment
    APP_STATE["satcat_lookup"] = fetch_satcat()

    # Sprint 9: build TLE extra lookup for mean_motion & inclination
    APP_STATE["tle_extra_lookup"] = build_tle_extra_lookup(sats)
    logger.info("TLE extra lookup built: %d entries", len(APP_STATE["tle_extra_lookup"]))

    df: pd.DataFrame = extract_features(sats)
    detector = OrbitalAnomalyDetector()
    df_anomalies: pd.DataFrame = detector.fit_predict(df)
    APP_STATE["df_anomalies"] = df_anomalies
    logger.info(
        "Startup complete: %d satellites, %d anomalies, SATCAT entries: %d",
        len(sats),
        int(df_anomalies["is_anomaly"].sum()),
        len(APP_STATE["satcat_lookup"]),
    )
    yield
    APP_STATE["satellites"] = []
    APP_STATE["df_anomalies"] = None
    APP_STATE["satcat_lookup"] = {}
    APP_STATE["tle_extra_lookup"] = {}
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AI-Orbit Intelligence 3D API",
    description="Real-time satellite tracking with Isolation Forest anomaly scores.",
    version="0.9.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"], summary="Health check")
async def health() -> Dict[str, Any]:
    """Return application health and loaded satellite count."""
    return {
        "status": "ok",
        "satellites_loaded": len(APP_STATE["satellites"]),
    }


@app.get(
    "/api/positions",
    response_model=PositionsResponse,
    tags=["positions"],
    summary="Real-time satellite positions",
)
async def get_positions(
    filter_type: str = Query(
        "ALL",
        description="Filter: ALL, LEO, MEO, GEO, ANOMALIES, or TOP10.",
    ),
    owner: Optional[str] = Query(
        default=None,
        description="Filter by country/owner code (e.g. US, PRC, CIS, FR, UK, ESA, IND, JPN).",
    ),
    object_type: Optional[str] = Query(
        default=None,
        description="Filter by object type (e.g. PAYLOAD, DEBRIS, ROCKET BODY, TBA, UNKNOWN).",
    ),
) -> PositionsResponse:
    """Propagate every satellite, classify orbit, enrich with SATCAT,
    apply filters.

    When filter_type is TOP10, returns only the 10 satellites with the
    highest anomaly_score (sorted descending).
    """
    sats: List[EarthSatellite] = APP_STATE["satellites"]
    df_anom: pd.DataFrame = APP_STATE["df_anomalies"]
    satcat: Dict[int, Dict[str, str]] = APP_STATE.get("satcat_lookup", {})
    tle_extra: Dict[int, Dict[str, float]] = APP_STATE.get("tle_extra_lookup", {})

    if not sats or df_anom is None:
        raise HTTPException(
            status_code=503,
            detail="Satellite data not loaded yet.",
        )

    anomaly_index: Dict[int, Dict[str, Any]] = (
        df_anom[["anomaly_score", "is_anomaly"]].to_dict("index")
    )

    filter_upper: str = filter_type.upper()
    t_now = ts.now()
    positions: List[SatellitePosition] = []

    for sat in sats:
        try:
            geocentric = sat.at(t_now)
            subpoint = geocentric.subpoint()
            lat = subpoint.latitude.degrees
            lon = subpoint.longitude.degrees
            alt = subpoint.elevation.km
        except Exception:
            continue

        orbit_type = classify_orbit(alt)
        norad_id = sat.model.satnum

        anom_data = anomaly_index.get(norad_id)
        if anom_data is not None:
            score = float(anom_data["anomaly_score"])
            flagged = bool(anom_data["is_anomaly"])
        else:
            score = 0.0
            flagged = False

        # SATCAT enrichment (Sprint 8)
        sat_meta = satcat.get(norad_id, {})
        sat_owner = sat_meta.get("owner", "UNKNOWN")
        sat_object_type = sat_meta.get("object_type", "UNKNOWN")

        # Sprint 9: TLE extra data (mean_motion & inclination)
        tle_data = tle_extra.get(norad_id, {})
        sat_mean_motion = tle_data.get("mean_motion", 0.0)
        sat_inclination = tle_data.get("inclination", 0.0)

        # Standard orbit/anomaly filters
        if filter_upper == "LEO" and orbit_type != "LEO":
            continue
        if filter_upper == "MEO" and orbit_type != "MEO":
            continue
        if filter_upper == "GEO" and orbit_type != "GEO":
            continue
        if filter_upper == "ANOMALIES" and not flagged:
            continue

        # Strategic OSINT filters (Sprint 8)
        if owner and sat_owner != owner.strip():
            continue
        if object_type and sat_object_type.upper() != object_type.strip().upper():
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


@app.get("/", tags=["frontend"], summary="3D Globe UI")
async def root():
    """Serve the Globe.gl 3D visualisation page."""
    return FileResponse("app/templates/index.html")


app.mount("/static", StaticFiles(directory="app/static"), name="static")

if __name__ == "__main__":
    uvicorn.run("orbit_intel.api:app", host="0.0.0.0", port=8000, reload=True)
