"""FastAPI application — AI-Orbit Intelligence 3D (Sprint 7 Consolidated).

Unified backend with lifespan-based automatic pipeline:
  - TLE loading at startup
    - Isolation Forest anomaly detection at startup
      - Real-time SGP4 positions with anomaly scores
        - TOP10 filter support
          - All Sprint 4 endpoints preserved for backward compatibility

          No manual POST /api/v1/analyse needed — anomalies are ready on boot.
          """

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

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

# ---------------------------------------------------------------------------
# Skyfield timescale (shared, loaded once)
# ---------------------------------------------------------------------------
ts = load.timescale()

# ---------------------------------------------------------------------------
# Application state — populated by the lifespan handler
# ---------------------------------------------------------------------------
_state: Dict[str, Any] = {
        "satellites_tle": [],
        "df_anomalies": None,
        "detector": None,
        "last_report": None,
}


# ---------------------------------------------------------------------------
# Helper: classify orbit type by altitude
# ---------------------------------------------------------------------------
def classify_orbit(alt_km: float) -> str:
        """Classify orbit type based on altitude."""
        if alt_km < 2000:
                    return "LEO"
elif alt_km > 35000:
        return "GEO"
    return "MEO"


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
        """Health check response."""
        status: str = Field(..., examples=["ok"])
        version: str = Field(..., examples=["0.7.0"])
        satellites_loaded: int = Field(..., examples=[14000])
        anomalies_detected: int = Field(..., examples=[700])


class SatellitePosition(BaseModel):
        """Real-time position of a single satellite."""
        name: str = Field(..., examples=["ISS (ZARYA)"])
        norad_id: int = Field(..., examples=[25544])
        lat: float = Field(..., examples=[51.64])
        lon: float = Field(..., examples=[0.12])
        alt: float = Field(..., examples=[408.0])
        orbit_type: str = Field(..., examples=["LEO"])
        anomaly_score: float = Field(
            ..., ge=0.0, le=1.0, examples=[0.12],
            description="0.0 = normal, 1.0 = highly anomalous.",
        )
        is_anomaly: bool = Field(..., examples=[False])


class PositionsResponse(BaseModel):
        """Batch response for all satellite positions."""
        timestamp: float = Field(..., examples=[1709136000.0])
        total_satellites: int = Field(..., examples=[10000])
        satellites: List[SatellitePosition]


class SatelliteAnomaly(BaseModel):
        """Single satellite anomaly result (legacy v1 compat)."""
        name: str = Field(..., examples=["ISS (ZARYA)"])
        norad_id: int = Field(..., examples=[25544])
        inclination: float = Field(..., examples=[0.9013])
        eccentricity: float = Field(..., examples=[0.0001])
        mean_motion: float = Field(..., examples=[0.0634])
        bstar: float = Field(..., examples=[0.0001])
        is_anomaly: bool = Field(..., examples=[False])
        anomaly_score: float = Field(
            ..., ge=0.0, le=1.0, examples=[0.12],
        )


class AnomalyReport(BaseModel):
        """Full anomaly detection report."""
        total_satellites: int = Field(..., examples=[9000])
        total_anomalies: int = Field(..., examples=[450])
        contamination_rate: float = Field(..., examples=[0.05])
        satellites: List[SatelliteAnomaly]


class IngestResponse(BaseModel):
        """TLE ingestion result."""
        status: str = Field(..., examples=["ok"])
        file_path: str = Field(..., examples=["data/active_satellites.txt"])
        satellite_count: int = Field(..., examples=[9000])


# ---------------------------------------------------------------------------
# Lifespan: automatic pipeline at startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        """Load TLE catalogue and train Isolation Forest at startup."""
        logger.info("=" * 60)
        logger.info("AI-Orbit Intelligence 3D — Initializing...")
        logger.info("=" * 60)

    try:
                # Step 1: Load TLE objects
                logger.info("[1/3] Loading TLE satellite catalogue...")
                sats: List[EarthSatellite] = load_tle_objects(
                    data_dir=DEFAULT_DATA_DIR
                )
                logger.info("Loaded %d satellites from TLE file.", len(sats))
                _state["satellites_tle"] = sats

        # Step 2: Extract orbital features
                logger.info("[2/3] Extracting orbital features...")
                df: pd.DataFrame = extract_features(sats)
                logger.info("Extracted features for %d satellites.", len(df))

        # Step 3: Train Isolation Forest and score anomalies
                logger.info("[3/3] Training Isolation Forest anomaly detector...")
                detector = OrbitalAnomalyDetector(contamination=0.05)
                df_anomalies: pd.DataFrame = detector.fit_predict(df)
                _state["df_anomalies"] = df_anomalies
                _state["detector"] = detector

        n_anomalies = int(df_anomalies["is_anomaly"].sum())

        # Build legacy report for backward-compatible endpoints
        records: List[SatelliteAnomaly] = []
        for norad_id, row in df_anomalies.iterrows():
                        records.append(
                                            SatelliteAnomaly(
                                                                    name=row["name"],
                                                                    norad_id=int(norad_id),
                                                                    inclination=round(float(row["inclination"]), 6),
                                                                    eccentricity=round(float(row["eccentricity"]), 6),
                                                                    mean_motion=round(float(row["mean_motion"]), 6),
                                                                    bstar=float(row["bstar"]),
                                                                    is_anomaly=bool(row["is_anomaly"]),
                                                                    anomaly_score=round(float(row["anomaly_score"]), 4),
                                            )
                        )
                    _state["last_report"] = AnomalyReport(
                                    total_satellites=len(df_anomalies),
                                    total_anomalies=n_anomalies,
                                    contamination_rate=0.05,
                                    satellites=records,
                    )

        logger.info("=" * 60)
        logger.info(
                        "READY: %d satellites loaded, %d anomalies detected.",
                        len(sats), n_anomalies,
        )
        logger.info("=" * 60)

except FileNotFoundError as exc:
        logger.critical("TLE file not found: %s", exc)
        logger.critical(
                        "Place TLE data in data/active_satellites.txt "
                        "or run POST /api/v1/ingest after startup."
        )

    yield

    # Shutdown cleanup
    _state["satellites_tle"] = []
    _state["df_anomalies"] = None
    _state["detector"] = None
    _state["last_report"] = None
    logger.info("Shutdown complete — state cleared.")


# ---------------------------------------------------------------------------
# FastAPI app with lifespan
# ---------------------------------------------------------------------------
app = FastAPI(
        title="AI-Orbit Intelligence 3D",
        description=(
                    "Real-time orbital anomaly detection API. "
                    "Sprint 7: Automatic startup pipeline, TOP10, Toggle Vectors, "
                    "Wiki enrichment, Active Selection."
        ),
        version="0.7.0",
        lifespan=lifespan,
)

app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
)

# Mount static files and templates
app.mount(
        "/static",
        StaticFiles(directory=BASE_DIR / "static"),
        name="static",
)
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def index(request: Request):
        """Serve the 3D globe visualization frontend."""
        return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
@app.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Health check",
)
async def health() -> HealthResponse:
        """Return application health status and loaded counts."""
        df = _state.get("df_anomalies")
        n_anomalies = int(df["is_anomaly"].sum()) if df is not None else 0
        return HealthResponse(
            status="ok",
            version="0.7.0",
            satellites_loaded=len(_state.get("satellites_tle", [])),
            anomalies_detected=n_anomalies,
        )


# ---------------------------------------------------------------------------
# Real-time positions (Sprint 7 — main endpoint for the frontend)
# ---------------------------------------------------------------------------
@app.get(
        "/api/positions",
        response_model=PositionsResponse,
        tags=["realtime"],
        summary="Real-time satellite positions",
)
async def get_positions(
        filter_type: str = Query(
                    default="ALL",
                    description="Filter: ALL, LEO, MEO, GEO, ANOMALIES, or TOP10.",
        ),
) -> PositionsResponse:
        """Propagate all satellites to current time and return positions.

            When filter_type is TOP10, returns only the 10 satellites with
                the highest anomaly_score (sorted descending).
                    """
        satellites = _state.get("satellites_tle", [])
        df_anom: Optional[pd.DataFrame] = _state.get("df_anomalies")

    if not satellites:
                raise HTTPException(
                                status_code=503,
                                detail="Satellite data not loaded yet.",
                )

    # Build anomaly lookup from DataFrame
    anomaly_lookup: Dict[int, Dict[str, Any]] = {}
    if df_anom is not None:
                anomaly_lookup = (
                                df_anom[["anomaly_score", "is_anomaly"]]
                                .to_dict("index")
                )

    filter_upper: str = filter_type.upper()
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

        # Standard orbit/anomaly filters
            if filter_upper == "LEO" and orbit_type != "LEO":
                            continue
                        if filter_upper == "MEO" and orbit_type != "MEO":
                                        continue
                                    if filter_upper == "GEO" and orbit_type != "GEO":
                                                    continue
                                                if filter_upper == "ANOMALIES" and not flagged:
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
                        )
        )

    # --- Sprint 7: TOP10 filter ---
    if filter_upper == "TOP10":
                positions.sort(
                                key=lambda p: p.anomaly_score, reverse=True
                )
                positions = positions[:10]

    return PositionsResponse(
                timestamp=time.time(),
                total_satellites=len(positions),
                satellites=positions,
    )


# ---------------------------------------------------------------------------
# Pipeline endpoints (kept for manual re-runs if needed)
# ---------------------------------------------------------------------------
@app.post(
        "/api/v1/ingest",
        response_model=IngestResponse,
        tags=["pipeline"],
        summary="Download latest TLE data",
)
async def ingest_tle(
        data_dir: str = Query(
                    default="data",
                    description="Directory for TLE storage.",
        ),
) -> IngestResponse:
        """Fetch the latest TLE data from CelesTrak and reload."""
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
        logger.error("Ingestion failed: %s", exc)
        raise HTTPException(
                        status_code=502,
                        detail=f"TLE download failed: {exc}",
        ) from exc


@app.post(
        "/api/v1/analyse",
        response_model=AnomalyReport,
        tags=["pipeline"],
        summary="Re-run anomaly detection",
)
async def analyse(
        data_dir: str = Query(
                    default="data",
                    description="Directory containing TLE files.",
        ),
        contamination: float = Query(
                    default=0.05,
                    ge=0.001,
                    le=0.5,
                    description="Expected anomaly proportion.",
        ),
) -> AnomalyReport:
        """Re-run the full anomaly detection pipeline manually."""
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
                                                                    inclination=round(float(row["inclination"]), 6),
                                                                    eccentricity=round(float(row["eccentricity"]), 6),
                                                                    mean_motion=round(float(row["mean_motion"]), 6),
                                                                    bstar=float(row["bstar"]),
                                                                    is_anomaly=bool(row["is_anomaly"]),
                                                                    anomaly_score=round(float(row["anomaly_score"]), 4),
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
        logger.error("TLE file missing: %s", exc)
        raise HTTPException(
                        status_code=404,
                        detail="TLE data not found. Run POST /api/v1/ingest first.",
        ) from exc
except ValueError as exc:
        logger.error("Analysis error: %s", exc)
        raise HTTPException(
                        status_code=422, detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Results endpoints (backward compat)
# ---------------------------------------------------------------------------
@app.get(
        "/api/v1/anomalies",
        response_model=List[SatelliteAnomaly],
        tags=["results"],
        summary="Get top anomalies",
)
async def get_anomalies(
        top_n: int = Query(default=10, ge=1, le=500),
        min_score: Optional[float] = Query(default=None, ge=0.0, le=1.0),
) -> List[SatelliteAnomaly]:
        """Return the most anomalous satellites."""
    report: Optional[AnomalyReport] = _state.get("last_report")
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
        summary="Get satellite by NORAD ID",
)
async def get_satellite(norad_id: int) -> SatelliteAnomaly:
        """Look up a single satellite by its NORAD catalogue number."""
    report: Optional[AnomalyReport] = _state.get("last_report")
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
