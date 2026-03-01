"""FastAPI application - AI-Orbit Intelligence 3D (Sprint 9 Consolidated).

Unified backend with lifespan-based automatic pipeline.
Sprint 8: SATCAT enrichment (owner, object_type), strategic OSINT filters.
Sprint 9: Added mean_motion & inclination to SatellitePosition for client-side orbital animation.
No manual POST /api/v1/analyse needed.
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

DEFAULT_DATA_DIR: Path = Path("data")
BASE_DIR: Path = Path(__file__).resolve().parent

ts = load.timescale()

SATCAT_URL: str = "https://celestrak.org/satcat/records.php?GROUP=active&FORMAT=json"

_state: Dict[str, Any] = {
    "satellites_tle": [],
    "df_anomalies": None,
    "detector": None,
    "last_report": None,
    "satcat_lookup": {},
    "tle_extra_lookup": {},  # Sprint 9: mean_motion & inclination from TLE
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
def build_tle_extra_lookup(sats: List[EarthSatellite]) -> Dict[int, Dict[str, float]]:
    """Extract mean_motion (revs/day) and inclination (degrees)
    directly from the SGP4 TLE model for each satellite."""
    lookup: Dict[int, Dict[str, float]] = {}
    for sat in sats:
        norad_id = sat.model.satnum
        try:
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


# ----------------------------------------------------------------
# Pydantic models
# ----------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    version: str = Field(..., examples=["0.9.0"])
    satellites_loaded: int = Field(..., examples=[14000])
    anomalies_detected: int = Field(..., examples=[700])


class SatellitePosition(BaseModel):
    name: str = Field(..., examples=["ISS (ZARYA)"])
    norad_id: int = Field(..., examples=[25544])
    lat: float = Field(..., examples=[51.64])
    lon: float = Field(..., examples=[0.12])
    alt: float = Field(..., examples=[408.0])
    orbit_type: str = Field(..., examples=["LEO"])
    anomaly_score: float = Field(..., ge=0.0, le=1.0, examples=[0.12])
    is_anomaly: bool = Field(..., examples=[False])
    owner: str = Field("UNKNOWN", examples=["US"])
    object_type: str = Field("UNKNOWN", examples=["PAYLOAD"])
    # Sprint 9: orbital dynamics for client-side animation
    mean_motion: float = Field(0.0, examples=[15.49], description="Mean motion in revolutions per day (from TLE).")
    inclination: float = Field(0.0, examples=[51.6442], description="Orbital inclination in degrees (from TLE).")


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
    anomaly_score: float = Field(..., ge=0.0, le=1.0, examples=[0.12])


class AnomalyReport(BaseModel):
    total_satellites: int = Field(..., examples=[9000])
    total_anomalies: int = Field(..., examples=[450])
    contamination_rate: float = Field(..., examples=[0.05])
    satellites: List[SatelliteAnomaly]


class IngestResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    file_path: str = Field(..., examples=["data/active_satellites.txt"])
    satellite_count: int = Field(..., examples=[9000])


# ----------------------------------------------------------------
# SATCAT fetcher (Sprint 8)
# ----------------------------------------------------------------
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


# ----------------------------------------------------------------
# Lifespan
# ----------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("AI-Orbit Intelligence 3D - Initializing...")
    try:
        logger.info("[1/5] Loading TLE satellite catalogue...")
        sats = load_tle_objects(data_dir=DEFAULT_DATA_DIR)
        logger.info("Loaded %d satellites.", len(sats))
        _state["satellites_tle"] = sats

        logger.info("[2/5] Downloading SATCAT (owner & object type)...")
        _state["satcat_lookup"] = fetch_satcat()

        # Sprint 9: build TLE extra lookup for mean_motion & inclination
        logger.info("[3/5] Building TLE extra lookup (mean_motion & inclination)...")
        _state["tle_extra_lookup"] = build_tle_extra_lookup(sats)
        logger.info("TLE extra lookup built: %d entries.", len(_state["tle_extra_lookup"]))

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
            records.append(SatelliteAnomaly(
                name=row["name"],
                norad_id=int(norad_id),
                inclination=round(float(row["inclination"]), 6),
                eccentricity=round(float(row["eccentricity"]), 6),
                mean_motion=round(float(row["mean_motion"]), 6),
                bstar=float(row["bstar"]),
                is_anomaly=bool(row["is_anomaly"]),
                anomaly_score=round(float(row["anomaly_score"]), 4),
            ))

        _state["last_report"] = AnomalyReport(
            total_satellites=len(df_anomalies),
            total_anomalies=n_anomalies,
            contamination_rate=0.05,
            satellites=records,
        )

        logger.info(
            "READY: %d satellites, %d anomalies, SATCAT entries: %d.",
            len(sats), n_anomalies, len(_state["satcat_lookup"]),
        )
    except FileNotFoundError as exc:
        logger.critical("TLE file not found: %s", exc)

    yield

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
    description="Real-time orbital anomaly detection API. Sprint 9.",
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

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
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
        version="0.9.0",
        satellites_loaded=len(_state.get("satellites_tle", [])),
        anomalies_detected=n_anomalies,
    )


@app.get("/api/positions", response_model=PositionsResponse, tags=["realtime"])
async def get_positions(
    filter_type: str = Query(
        default="ALL",
        description="ALL, LEO, MEO, GEO, ANOMALIES, or TOP10.",
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
    satellites = _state.get("satellites_tle", [])
    df_anom = _state.get("df_anomalies")
    satcat = _state.get("satcat_lookup", {})
    tle_extra = _state.get("tle_extra_lookup", {})

    if not satellites:
        raise HTTPException(status_code=503, detail="Satellite data not loaded yet.")

    anomaly_lookup: Dict[int, Dict[str, Any]] = {}
    if df_anom is not None:
        anomaly_lookup = df_anom[["anomaly_score", "is_anomaly"]].to_dict("index")

    filter_upper = filter_type.upper()
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

        norad_id = sat.model.satnum
        orbit_type = classify_orbit(alt)

        anom_data = anomaly_lookup.get(norad_id)
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

        # --- Orbit / anomaly filters ---
        if filter_upper == "LEO" and orbit_type != "LEO":
            continue
        if filter_upper == "MEO" and orbit_type != "MEO":
            continue
        if filter_upper == "GEO" and orbit_type != "GEO":
            continue
        if filter_upper == "ANOMALIES" and not flagged:
            continue

        # --- Strategic OSINT filters (Sprint 8) ---
        if owner and sat_owner != owner.strip():
            continue
        if object_type and sat_object_type.upper() != object_type.strip().upper():
            continue

        positions.append(SatellitePosition(
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
        ))

    # --- Sprint 7: TOP10 filter ---
    if filter_upper == "TOP10":
        positions.sort(key=lambda p: p.anomaly_score, reverse=True)
        positions = positions[:10]

    return PositionsResponse(
        timestamp=time.time(),
        total_satellites=len(positions),
        satellites=positions,
    )


@app.post("/api/v1/ingest", response_model=IngestResponse, tags=["pipeline"])
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
            detail=f"TLE download failed: {exc}"
        ) from exc


@app.post("/api/v1/analyse", response_model=AnomalyReport, tags=["pipeline"])
async def analyse(
    data_dir: str = Query(default="data"),
    contamination: float = Query(default=0.05, ge=0.001, le=0.5),
) -> AnomalyReport:
    try:
        satellites = load_tle_objects(data_dir=Path(data_dir))
        _state["satellites_tle"] = satellites

        df = extract_features(satellites)
        if df.empty:
            raise HTTPException(
                status_code=422,
                detail="No satellites could be parsed."
            )

        detector = OrbitalAnomalyDetector(contamination=contamination)
        df_result = detector.fit_predict(df)
        _state["df_anomalies"] = df_result
        _state["detector"] = detector

        records: List[SatelliteAnomaly] = []
        for norad_id, row in df_result.iterrows():
            records.append(SatelliteAnomaly(
                name=row["name"],
                norad_id=int(norad_id),
                inclination=round(float(row["inclination"]), 6),
                eccentricity=round(float(row["eccentricity"]), 6),
                mean_motion=round(float(row["mean_motion"]), 6),
                bstar=float(row["bstar"]),
                is_anomaly=bool(row["is_anomaly"]),
                anomaly_score=round(float(row["anomaly_score"]), 4),
            ))

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
            detail="TLE data not found."
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get(
    "/api/v1/anomalies",
    response_model=List[SatelliteAnomaly],
    tags=["results"],
)
async def get_anomalies(
    top_n: int = Query(default=10, ge=1, le=500),
    min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
) -> List[SatelliteAnomaly]:
    report = _state.get("last_report")
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis results available."
        )
    results = sorted(
        report.satellites,
        key=lambda s: s.anomaly_score,
        reverse=True
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
            detail="No analysis results available."
        )
    for sat in report.satellites:
        if sat.norad_id == norad_id:
            return sat
    raise HTTPException(
        status_code=404,
        detail=f"Satellite {norad_id} not found."
    )
