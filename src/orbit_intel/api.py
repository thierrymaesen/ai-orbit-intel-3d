"""FastAPI real-time satellite position & anomaly API.

Loads TLE data at startup (full catalogue), runs Isolation Forest
anomaly detection, and serves an endpoint that computes live
lat/lon/altitude positions for every satellite using Skyfield SGP4
propagation, enriched with the pre-computed anomaly severity score.

Sprint 6: full-scale catalogue, orbit_type classification, filter API.
"""

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

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

ts = load.timescale()

APP_STATE: Dict[str, Any] = {
    "satellites": [],
    "df_anomalies": None,
}


def classify_orbit(altitude_km: float) -> str:
    """Classify orbit: LEO < 2000 km, GEO > 35000 km, else MEO."""
    if altitude_km < 2000:
        return "LEO"
    if altitude_km > 35000:
        return "GEO"
    return "MEO"


class SatellitePosition(BaseModel):
    """Real-time position of a single satellite."""

    name: str = Field(..., examples=["ISS (ZARYA)"])
    norad_id: int = Field(..., examples=[25544])
    lat: float = Field(..., examples=[51.64], description="Latitude in degrees.")
    lon: float = Field(..., examples=[0.12], description="Longitude in degrees.")
    alt: float = Field(..., examples=[408.0], description="Altitude in kilometres.")
    orbit_type: str = Field(..., examples=["LEO"], description="LEO, MEO or GEO.")
    anomaly_score: float = Field(
        ..., ge=0.0, le=1.0, examples=[0.12],
        description="0.0 = normal, 1.0 = highly anomalous.",
    )
    is_anomaly: bool = Field(..., examples=[False], description="True if anomalous.")


class PositionsResponse(BaseModel):
    """Batch response for all satellite positions."""

    timestamp: float = Field(..., examples=[1709136000.0])
    total_satellites: int = Field(..., examples=[10000])
    satellites: List[SatellitePosition]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load full TLE catalogue and train Isolation Forest at startup."""
    logger.info("Initializing Space Data & AI Engine...")

    sats: List[EarthSatellite] = load_tle_objects(data_dir=DEFAULT_DATA_DIR)
    logger.info("Loaded full catalogue: %d satellites", len(sats))

    APP_STATE["satellites"] = sats

    df: pd.DataFrame = extract_features(sats)
    detector = OrbitalAnomalyDetector()
    df_anomalies: pd.DataFrame = detector.fit_predict(df)
    APP_STATE["df_anomalies"] = df_anomalies

    logger.info(
        "Startup complete: %d satellites, %d anomalies",
        len(sats),
        int(df_anomalies["is_anomaly"].sum()),
    )

    yield

    APP_STATE["satellites"] = []
    APP_STATE["df_anomalies"] = None
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AI-Orbit Intelligence 3D API",
    description="Real-time satellite tracking with Isolation Forest anomaly scores.",
    version="0.6.0",
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
        description="Filter: ALL, LEO, MEO, GEO, or ANOMALIES.",
    ),
) -> PositionsResponse:
    """Propagate every satellite, classify orbit, apply filter."""
    sats: List[EarthSatellite] = APP_STATE["satellites"]
    df_anom: pd.DataFrame = APP_STATE["df_anomalies"]

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
