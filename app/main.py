"""FastAPI application — Orbital anomaly detection REST API.

Exposes the full orbital intelligence pipeline (TLE ingestion,
feature extraction, Isolation Forest anomaly detection) through
structured REST endpoints with Pydantic response models.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
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

app = FastAPI(
    title="AI-Orbit Intelligence 3D",
    description=(
        "Real-time orbital anomaly detection API. "
        "Analyses satellite TLE data with Isolation Forest "
        "to identify anomalous orbital behaviour."
    ),
    version="0.4.0",
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., examples=["ok"])
    version: str = Field(..., examples=["0.4.0"])


class SatelliteAnomaly(BaseModel):
    """Single satellite anomaly result."""

    name: str = Field(..., examples=["ISS (ZARYA)"])
    norad_id: int = Field(..., examples=[25544])
    inclination: float = Field(..., examples=[0.9013])
    eccentricity: float = Field(..., examples=[0.0001])
    mean_motion: float = Field(..., examples=[0.0634])
    bstar: float = Field(..., examples=[0.0001])
    is_anomaly: bool = Field(..., examples=[False])
    anomaly_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        examples=[0.12],
        description=(
            "Anomaly severity: 0.0 = normal, 1.0 = highly anomalous."
        ),
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
    file_path: str = Field(
        ..., examples=["data/active_satellites.txt"]
    )
    satellite_count: int = Field(..., examples=[9000])


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

_state: dict = {
    "detector": None,
    "last_report": None,
    "satellites_tle": None,
}


# ---------------------------------------------------------------------------
# Helper: classify orbit type by altitude
# ---------------------------------------------------------------------------

def classify_orbit(alt_km: float) -> str:
    """Classify orbit type based on altitude."""
    if alt_km < 2000:
        return "LEO"
    elif alt_km < 35786:
        return "MEO"
    else:
        return "GEO"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse, tags=["frontend"])
async def index(request: Request):
    """Serve the 3D globe visualization frontend."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Health check",
)
async def health() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(status="ok", version="0.4.0")


@app.get(
    "/api/positions",
    tags=["realtime"],
    summary="Real-time satellite positions",
)
async def get_positions(
    filter_type: str = Query(
        default="ALL",
        description="Filter: ALL, LEO, MEO, GEO, or ANOMALIES.",
    ),
):
    """Propagate all satellites to current time and return positions.

    Uses SGP4 via Skyfield to compute real-time lat/lon/alt for
    every satellite in the catalogue. Merges anomaly scores from
    the last analysis run if available.
    """
    # Load TLE objects if not cached
    if _state["satellites_tle"] is None:
        try:
            _state["satellites_tle"] = load_tle_objects(
                data_dir=Path("data")
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=404,
                detail="TLE data not found. Run POST /api/v1/ingest first.",
            )

    satellites = _state["satellites_tle"]
    ts = load.timescale()
    t = ts.now()

    # Build anomaly lookup from last report
    anomaly_lookup: Dict[int, Dict[str, Any]] = {}
    report = _state.get("last_report")
    if report is not None:
        for sat in report.satellites:
            anomaly_lookup[sat.norad_id] = {
                "is_anomaly": sat.is_anomaly,
                "anomaly_score": sat.anomaly_score,
            }

    results = []
    for sat in satellites:
        try:
            geocentric = sat.at(t)
            subpoint = wgs84.subpoint(geocentric)
            lat = subpoint.latitude.degrees
            lon = subpoint.longitude.degrees
            alt = subpoint.elevation.km

            norad_id = sat.model.satnum
            anom_info = anomaly_lookup.get(norad_id, {})
            is_anomaly = anom_info.get("is_anomaly", False)
            anomaly_score = anom_info.get("anomaly_score", 0.0)
            orbit_type = classify_orbit(alt)

            # Apply filter
            if filter_type == "LEO" and orbit_type != "LEO":
                continue
            if filter_type == "MEO" and orbit_type != "MEO":
                continue
            if filter_type == "GEO" and orbit_type != "GEO":
                continue
            if filter_type == "ANOMALIES" and not is_anomaly:
                continue

            results.append({
                "name": sat.name,
                "norad_id": norad_id,
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "alt": round(alt, 2),
                "orbit_type": orbit_type,
                "is_anomaly": is_anomaly,
                "anomaly_score": round(anomaly_score, 4),
            })
        except Exception:
            continue

    return {
        "total_satellites": len(results),
        "satellites": results,
    }


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
    """Fetch the latest TLE data from CelesTrak.

    Downloads the active satellite catalogue and persists
    it locally for subsequent analysis.
    """
    try:
        dir_path = Path(data_dir)
        result_path = fetch_tle_data(data_dir=dir_path)
        satellites = load_tle_objects(data_dir=dir_path)
        # Cache TLE objects for position endpoint
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
    summary="Run anomaly detection",
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
    """Run the full anomaly detection pipeline.

    Loads TLE data, extracts orbital features, trains an
    Isolation Forest model, and returns scored results for
    every satellite.
    """
    try:
        satellites = load_tle_objects(
            data_dir=Path(data_dir)
        )
        # Cache TLE objects for position endpoint
        _state["satellites_tle"] = satellites
        df = extract_features(satellites)

        if df.empty:
            raise HTTPException(
                status_code=422,
                detail="No satellites could be parsed.",
            )

        detector = OrbitalAnomalyDetector(
            contamination=contamination,
        )
        df_result = detector.fit_predict(df)

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
            total_anomalies=int(
                df_result["is_anomaly"].sum()
            ),
            contamination_rate=contamination,
            satellites=records,
        )
        _state["last_report"] = report
        return report

    except FileNotFoundError as exc:
        logger.error("TLE file missing: %s", exc)
        raise HTTPException(
            status_code=404,
            detail=(
                "TLE data not found. "
                "Run POST /api/v1/ingest first."
            ),
        ) from exc
    except ValueError as exc:
        logger.error("Analysis error: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@app.get(
    "/api/v1/anomalies",
    response_model=List[SatelliteAnomaly],
    tags=["results"],
    summary="Get top anomalies",
)
async def get_anomalies(
    top_n: int = Query(
        default=10,
        ge=1,
        le=500,
        description="Number of top anomalies to return.",
    ),
    min_score: Optional[float] = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum anomaly score filter.",
    ),
) -> List[SatelliteAnomaly]:
    """Return the most anomalous satellites from the last run.

    Requires a prior call to POST /api/v1/analyse.
    Results are sorted by descending anomaly score.
    """
    report: Optional[AnomalyReport] = _state.get(
        "last_report"
    )
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No analysis results available. "
                "Run POST /api/v1/analyse first."
            ),
        )

    results = sorted(
        report.satellites,
        key=lambda s: s.anomaly_score,
        reverse=True,
    )

    if min_score is not None:
        results = [
            s for s in results
            if s.anomaly_score >= min_score
        ]

    return results[:top_n]


@app.get(
    "/api/v1/satellite/{norad_id}",
    response_model=SatelliteAnomaly,
    tags=["results"],
    summary="Get satellite by NORAD ID",
)
async def get_satellite(
    norad_id: int,
) -> SatelliteAnomaly:
    """Look up a single satellite by its NORAD catalogue number.

    Requires a prior call to POST /api/v1/analyse.
    """
    report: Optional[AnomalyReport] = _state.get(
        "last_report"
    )
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No analysis results available. "
                "Run POST /api/v1/analyse first."
            ),
        )

    for sat in report.satellites:
        if sat.norad_id == norad_id:
            return sat

    raise HTTPException(
        status_code=404,
        detail=f"Satellite {norad_id} not found.",
    )
