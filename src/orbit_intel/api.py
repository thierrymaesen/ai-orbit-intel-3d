"""FastAPI real-time satellite position & anomaly API.

Loads TLE data at startup, runs Isolation Forest anomaly detection,
and serves an endpoint that computes live lat/lon/altitude positions
for every satellite using Skyfield SGP4 propagation, enriched with
the pre-computed anomaly severity score.
"""

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
MAX_SATELLITES: int = 1000

ts = load.timescale()

APP_STATE: Dict[str, Any] = {
      "satellites": [],
      "df_anomalies": None,
}


# -------------------------------------------------------------------
# Pydantic response schemas
# -------------------------------------------------------------------


class SatellitePosition(BaseModel):
      """Real-time position of a single satellite."""

    name: str = Field(..., examples=["ISS (ZARYA)"])
    norad_id: int = Field(..., examples=[25544])
    lat: float = Field(
              ...,
              examples=[51.64],
              description="Latitude in degrees.",
    )
    lon: float = Field(
              ...,
              examples=[-0.12],
              description="Longitude in degrees.",
    )
    alt: float = Field(
              ...,
              examples=[408.0],
              description="Altitude in kilometres.",
    )
    anomaly_score: float = Field(
              ...,
              ge=0.0,
              le=1.0,
              examples=[0.12],
              description=(
                            "Anomaly severity: "
                            "0.0 = normal, 1.0 = highly anomalous."
              ),
    )
    is_anomaly: bool = Field(
              ...,
              examples=[False],
              description="True if flagged as anomalous.",
    )


class PositionsResponse(BaseModel):
      """Batch response for all satellite positions."""

    timestamp: float = Field(
              ...,
              examples=[1709136000.0],
              description="Unix epoch of the computation.",
    )
    total_satellites: int = Field(
              ..., examples=[1000]
    )
    satellites: List[SatellitePosition]


# -------------------------------------------------------------------
# Lifespan: load data & train model at startup
# -------------------------------------------------------------------


@asynccontextmanager
async def lifespan(
      app: FastAPI,
) -> AsyncGenerator[None, None]:
      """Initialise satellite data and AI engine on startup.

          Loads TLE objects, extracts orbital features, trains the
              Isolation Forest anomaly detector, and caches everything
                  in ``APP_STATE`` for use by the request handlers.
                      """
      logger.info(
          "Initializing Space Data & AI Engine..."
      )

    sats: List[EarthSatellite] = load_tle_objects(
              data_dir=DEFAULT_DATA_DIR,
    )

    sats = sats[:MAX_SATELLITES]
    logger.info(
              "Limited to %d satellites for demo performance",
              len(sats),
    )
    APP_STATE["satellites"] = sats

    df: pd.DataFrame = extract_features(sats)
    detector = OrbitalAnomalyDetector()
    df_anomalies: pd.DataFrame = detector.fit_predict(df)
    APP_STATE["df_anomalies"] = df_anomalies

    logger.info(
              "Startup complete — %d satellites ready, "
              "%d anomalies detected",
              len(sats),
              int(df_anomalies["is_anomaly"].sum()),
    )

    yield

    APP_STATE["satellites"] = []
    APP_STATE["df_anomalies"] = None
    logger.info("Shutdown complete — resources released.")


# -------------------------------------------------------------------
# FastAPI application
# -------------------------------------------------------------------

app = FastAPI(
      title="AI-Orbit Intelligence 3D API",
      description=(
                "Real-time satellite position tracking enriched "
                "with Isolation Forest anomaly scores."
      ),
      version="0.4.0",
      lifespan=lifespan,
)

app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
)


# -------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------


@app.get(
      "/health",
      tags=["system"],
      summary="Health check",
)
async def health() -> Dict[str, Any]:
      """Return application health and loaded satellite count."""
      return {
          "status": "ok",
          "satellites_loaded": len(
              APP_STATE["satellites"]
          ),
      }


@app.get(
      "/api/positions",
      response_model=PositionsResponse,
      tags=["positions"],
      summary="Real-time satellite positions",
)
async def get_positions() -> PositionsResponse:
      """Compute current lat/lon/alt for every satellite.

          Propagates each satellite to the current instant using
              the Skyfield SGP4 engine, then enriches the result with
                  the pre-computed anomaly score from the Isolation Forest
                      model trained at startup.

                          Returns:
                                  PositionsResponse with a list of satellite positions.

                                      Raises:
                                              HTTPException: 503 if satellite data is not loaded.
                                                  """
      sats: List[EarthSatellite] = APP_STATE["satellites"]
      df_anom: pd.DataFrame = APP_STATE["df_anomalies"]

    if not sats or df_anom is None:
              raise HTTPException(
                            status_code=503,
                            detail=(
                                              "Satellite data not loaded. "
                                              "The server is still initialising."
                            ),
              )

    anomaly_index: Dict[int, Dict[str, Any]] = (
              df_anom[["anomaly_score", "is_anomaly"]]
              .to_dict("index")
    )

    t_now = ts.now()
    positions: List[SatellitePosition] = []

    for sat in sats:
              try:
                            geocentric = sat.at(t_now)
                            subpoint = geocentric.subpoint()

                  lat: float = subpoint.latitude.degrees
            lon: float = subpoint.longitude.degrees
            alt: float = subpoint.elevation.km
except Exception:  # noqa: BLE001
            continue

        norad_id: int = sat.model.satnum
        anom_data = anomaly_index.get(norad_id)

        if anom_data is not None:
                      score = float(anom_data["anomaly_score"])
                      flagged = bool(anom_data["is_anomaly"])
else:
            score = 0.0
            flagged = False

        positions.append(
                      SatellitePosition(
                                        name=sat.name,
                                        norad_id=norad_id,
                                        lat=round(lat, 4),
                                        lon=round(lon, 4),
                                        alt=round(alt, 2),
                                        anomaly_score=round(score, 4),
                                        is_anomaly=flagged,
                      )
        )

    return PositionsResponse(
              timestamp=time.time(),
              total_satellites=len(positions),
              satellites=positions,
    )


if __name__ == "__main__":
      uvicorn.run(
                "orbit_intel.api:app",
                host="0.0.0.0",
                port=8000,
                reload=True,
      )
