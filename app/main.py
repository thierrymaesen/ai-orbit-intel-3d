"""FastAPI application — Orbital anomaly detection REST API.

Exposes the full orbital intelligence pipeline (TLE ingestion,
feature extraction, Isolation Forest anomaly detection) through
structured REST endpoints with Pydantic response models.
"""

import logging
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from orbit_intel.anomaly import OrbitalAnomalyDetector
from orbit_intel.dynamics import extract_features, load_tle_objects
from orbit_intel.ingest import fetch_tle_data

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

DEFAULT_DATA_DIR: Path = Path("data")

app = FastAPI(
    title="AI-Orbit Intelligence 3D",
    description=(
        "Real-time orbital anomaly detection API. "
        "Analyses satellite TLE data with Isolation Forest "
        "to identify anomalous orbital behaviour."
    ),
    version="0.4.0",
)


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
}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Health check",
)
async def health() -> HealthResponse:
    """Return application health status."""
    return HealthResponse(status="ok", version="0.4.0")


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
